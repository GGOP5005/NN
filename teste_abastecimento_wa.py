"""
teste_abastecimento_wa.py
==========================
Testa o fluxo completo COM WhatsApp real.
Abre o grupo informado, baixa os cupons recentes e processa.

Uso:
  python teste_abastecimento_wa.py "Nome do Grupo"
  python teste_abastecimento_wa.py "Nome do Grupo" --lancar
  python teste_abastecimento_wa.py "Nome do Grupo" --lancar --limite 3
"""

import sys
import os
import json
import time
import re
import tempfile
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright

init(autoreset=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from robo_abastecimento import (
    extrair_dados_cupom_gemini,
    buscar_equipamento_por_placa,
    buscar_fornecedor_por_cnpj,
    buscar_combustivel_id,
    buscar_motorista_planilha,
    lancar_abastecimento,
    salvar_log,
    carregar_ids_processados,
    salvar_ids_processados,
    PASTA_CUPONS,
    log,
)

# Sessão separada do despachante para não colidir
PASTA_SESSAO_WA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WA_Session_Abastecimento")
from api_bsoft import BsoftAPI

# ── Argumentos ────────────────────────────────────────────────
DRY_RUN     = "--lancar" not in sys.argv
LIMITE      = 10  # máximo de cupons por execução
EMPRESAS_ID = os.environ.get("BSOFT_EMPRESA_ID", "2")

args = sys.argv[1:]
NOME_GRUPO = next((a for a in args if not a.startswith("--")), None)

if not NOME_GRUPO:
    print(Fore.RED + "❌ Informe o nome do grupo:")
    print(Fore.WHITE + '   python teste_abastecimento_wa.py "Frota 001"')
    sys.exit(1)

for i, a in enumerate(args):
    if a == "--limite" and i + 1 < len(args):
        try:
            LIMITE = int(args[i + 1])
        except ValueError:
            pass


def extrair_anexo(msg_node, page_ref) -> str | None:
    """
    Mesma lógica do despachante_whatsapp.py:
    hover → seta de contexto ou click direito → Baixar
    """
    try:
        msg_node.scroll_into_view_if_needed()
        msg_node.hover()
        time.sleep(0.5)

        # Tenta seta de contexto primeiro (igual ao despachante)
        btn_menu = msg_node.locator(
            'span[data-icon="ic-chevron-down-menu"], span[data-icon="down-context"]'
        ).first
        if btn_menu.is_visible():
            btn_menu.click(force=True)
        else:
            msg_node.click(button="right", force=True)

        time.sleep(1)

        btn_baixar = page_ref.locator(
            'ul li:has-text("Baixar"), ul li:has-text("Download"), '
            'div[role="button"]:has-text("Baixar")'
        ).first

        if btn_baixar.is_visible():
            with page_ref.expect_download(timeout=15000) as dl_info:
                btn_baixar.click(timeout=5000)
            dl  = dl_info.value
            ext = os.path.splitext(dl.suggested_filename)[1] or ".png"
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dest = os.path.join(PASTA_CUPONS, f"cupom_{int(time.time())}{ext}")
            dl.save_as(dest)
            return dest
        else:
            page_ref.keyboard.press("Escape")
    except Exception:
        try:
            page_ref.keyboard.press("Escape")
        except Exception:
            pass
    return None


def baixar_midias_grupo(page, nome_grupo: str, ids_processados: set) -> list:
    """
    Mesma arquitetura do despachante_whatsapp.py.
    Usa div.message-in para detectar mensagens recebidas com mídia.
    """
    cupons = []
    os.makedirs(PASTA_CUPONS, exist_ok=True)

    log(f"🔍 Procurando grupo '{nome_grupo}'...", Fore.YELLOW)

    # Abre o grupo (igual ao despachante)
    busca = page.locator(
        'input[data-tab="3"], div[contenteditable="true"][data-tab="3"]'
    ).first
    busca.click()
    time.sleep(0.5)
    busca.fill("")
    busca.type(nome_grupo, delay=50)
    time.sleep(2)

    grupo_loc = page.locator(f'span[title="{nome_grupo}"]').first
    if grupo_loc.count() == 0:
        log(f"❌ Grupo '{nome_grupo}' não encontrado.", Fore.RED)
        titulos = page.locator('span[data-testid="cell-frame-title"]').all()
        for t in titulos[:10]:
            try:
                print(f"     - {t.inner_text()}")
            except Exception:
                pass
        return cupons

    grupo_loc.click()
    time.sleep(3)
    log(f"✅ Grupo '{nome_grupo}' aberto.", Fore.GREEN)

    # Aguarda carregar (igual ao despachante)
    time.sleep(3)

    # Pega TODAS as mensagens recebidas com mídia (img ou document)
    # Igual ao despachante: div.message-in
    todas_msgs = page.locator('div.message-in').all()
    log(f"📱 {len(todas_msgs)} mensagem(ns) recebida(s) no grupo.", Fore.CYAN)

    msgs_com_midia = []
    for msg in todas_msgs:
        try:
            tem_midia = msg.locator('img, span[data-icon="document"]').count() > 0
            if tem_midia:
                data_id = msg.get_attribute("data-id") or msg.inner_text().strip()[:40]
                msgs_com_midia.append({"node": msg, "data_id": data_id})
        except Exception:
            pass

    log(f"🖼️  {len(msgs_com_midia)} mensagem(ns) com mídia.", Fore.CYAN)

    count = 0
    # Processa as mais recentes primeiro (últimas da lista)
    for item in reversed(msgs_com_midia):
        if count >= LIMITE:
            break

        data_id  = item["data_id"]
        msg_node = item["node"]

        if data_id in ids_processados:
            log(f"   ⏭️ Já processado.", Fore.WHITE)
            continue

        log(f"   📥 Baixando cupom {count + 1}...", Fore.CYAN)

        arquivo = extrair_anexo(msg_node, page)
        time.sleep(1)

        if arquivo:
            log(f"   ✅ Salvo: {os.path.basename(arquivo)}", Fore.GREEN)
            cupons.append({
                "id_msg":    data_id,
                "grupo":     nome_grupo,
                "arquivo":   arquivo,
                "remetente": "",
                "timestamp": "",
            })
            count += 1
        else:
            log(f"   ❌ Não foi possível baixar.", Fore.RED)

        time.sleep(1)

    return cupons


def processar_cupom(api, cupom, ids_processados):
    """Processa um cupom: extrai dados, resolve IDs, lança na Bsoft."""
    arquivo = cupom["arquivo"]
    grupo   = cupom["grupo"]
    id_msg  = cupom["id_msg"]

    print(Fore.BLUE + "\n" + "-" * 55)
    log(f"📄 Arquivo: {os.path.basename(arquivo)}", Fore.YELLOW)
    log(f"👤 Remetente: {cupom.get('remetente', '?')} | ⏰ {cupom.get('timestamp', '?')}", Fore.WHITE)

    entrada_log = {
        "id_msg": id_msg, "grupo": grupo,
        "arquivo": os.path.basename(arquivo),
        "processado_em": datetime.now().isoformat(),
        "dados_gemini": None, "equipamento_id": None,
        "fornecedor_id": None, "combustivel_id": None,
        "motorista_id": None, "resultado_bsoft": None,
        "status": "ERRO", "erro": "",
    }

    # Gemini
    log("🤖 Extraindo com Gemini...", Fore.WHITE)
    dados = extrair_dados_cupom_gemini(arquivo)
    if not dados:
        entrada_log["erro"] = "Gemini falhou"
        salvar_log(entrada_log)
        return False

    entrada_log["dados_gemini"] = dados
    print(Fore.CYAN + f"   Placa: {dados.get('placa')} | Litros: {dados.get('litros')} | "
                      f"Total: R${dados.get('valor_total')} | Data: {dados.get('data')}")
    print(Fore.CYAN + f"   Combustível: {dados.get('combustivel')} | Posto: {dados.get('posto_nome')}")
    print(Fore.CYAN + f"   CNPJ posto: {dados.get('posto_cnpj')} | KM: {dados.get('km_atual')}")

    if not dados.get("placa") or not dados.get("litros") or not dados.get("valor_total"):
        entrada_log["erro"] = "Dados incompletos"
        salvar_log(entrada_log)
        log("❌ Dados incompletos no cupom.", Fore.RED)
        return False

    # Equipamento
    equip_id = buscar_equipamento_por_placa(api, dados["placa"])
    if not equip_id:
        entrada_log["erro"] = f"Placa {dados['placa']} não encontrada"
        salvar_log(entrada_log)
        return False
    entrada_log["equipamento_id"] = equip_id

    # Fornecedor
    forn_id = buscar_fornecedor_por_cnpj(api, dados.get("posto_cnpj", ""))
    if not forn_id:
        entrada_log["erro"] = f"CNPJ {dados.get('posto_cnpj')} não encontrado"
        salvar_log(entrada_log)
        return False
    entrada_log["fornecedor_id"] = forn_id

    # Combustível
    comb_id = buscar_combustivel_id(api, dados.get("combustivel", ""))
    if not comb_id:
        entrada_log["erro"] = f"Combustível '{dados.get('combustivel')}' não mapeado"
        salvar_log(entrada_log)
        return False
    entrada_log["combustivel_id"] = comb_id

    # Motorista (opcional)
    motor_id = buscar_motorista_planilha(dados.get("placa", ""), dados.get("data", ""))
    entrada_log["motorista_id"] = motor_id

    # Resumo
    print(Fore.GREEN + f"\n   ✅ equipamentos_id={equip_id} | fornecedor_id={forn_id} | "
                       f"combustivel_id={comb_id} | motorista_id={motor_id or 'N/A'}")

    if DRY_RUN:
        log("⚠️  DRY RUN — não lançado. Use --lancar para lançar.", Fore.YELLOW)
        entrada_log["status"] = "DRY_RUN"
        salvar_log(entrada_log)
        return True

    # Lança
    log("📤 Lançando na Bsoft...", Fore.WHITE)
    dados["grupo_frota"] = grupo
    resultado = lancar_abastecimento(api, dados, equip_id, forn_id, comb_id, motor_id, EMPRESAS_ID)
    entrada_log["resultado_bsoft"] = resultado

    if resultado and (resultado.get("id") or resultado.get("success")):
        entrada_log["status"] = "OK"
        salvar_log(entrada_log)
        ids_processados.add(id_msg)
        salvar_ids_processados(ids_processados)
        log(f"✅ Lançado! id={resultado.get('id')}", Fore.GREEN)
        return True
    else:
        entrada_log["erro"] = str(resultado)
        salvar_log(entrada_log)
        log(f"❌ Falha: {resultado}", Fore.RED)
        return False


def main():
    print(Fore.BLUE + Style.BRIGHT + "=" * 55)
    print(Fore.BLUE + Style.BRIGHT + "   TESTE ABASTECIMENTO — WhatsApp Real")
    print(Fore.BLUE + Style.BRIGHT + f"   Grupo:  {NOME_GRUPO}")
    print(Fore.BLUE + Style.BRIGHT + f"   Limite: {LIMITE} cupons")
    print(Fore.BLUE + Style.BRIGHT + f"   Modo:   {'DRY RUN' if DRY_RUN else '🚨 LANÇAMENTO REAL'}")
    print(Fore.BLUE + Style.BRIGHT + "=" * 55 + "\n")

    ids_processados = carregar_ids_processados()
    api = BsoftAPI()
    cupons = []

    # Abre WhatsApp e baixa os cupons
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PASTA_SESSAO_WA,
            headless=False,           # visível para debug
            viewport={"width": 1280, "height": 720},
            accept_downloads=True,
        )
        page = browser.new_page()

        log("⏳ Carregando WhatsApp Web...", Fore.WHITE)
        page.goto("https://web.whatsapp.com/", timeout=60000)
        page.wait_for_selector(
            'input[data-tab="3"], div[contenteditable="true"][data-tab="3"]',
            timeout=60000
        )
        log("✅ WhatsApp conectado.", Fore.GREEN)
        time.sleep(3)

        cupons = baixar_midias_grupo(page, NOME_GRUPO, ids_processados)
        browser.close()

    log(f"\n📋 {len(cupons)} cupom(ns) baixado(s).", Fore.CYAN)

    if not cupons:
        log("Nenhum cupom novo para processar.", Fore.YELLOW)
        return

    # Processa cada cupom
    ok = erro = 0
    for cupom in cupons:
        if processar_cupom(api, cupom, ids_processados):
            ok += 1
        else:
            erro += 1

    print(Fore.BLUE + "\n" + "=" * 55)
    print(Fore.GREEN  + f"  ✅ OK    : {ok}")
    print(Fore.RED    + f"  ❌ Erro  : {erro}")
    print(Fore.BLUE   + "=" * 55)


if __name__ == "__main__":
    main()