"""
robo1_downloader_wa.py
=======================
Responsabilidade ÚNICA: entrar nos grupos WhatsApp e baixar imagens de cupons.
NÃO processa, NÃO lança na Bsoft.

Estratégia anti-scroll:
  - Entra no grupo
  - Pega APENAS as mensagens já visíveis na viewport (sem rolar)
  - Baixa via blob JS (sem clicar em nada)
  - Salva foto + metadado JSON na pasta de cupons
"""

import os
import sys
import json
import time
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright

init(autoreset=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BASE_DIR

GRUPOS_FROTA = {
    "001": "Abastecimento 001",
    "002": "Abastecimento 002",
    "003": "Abastecimento 003",
    "005": "Abastecimento 005",
    "006": "Abastecimento 006",
}

PASTA_SESSAO_WA  = os.path.join(BASE_DIR, "WA_Session_Abastecimento")
PASTA_CUPONS     = os.path.join(BASE_DIR, "cupons_abastecimento")
ARQUIVO_IDS_PROC = os.path.join(BASE_DIR, "logs", "abastecimento", "ids_processados.json")


def log(msg, cor=Fore.WHITE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{Style.RESET_ALL} {cor}{msg}{Style.RESET_ALL}")


def carregar_ids_processados() -> set:
    try:
        if os.path.exists(ARQUIVO_IDS_PROC):
            with open(ARQUIVO_IDS_PROC, "r", encoding="utf-8") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def salvar_ids_processados(ids: set):
    os.makedirs(os.path.dirname(ARQUIVO_IDS_PROC), exist_ok=True)
    with open(ARQUIVO_IDS_PROC, "w", encoding="utf-8") as f:
        json.dump(list(ids), f)


def baixar_blob(page, msg_node, destino: str) -> str | None:
    """Baixa imagem via JS sem nenhum clique ou scroll."""
    try:
        msg_node.scroll_into_view_if_needed()
        time.sleep(0.8)

        srcs = msg_node.evaluate("""node => {
            return Array.from(node.querySelectorAll('img'))
                .map(img => img.src)
                .filter(src => src && src.startsWith('blob:'));
        }""")

        if not srcs:
            return None

        b64 = page.evaluate(f"""async () => {{
            try {{
                const res  = await fetch('{srcs[0]}');
                const blob = await res.blob();
                return await new Promise(r => {{
                    const fr = new FileReader();
                    fr.onloadend = () => r(fr.result);
                    fr.readAsDataURL(blob);
                }});
            }} catch(e) {{ return null; }}
        }}""")

        if not b64 or ',' not in b64:
            return None

        dados = base64.b64decode(b64.split(',')[1])
        if len(dados) < 5000:
            return None

        with open(destino, 'wb') as f:
            f.write(dados)
        return destino

    except Exception as e:
        log(f"   ⚠️ blob: {e}", Fore.YELLOW)
        return None


def coletar_grupo(page, codigo: str, nome_grupo: str, ids_processados: set) -> list:
    """
    Entra no grupo e captura mensagens com imagem que já estão
    VISÍVEIS NA VIEWPORT — sem scroll algum.
    Retorna lista de dicts com metadados para o robô 2 processar.
    """
    salvos = []
    os.makedirs(PASTA_CUPONS, exist_ok=True)

    # Abre o grupo via busca
    busca = page.locator('input[data-tab="3"], div[contenteditable="true"][data-tab="3"]').first
    busca.click()
    time.sleep(0.3)
    busca.fill("")
    busca.type(nome_grupo, delay=40)
    time.sleep(2)

    grupo_loc = page.locator(f'span[title="{nome_grupo}"]').first
    if grupo_loc.count() == 0:
        log(f"   ⚠️ Grupo '{nome_grupo}' não encontrado.", Fore.YELLOW)
        return salvos

    grupo_loc.click()
    time.sleep(2.5)

    # Aguarda o chat carregar (sem rolar)
    try:
        page.wait_for_selector('div.message-in', timeout=8000)
    except Exception:
        log(f"   ⚠️ Nenhuma mensagem carregada em '{nome_grupo}'.", Fore.YELLOW)
        return salvos

    time.sleep(1.0)

    # Pega APENAS mensagens visíveis na viewport atual (sem scroll)
    # getBoundingClientRect().top >= 0 && bottom <= window.innerHeight
    msgs_visiveis = page.evaluate("""() => {
        const resultado = [];
        const msgs = document.querySelectorAll('div.message-in');
        const alturaJanela = window.innerHeight;
        msgs.forEach((msg, idx) => {
            const temImagem = !!msg.querySelector('img');
            if (!temImagem) return;
            const rect = msg.getBoundingClientRect();
            // Aceita mensagens visíveis OU próximas do fundo (últimas carregadas)
            const visivel = rect.top < alturaJanela + 300 && rect.bottom > -300;
            if (!visivel) return;
            resultado.push({
                dataId: msg.getAttribute('data-id') || ('noid_' + idx),
                nth: idx,
                top: rect.top,
            });
        });
        // Ordena por posição — as mais recentes ficam mais abaixo (top maior)
        resultado.sort((a, b) => b.top - a.top);
        return resultado;
    }""")

    log(f"   📱 '{nome_grupo}': {len(msgs_visiveis)} imagem(ns) visível(is)", Fore.CYAN)

    # Pega as 5 mais recentes (top maior = mais abaixo na tela)
    for item in msgs_visiveis[:5]:
        data_id = item['dataId']
        nth     = item['nth']

        if data_id in ids_processados:
            log(f"   ⏭️ Já baixado: {data_id[:35]}", Fore.WHITE)
            continue

        msg_node = page.locator('div.message-in').nth(nth)

        ts  = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = os.path.join(PASTA_CUPONS, f"cupom_{codigo}_{ts}.jpg")

        log(f"   📥 Baixando {data_id[:35]}...", Fore.CYAN)
        resultado = baixar_blob(page, msg_node, dest)

        if not resultado:
            log(f"   ⚠️ Falha no download.", Fore.YELLOW)
            ids_processados.add(data_id)
            continue

        hash_arq = hashlib.md5(open(dest, 'rb').read()).hexdigest()
        if hash_arq in ids_processados:
            os.remove(dest)
            ids_processados.add(data_id)
            log(f"   ⏭️ Duplicata (hash).", Fore.WHITE)
            continue

        # Salva metadado JSON junto com a imagem
        meta = {
            "id_msg":        data_id,
            "grupo":         nome_grupo,
            "codigo_grupo":  codigo,
            "arquivo":       os.path.basename(dest),
            "hash":          hash_arq,
            "baixado_em":    datetime.now().isoformat(),
            "processado":    False,
        }
        meta_path = dest.replace('.jpg', '.json').replace('.png', '.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        ids_processados.add(data_id)
        ids_processados.add(hash_arq)

        tamanho = os.path.getsize(dest)
        log(f"   ✅ Salvo: {os.path.basename(dest)} ({tamanho//1024}KB)", Fore.GREEN)
        salvos.append(meta)
        time.sleep(0.5)

    return salvos


def executar():
    log("🚀 Robô 1 — Downloader WhatsApp", Fore.BLUE)
    ids_processados = carregar_ids_processados()
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PASTA_SESSAO_WA,
            headless=False,
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
        )
        page = browser.new_page()

        try:
            log("⏳ Carregando WhatsApp Web...", Fore.WHITE)
            page.goto("https://web.whatsapp.com/", timeout=60000)
            page.wait_for_selector(
                'input[data-tab="3"], div[contenteditable="true"][data-tab="3"]',
                timeout=60000
            )
            log("✅ WhatsApp conectado.", Fore.GREEN)
            time.sleep(4)

            for codigo, nome in GRUPOS_FROTA.items():
                log(f"\n📱 Grupo: {nome}", Fore.YELLOW)
                salvos = coletar_grupo(page, codigo, nome, ids_processados)
                total += len(salvos)

        except Exception as e:
            log(f"❌ Erro crítico: {e}", Fore.RED)
        finally:
            salvar_ids_processados(ids_processados)
            browser.close()

    log(f"\n✅ Total baixado: {total} imagem(ns)", Fore.GREEN)
    return total


if __name__ == "__main__":
    executar()