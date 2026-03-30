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
import hashlib
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
LIMITE      = 3   # máximo de cupons por execução
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
    Captura a imagem via blob JS — sem nenhum clique no menu.
    Evita o problema de o WA fechar o grupo ao clicar em botões.
    """
    try:
        msg_node.scroll_into_view_if_needed()
        time.sleep(0.5)

        # Pega src de todas as imagens dentro da mensagem
        srcs = msg_node.evaluate("""node => {
            return Array.from(node.querySelectorAll('img'))
                .map(img => img.src)
                .filter(src => src && src.startsWith('blob:'));
        }""")

        if not srcs:
            return None

        img_src = srcs[0]

        b64 = page_ref.evaluate(f"""async () => {{
            try {{
                const res  = await fetch('{img_src}');
                const blob = await res.blob();
                return await new Promise(resolve => {{
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                }});
            }} catch(e) {{ return null; }}
        }}""")

        if not b64 or ',' not in b64:
            return None

        import base64 as _b64
        dados = _b64.b64decode(b64.split(',')[1])
        ext   = '.jpg' if 'jpeg' in b64 else '.png'
        dest  = os.path.join(PASTA_CUPONS, f"cupom_{int(time.time())}{ext}")
        with open(dest, 'wb') as f_out:
            f_out.write(dados)

        return dest

    except Exception as e:
        log(f"   ⚠️ extrair_anexo: {e}", Fore.YELLOW)
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
    from datetime import timedelta

    hoje    = datetime.now()
    limite  = hoje - timedelta(hours=36)

    # Lê os separadores de data + mensagens em ordem para saber a data de cada msg
    # O WA renderiza separadores como: "Hoje", "Ontem", "sexta-feira", "26/03/2026"
    # Estratégia: varre o DOM inteiro em ordem e usa os separadores de data
    # para saber qual data cada mensagem pertence
    # Usa posição Y no viewport para correlacionar mensagens com separadores de data
    dados_dom = page.evaluate("""() => {
        // Separadores: span[dir=auto] com fontSize 12px
        const separadores = [];
        document.querySelectorAll('span[dir="auto"]').forEach(span => {
            const style = span.getAttribute('style') || '';
            if (!style.includes('--x-fontSize: 12px')) return;
            const txt = (span.innerText || '').trim();
            if (!txt || txt.length > 20) return;
            const eh_data = txt.includes('/') ||
                /^(hoje|ontem|seg|ter|qua|qui|sex|s[aá]b|dom)/i.test(txt);
            if (!eh_data) return;
            const rect = span.getBoundingClientRect();
            separadores.push({ texto: txt, y: rect.top + window.scrollY });
        });

        // Mensagens recebidas com mídia — guarda índice para usar nth()
        const mensagens = [];
        let idx = 0;
        document.querySelectorAll('div.message-in').forEach(msg => {
            const temMidia = !!msg.querySelector('img') ||
                             !!msg.querySelector('span[data-icon="document"]');
            const midiaNth = idx; idx++;
            if (!temMidia) return;
            const dataId = msg.getAttribute('data-id') || ('noid_' + midiaNth);
            const rect = msg.getBoundingClientRect();
            mensagens.push({ dataId, y: rect.top + window.scrollY, nth: midiaNth });
        });

        return { separadores: separadores.sort((a,b)=>a.y-b.y),
                 mensagens:   mensagens.sort((a,b)=>a.y-b.y) };
    }""")

    separadores = dados_dom.get('separadores', [])
    mensagens   = dados_dom.get('mensagens', [])

    seps = [s['texto'] for s in separadores]
    log(f"   📅 Separadores detectados: {seps}", Fore.CYAN)
    log(f"   📨 {len(mensagens)} msg(s) com mídia encontradas no DOM", Fore.CYAN)

    DIAS_PT = {'hoje': hoje.date(), 'ontem': (hoje - timedelta(days=1)).date()}
    for i in range(2, 8):
        d = hoje - timedelta(days=i)
        mapa = {'Monday':'segunda','Tuesday':'terça','Wednesday':'quarta',
                'Thursday':'quinta','Friday':'sexta','Saturday':'sábado','Sunday':'domingo'}
        nome_pt = mapa.get(d.strftime('%A'), '').lower()
        if nome_pt:
            DIAS_PT[nome_pt] = d.date()
            DIAS_PT[nome_pt[:3]] = d.date()

    def txt_para_data(txt):
        txt_low = txt.lower().strip()
        if '/' in txt:
            try:
                p = txt.split('/')
                return datetime(int(p[2]), int(p[1]), int(p[0])).date()
            except Exception:
                return None
        for chave, val in DIAS_PT.items():
            if txt_low.startswith(chave):
                return val
        return None

    todas_msgs = page.locator('div.message-in').all()
    log(f"📱 {len(todas_msgs)} mensagem(ns) recebida(s) no grupo.", Fore.CYAN)

    msgs_com_midia = []
    for msg_info in mensagens:
        data_id = msg_info['dataId']
        msg_y   = msg_info['y']

        if data_id in ids_processados:
            log(f"   ⏭️ Já processado: {data_id[:40]}", Fore.WHITE)
            continue

        # Separador imediatamente antes desta mensagem (maior Y <= msg_y)
        sep_antes = None
        for sep in separadores:
            if sep['y'] <= msg_y:
                sep_antes = sep
        
        data_msg = txt_para_data(sep_antes['texto']) if sep_antes else None

        if data_msg:
            data_dt    = datetime.combine(data_msg, datetime.min.time())
            diff_horas = (hoje - data_dt).total_seconds() / 3600
            if diff_horas > 48:
                log(f"   🗓️ Mensagem de {data_msg} ignorada ({diff_horas:.0f}h)", Fore.WHITE)
                continue

        # Usa índice nth para achar o node correto (evita problema com @ no CSS)
        nth = msg_info.get("nth", -1)
        if nth >= 0:
            node_encontrado = page.locator('div.message-in').nth(nth)
        else:
            node_encontrado = None
            todos = page.locator('div.message-in').all()
            for n in todos:
                try:
                    if (n.get_attribute("data-id") or "") == data_id:
                        node_encontrado = n
                        break
                except Exception:
                    pass

        if not node_encontrado:
            log(f"   ⚠️ Node não encontrado: {data_id[:40]}", Fore.YELLOW)
            continue

        log(f"   ✅ Aceita: data={data_msg} | id={data_id[:40]}", Fore.CYAN)
        msgs_com_midia.append({"node": node_encontrado, "data_id": data_id, "ts": str(data_msg or "")})

    # Fallback: sem separadores detectados
    if not separadores:
        log("   ⚠️ Sem separadores — fallback sem filtro.", Fore.YELLOW)
        for msg in todas_msgs:
            try:
                tem_midia = msg.locator('img, span[data-icon="document"]').count() > 0
                if not tem_midia: continue
                data_id = msg.get_attribute("data-id") or f"noid_{len(msgs_com_midia)}"
                if data_id in ids_processados: continue
                msgs_com_midia.append({"node": msg, "data_id": data_id, "ts": ""})
            except Exception:
                pass

    log(f"🖼️  {len(msgs_com_midia)} mensagem(ns) com mídia para processar.", Fore.CYAN)

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

        log(f"   📥 Baixando cupom {count + 1} ({item.get('ts', '?')})...", Fore.CYAN)

        arquivo = extrair_anexo(msg_node, page)
        time.sleep(1)

        if arquivo:
            tamanho = os.path.getsize(arquivo)
            hash_arq = hashlib.md5(open(arquivo, "rb").read()).hexdigest()
            log(f"   🔍 data_id={data_id[:40]} | tamanho={tamanho}B | hash={hash_arq[:8]}", Fore.MAGENTA)
            log(f"       ids_proc contém data_id: {data_id in ids_processados} | hash: {hash_arq in ids_processados}", Fore.MAGENTA)

            if tamanho < 5000:
                log(f"   ⏭️ Arquivo muito pequeno ({tamanho}B) — descartado.", Fore.YELLOW)
                os.remove(arquivo)
                ids_processados.add(data_id)
                continue

            if hash_arq in ids_processados:
                log(f"   ⏭️ Hash já processado — descartado.", Fore.WHITE)
                os.remove(arquivo)
                ids_processados.add(data_id)
                salvar_ids_processados(ids_processados)
                continue

            log(f"   ✅ Salvo: {os.path.basename(arquivo)} ({tamanho//1024}KB)", Fore.GREEN)
            cupons.append({
                "id_msg":    data_id,
                "grupo":     nome_grupo,
                "arquivo":   arquivo,
                "remetente": "",
                "timestamp": item.get("ts", ""),
            })
            count += 1
        else:
            log(f"   ❌ Não foi possível baixar — pulando.", Fore.RED)
            ids_processados.add(data_id)  # marca para não travar de novo

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
        entrada_log["erro"] = "Dados incompletos — provavelmente foto de hodômetro"
        salvar_log(entrada_log)
        log("❌ Dados incompletos — marcando como processado para não repetir.", Fore.YELLOW)
        # Salva hash para não baixar de novo
        hash_arq = hashlib.md5(open(arquivo, "rb").read()).hexdigest()
        ids_processados.add(hash_arq)
        ids_processados.add(cupom["id_msg"])
        salvar_ids_processados(ids_processados)
        return False

    # Valida data — ignora cupons com mais de 36h
    if dados.get("data"):
        try:
            from datetime import timedelta
            data_cupom = datetime.strptime(dados["data"], "%Y-%m-%d")
            if (datetime.now() - data_cupom).total_seconds() > 36 * 3600:
                log(f"   ⏭️ Cupom antigo ({dados['data']}) — ignorando.", Fore.YELLOW)
                # Persiste hash+id imediatamente para não baixar de novo
                hash_arquivo = hashlib.md5(open(arquivo, "rb").read()).hexdigest()
                ids_processados.add(hash_arquivo)
                ids_processados.add(cupom["id_msg"])
                salvar_ids_processados(ids_processados)
                log(f"   💾 Hash {hash_arquivo[:8]} salvo — não vai baixar de novo.", Fore.CYAN)
                entrada_log["erro"] = f"Cupom antigo: {dados['data']}"
                salvar_log(entrada_log)
                return False
        except Exception:
            pass

    # Equipamento
    equip_id = buscar_equipamento_por_placa(api, dados["placa"])
    if not equip_id:
        entrada_log["erro"] = f"Placa {dados['placa']} não encontrada"
        salvar_log(entrada_log)
        return False
    entrada_log["equipamento_id"] = equip_id

    # Fornecedor — tenta CNPJ exato, fuzzy por nome+CNPJ, depois só nome
    from robo_abastecimento import buscar_fornecedor_por_nome
    forn_id = buscar_fornecedor_por_cnpj(api, dados.get("posto_cnpj", ""), dados.get("posto_nome", ""))
    if not forn_id and dados.get("posto_nome"):
        forn_id = buscar_fornecedor_por_nome(api, dados["posto_nome"], dados.get("posto_cnpj",""))
    if not forn_id:
        entrada_log["erro"] = f"Fornecedor não encontrado: CNPJ={dados.get('posto_cnpj')} Nome={dados.get('posto_nome')}"
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

    # Motorista — CPF do cupom → planilha → nome → ID Bsoft
    from robo_abastecimento import buscar_motorista_id_por_nome, buscar_motorista_id_por_cpf
    motor_id = None
    if dados.get("motorista_cpf"):
        motor_id = buscar_motorista_id_por_cpf(api, dados["motorista_cpf"])
    if not motor_id:
        nome_motorista = buscar_motorista_planilha(dados.get("placa", ""), dados.get("data", ""))
        if nome_motorista:
            motor_id = buscar_motorista_id_por_nome(api, nome_motorista)
    if not motor_id and dados.get("motorista"):
        motor_id = buscar_motorista_id_por_nome(api, dados["motorista"])
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

    if resultado and (resultado.get("id") or resultado.get("success") or resultado.get("codAbastecimento")):
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