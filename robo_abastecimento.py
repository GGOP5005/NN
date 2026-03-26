"""
robo_abastecimento.py
======================
Robô que roda 2x ao dia (08:00 e 20:00).
Fluxo:
  1. Abre WhatsApp Web (sessão já salva)
  2. Entra nos grupos Frota 001, 002, 003, 005, 006
  3. Baixa imagens/PDFs não processados (desde o último ciclo)
  4. Gemini Vision extrai dados do cupom fiscal
  5. Busca equipamentos_id pela placa na API Bsoft
  6. Busca fornecedor_id pelo CNPJ do posto na API Bsoft
  7. Confirma motorista_id via planilha Google Sheets (placa + data)
  8. POST /manutencao/v1/abastecimentos
  9. Salva log completo em JSON + envia confirmação no grupo
"""

import os
import re
import json
import time
import base64
import hashlib
import schedule
import tempfile
import unicodedata
from datetime import datetime, date
from pathlib import Path
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
import requests
from requests.auth import HTTPBasicAuth

from config import (
    BASE_DIR, BSOFT_USUARIO, BSOFT_SENHA, BSOFT_BASE_URL,
    LISTA_CHAVES_GEMINI, PLANILHA_ID
)
from api_bsoft import BsoftAPI

init(autoreset=True)

# =============================================================
# CONFIGURAÇÕES
# =============================================================

# Grupos WhatsApp da frota (nome exato como aparece no WhatsApp)
GRUPOS_FROTA = {
    "001": "Frota 001",
    "002": "Frota 002",
    "003": "Frota 003",
    "005": "Frota 005",
    "006": "Frota 006",
}

PASTA_SESSAO_WA  = os.path.join(BASE_DIR, "WA_Session_Abastecimento")
PASTA_CUPONS     = os.path.join(BASE_DIR, "cupons_abastecimento")
PASTA_LOGS       = os.path.join(BASE_DIR, "logs", "abastecimento")
ARQUIVO_IDS_PROC = os.path.join(BASE_DIR, "logs", "abastecimento", "ids_processados.json")

# Cache Bsoft (evita chamadas repetidas por execução)
_cache_equipamentos: dict = {}   # placa → equipamentos_id
_cache_fornecedores: dict = {}   # cnpj  → fornecedor_id
_cache_combustiveis: dict = {}   # descricao → combustivel_id
_cache_motoristas:   dict = {}   # (placa, data_str) → motorista_id

# Aba da planilha com a escala de motoristas
ABA_ESCALA = "FROTA"  # ajuste se o nome da aba for diferente


# =============================================================
# UTILITÁRIOS
# =============================================================

def log(msg: str, cor=Fore.WHITE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{Style.RESET_ALL} {cor}{msg}{Style.RESET_ALL}")

def normalizar(texto: str) -> str:
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    ).upper().strip()

def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")

def limpar_placa(placa: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (placa or "").upper())

def formatar_moeda(valor) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(valor)

def gerar_id_msg(grupo: str, timestamp: str, conteudo: str) -> str:
    chave = f"{grupo}:{timestamp}:{conteudo[:50]}"
    return hashlib.md5(chave.encode()).hexdigest()


# =============================================================
# PERSISTÊNCIA DE IDs PROCESSADOS
# =============================================================

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


# =============================================================
# GEMINI VISION — EXTRAÇÃO DO CUPOM
# =============================================================

PROMPT_CUPOM = """
Você é um extrator de dados de cupons fiscais de abastecimento de combustível.
Analise a imagem/documento e retorne APENAS um JSON com os campos abaixo.
Se um campo não estiver visível, retorne "".

{
  "posto_nome": "Nome do posto/empresa",
  "posto_cnpj": "CNPJ do posto somente números",
  "posto_cidade": "Cidade",
  "posto_uf": "UF (2 letras)",
  "data": "YYYY-MM-DD",
  "hora": "HH:MM:SS",
  "combustivel": "Nome do combustível (ex: DIESEL S10, GASOLINA COMUM)",
  "litros": "Quantidade em litros (número decimal, ponto como separador)",
  "valor_unitario": "Valor por litro (número decimal)",
  "valor_total": "Valor total pago (número decimal)",
  "placa": "Placa do veículo (formato AAA-0000 ou AAA0A00)",
  "motorista": "Nome do motorista se aparecer",
  "km_atual": "Quilometragem atual do veículo se aparecer",
  "numero_cupom": "Número do documento fiscal",
  "chave_acesso": "Chave de acesso NF-e (44 dígitos) se aparecer"
}

Retorne APENAS o JSON, sem texto adicional, sem markdown.
"""

def extrair_dados_cupom_gemini(caminho_arquivo: str) -> dict | None:
    """Usa Gemini Vision para extrair dados do cupom (imagem ou PDF)."""
    from google import genai
    from google.genai import types

    extensao = Path(caminho_arquivo).suffix.lower()

    with open(caminho_arquivo, "rb") as f:
        conteudo_bytes = f.read()

    if extensao in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif extensao == ".png":
        mime = "image/png"
    elif extensao == ".pdf":
        mime = "application/pdf"
    elif extensao == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    for chave in LISTA_CHAVES_GEMINI:
        try:
            client = genai.Client(api_key=chave)
            resposta = client.models.generate_content(
                model="gemini-2.5-flash-preview-04-17",
                contents=[
                    PROMPT_CUPOM,
                    types.Part.from_bytes(data=conteudo_bytes, mime_type=mime),
                ]
            )
            texto = resposta.text.strip()
            texto = re.sub(r"```(?:json)?", "", texto).strip().rstrip("`").strip()
            dados = json.loads(texto)
            return dados
        except json.JSONDecodeError:
            log(f"   ⚠️ Gemini retornou JSON inválido. Tentando próxima chave...", Fore.YELLOW)
        except Exception as e:
            log(f"   ⚠️ Chave Gemini falhou: {e}", Fore.YELLOW)

    return None


# =============================================================
# CACHE BSOFT — EQUIPAMENTOS / FORNECEDORES / COMBUSTÍVEIS
# =============================================================

def buscar_equipamento_por_placa(api: BsoftAPI, placa: str) -> str | None:
    """
    Busca equipamento pelo campo 'equipamento' que vem no formato 'PLACA/UF'.
    Ex: 'KUZ-4E30/PE' → id='2'
    """
    placa_norm = limpar_placa(placa)
    if placa_norm in _cache_equipamentos:
        return _cache_equipamentos[placa_norm]

    # Carrega todos (só 10 veículos — sem paginação necessária)
    equipamentos = api.get("manutencao/v1/equipamentos")
    if not equipamentos:
        return None

    lista = equipamentos if isinstance(equipamentos, list) else equipamentos.get("data", [])
    for eq in lista:
        # Formato: "KUZ-4E30/PE" — pega só a parte antes da /
        campo = str(eq.get("equipamento") or "")
        placa_campo = limpar_placa(campo.split("/")[0])
        if placa_campo == placa_norm:
            eid = str(eq.get("id") or "")
            _cache_equipamentos[placa_norm] = eid
            log(f"   ✅ Equipamento: {campo} → id={eid}", Fore.GREEN)
            return eid

    log(f"   ❌ Placa {placa} não encontrada nos equipamentos Bsoft.", Fore.RED)
    log(f"      Placas disponíveis: {[e.get('equipamento','') for e in lista]}", Fore.YELLOW)
    return None


def buscar_fornecedor_por_cnpj(api: BsoftAPI, cnpj: str) -> str | None:
    cnpj_norm = limpar_cnpj(cnpj)
    if cnpj_norm in _cache_fornecedores:
        return _cache_fornecedores[cnpj_norm]

    resultado = api.get("pessoas/v1/pessoas/juridicas", params={"cnpj": cnpj_norm}, paginar=False)
    if not resultado:
        return None

    lista = resultado if isinstance(resultado, list) else resultado.get("data", [])
    for pessoa in lista:
        cnpj_pessoa = limpar_cnpj(pessoa.get("cnpj") or "")
        if cnpj_pessoa == cnpj_norm:
            fid = str(pessoa.get("id") or pessoa.get("codPessoa") or "")
            _cache_fornecedores[cnpj_norm] = fid
            log(f"   ✅ Fornecedor encontrado: CNPJ={cnpj} → id={fid}", Fore.GREEN)
            return fid

    log(f"   ❌ Fornecedor CNPJ {cnpj} não encontrado na Bsoft.", Fore.RED)
    return None


# Mapa fixo baseado nos combustíveis reais da Bsoft (confirmado via API)
_MAPA_COMBUSTIVEIS = {
    "DIESEL S-10": "2",
    "DIESEL S10":  "2",
    "DIESEL":      "1",
    "GASOLINA":    "4",
    "ETANOL":      "3",
}

def buscar_combustivel_id(api: BsoftAPI, nome_combustivel: str) -> str | None:
    """
    Resolve combustível pelo nome do cupom → id Bsoft.
    Mapa: DIESEL S10 → 2 | DIESEL → 1 | GASOLINA → 4 | ETANOL → 3
    """
    nome_norm = normalizar(nome_combustivel)
    if nome_norm in _cache_combustiveis:
        return _cache_combustiveis[nome_norm]

    # Tenta mapa fixo primeiro (mais rápido)
    for chave, cid in _MAPA_COMBUSTIVEIS.items():
        if chave in nome_norm:
            _cache_combustiveis[nome_norm] = cid
            log(f"   ⛽ Combustível: '{nome_combustivel}' → id={cid}", Fore.CYAN)
            return cid

    # Fallback: busca na API
    resultado = api.get("manutencao/v1/combustiveis")
    if not resultado:
        log(f"   ⚠️ Combustível '{nome_combustivel}' não mapeado.", Fore.YELLOW)
        return None

    lista = resultado if isinstance(resultado, list) else resultado.get("data", [])
    for comb in lista:
        desc = normalizar(comb.get("descricao") or "")
        palavras = [p for p in nome_norm.split() if len(p) >= 3]
        if any(p in desc for p in palavras):
            cid = str(comb.get("id") or "")
            _cache_combustiveis[nome_norm] = cid
            log(f"   ⛽ Combustível API: '{nome_combustivel}' → '{comb.get('descricao')}' id={cid}", Fore.CYAN)
            return cid

    log(f"   ⚠️ Combustível '{nome_combustivel}' não encontrado.", Fore.YELLOW)
    return None


# =============================================================
# PLANILHA — MOTORISTA POR PLACA + DATA
# =============================================================

def buscar_motorista_planilha(placa: str, data_abastecimento: str) -> str | None:
    """
    Consulta a planilha de escala para encontrar o motorista_id Bsoft.
    Espera que a aba ABA_ESCALA tenha colunas: DATA | PLACA | MOTORISTA | ID_BSOFT
    """
    chave = (limpar_placa(placa), data_abastecimento)
    if chave in _cache_motoristas:
        return _cache_motoristas[chave]

    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials

        CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
        SCOPES     = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds      = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        service    = build("sheets", "v4", credentials=creds)

        res = service.spreadsheets().values().get(
            spreadsheetId=PLANILHA_ID,
            range=f"{ABA_ESCALA}!A:D"
        ).execute()

        linhas = res.get("values", [])
        if not linhas:
            return None

        headers = [normalizar(h) for h in linhas[0]]
        idx_data     = next((i for i, h in enumerate(headers) if "DATA"     in h), 0)
        idx_placa    = next((i for i, h in enumerate(headers) if "PLACA"    in h), 1)
        idx_motorist = next((i for i, h in enumerate(headers) if "MOTORISTA" in h), 2)
        idx_id       = next((i for i, h in enumerate(headers) if "ID" in h or "BSOFT" in h), 3)

        placa_busca = limpar_placa(placa)

        for linha in linhas[1:]:
            if len(linha) <= max(idx_data, idx_placa, idx_id):
                continue
            data_cell  = str(linha[idx_data]).strip() if idx_data < len(linha) else ""
            placa_cell = limpar_placa(linha[idx_placa] if idx_placa < len(linha) else "")
            id_bsoft   = str(linha[idx_id]).strip() if idx_id < len(linha) else ""

            # Normaliza data para YYYY-MM-DD
            data_norm = data_cell.replace("/", "-")
            if len(data_norm) == 10 and data_norm[2] == "-":
                # DD-MM-YYYY → YYYY-MM-DD
                d, m, a = data_norm.split("-")
                data_norm = f"{a}-{m}-{d}"

            if placa_cell == placa_busca and data_norm == data_abastecimento:
                if id_bsoft:
                    _cache_motoristas[chave] = id_bsoft
                    nome = linha[idx_motorist] if idx_motorist < len(linha) else "?"
                    log(f"   ✅ Motorista planilha: {nome} (id={id_bsoft})", Fore.GREEN)
                    return id_bsoft

    except Exception as e:
        log(f"   ⚠️ Erro ao consultar planilha de escala: {e}", Fore.YELLOW)

    return None


# =============================================================
# LOG JSON
# =============================================================

def salvar_log(entrada: dict):
    os.makedirs(PASTA_LOGS, exist_ok=True)
    hoje = date.today().strftime("%Y-%m-%d")
    arquivo = os.path.join(PASTA_LOGS, f"abastecimento_{hoje}.json")

    registros = []
    if os.path.exists(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                registros = json.load(f)
        except Exception:
            pass

    registros.append(entrada)

    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)


# =============================================================
# LANÇAMENTO NA BSOFT
# =============================================================

def lancar_abastecimento(api: BsoftAPI, dados: dict, equipamento_id: str,
                          fornecedor_id: str, combustivel_id: str,
                          motorista_id: str | None, empresas_id: str) -> dict:
    """
    Monta e envia o POST para a API Bsoft.
    Campos confirmados via abastecimentos existentes na API.
    """
    body = {
        "equipamentos_id":    equipamento_id,
        "dtAbastecimento":    dados.get("data", ""),
        "ltsAbastecidos":     float(dados.get("litros", 0) or 0),
        "valorUnitario":      float(dados.get("valor_unitario", 0) or 0),
        "valorAbastecimento": float(dados.get("valor_total", 0) or 0),
        "localAbastecimento": dados.get("posto_cidade", ""),
        "ufAbastecimento":    dados.get("posto_uf", ""),
        "fornecedor_id":      fornecedor_id,
        "combustivel_id":     combustivel_id,
        "empresas_id":        empresas_id,  # Matriz Norte Nordeste = 2
        "tanqueCheio":        "N",
        "observacao":         (
            f"Lançado automaticamente via WhatsApp | "
            f"Cupom: {dados.get('numero_cupom', '')} | "
            f"Grupo: {dados.get('grupo_frota', '')}"
        ),
    }

    # KM atual (leitura) — vem do cupom como km_atual
    if dados.get("km_atual"):
        try:
            body["leitura"] = int(float(str(dados["km_atual"]).replace(".", "").replace(",", "")))
        except Exception:
            pass

    # Motorista
    if motorista_id:
        body["operadorMotorista_id"] = motorista_id

    # Documento fiscal
    if dados.get("numero_cupom"):
        body["tipoDocumento_id"] = "NFE"
        body["nroDoc"]           = str(dados["numero_cupom"])

    # Chave de acesso NF-e
    if dados.get("chave_acesso"):
        body["chaveAcesso"] = re.sub(r"\D", "", dados["chave_acesso"])

    log(f"   📦 Body POST abastecimento: {json.dumps(body, ensure_ascii=False)}", Fore.CYAN)
    resultado = api.post("manutencao/v1/abastecimentos", body)
    return resultado or {}


# =============================================================
# WHATSAPP — COLETA DE CUPONS
# =============================================================

def coletar_cupons_grupo(page, nome_grupo: str, ids_processados: set) -> list:
    """
    Abre o grupo no WhatsApp Web, percorre mensagens recentes
    e baixa imagens/PDFs não processados.
    Retorna lista de dicts: {id_msg, grupo, arquivo, timestamp_msg, remetente}
    """
    cupons = []

    try:
        # Busca o grupo na lista de conversas
        campo_busca = page.locator('input[data-tab="3"], div[contenteditable="true"][data-tab="3"]').first
        campo_busca.click()
        time.sleep(0.5)
        campo_busca.fill("")
        campo_busca.type(nome_grupo, delay=60)
        time.sleep(2)

        # Clica no grupo encontrado
        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        if resultado.count() == 0:
            log(f"   ⚠️ Grupo '{nome_grupo}' não encontrado.", Fore.YELLOW)
            return cupons

        resultado.click()
        time.sleep(2)

        # Pega mensagens com imagem ou documento nas últimas 50 mensagens
        msgs_midia = page.evaluate("""() => {
            const resultado = [];
            const msgs = document.querySelectorAll(
                'div[data-id] img.x9f619, div[data-id] span[data-icon="document-filled"]'
            );
            msgs.forEach(el => {
                const container = el.closest('div[data-id]');
                if (!container) return;
                const dataId = container.getAttribute('data-id');
                const timestamp = container.querySelector('span[data-testid="msg-meta"] span')?.innerText || '';
                const remetente = container.querySelector('span[data-testid="author"]')?.innerText || '';
                resultado.push({ dataId, timestamp, remetente });
            });
            return resultado;
        }""")

        log(f"   📱 Grupo '{nome_grupo}': {len(msgs_midia)} mídias encontradas.", Fore.CYAN)

        os.makedirs(PASTA_CUPONS, exist_ok=True)

        for msg in msgs_midia:
            id_msg = msg.get("dataId", "")
            if not id_msg or id_msg in ids_processados:
                continue

            # Clica na mensagem para expandir/download
            try:
                container = page.locator(f'div[data-id="{id_msg}"]').first
                if container.count() == 0:
                    continue

                # Baixa com expect_download
                with page.expect_download(timeout=15000) as dl_info:
                    # Tenta clicar no botão de download se existir
                    btn_dl = container.locator('span[data-icon="download"]').first
                    if btn_dl.count() > 0:
                        btn_dl.click(force=True)
                    else:
                        # Clica na imagem diretamente — abre visualizador
                        container.locator("img").first.click(force=True)
                        time.sleep(1)
                        # Botão de download no visualizador
                        dl_btn = page.locator('span[data-icon="download"]').first
                        if dl_btn.count() > 0:
                            dl_btn.click(force=True)
                        else:
                            # Fallback: tira screenshot da imagem expandida
                            img_el = page.locator('img[src*="blob:"]').first
                            if img_el.count() > 0:
                                ts_nome = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                                nome_arquivo = os.path.join(PASTA_CUPONS, f"cupom_{nome_grupo}_{ts_nome}.png")
                                img_el.screenshot(path=nome_arquivo)
                                page.keyboard.press("Escape")
                                cupons.append({
                                    "id_msg":    id_msg,
                                    "grupo":     nome_grupo,
                                    "arquivo":   nome_arquivo,
                                    "timestamp": msg.get("timestamp", ""),
                                    "remetente": msg.get("remetente", ""),
                                })
                                continue

                download = dl_info.value
                ext = Path(download.suggested_filename).suffix or ".jpg"
                ts_nome = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                nome_arquivo = os.path.join(PASTA_CUPONS, f"cupom_{nome_grupo}_{ts_nome}{ext}")
                download.save_as(nome_arquivo)

                # Fecha visualizador se aberto
                page.keyboard.press("Escape")
                time.sleep(0.5)

                cupons.append({
                    "id_msg":    id_msg,
                    "grupo":     nome_grupo,
                    "arquivo":   nome_arquivo,
                    "timestamp": msg.get("timestamp", ""),
                    "remetente": msg.get("remetente", ""),
                })
                log(f"   📥 Baixado: {os.path.basename(nome_arquivo)}", Fore.CYAN)
                time.sleep(1)

            except Exception as e:
                log(f"   ⚠️ Erro ao baixar msg {id_msg}: {e}", Fore.YELLOW)
                page.keyboard.press("Escape")
                time.sleep(0.5)

    except Exception as e:
        log(f"   ❌ Erro ao processar grupo '{nome_grupo}': {e}", Fore.RED)

    return cupons


def enviar_confirmacao_whatsapp(page, nome_grupo: str, mensagem: str):
    """Envia uma mensagem de texto no grupo do WhatsApp."""
    try:
        campo_busca = page.locator('input[data-tab="3"], div[contenteditable="true"][data-tab="3"]').first
        campo_busca.click()
        time.sleep(0.3)
        campo_busca.fill("")
        campo_busca.type(nome_grupo, delay=60)
        time.sleep(1.5)

        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        if resultado.count() == 0:
            return

        resultado.click()
        time.sleep(1.5)

        campo_texto = page.locator('div[contenteditable="true"][data-tab="10"]').first
        campo_texto.click()
        time.sleep(0.3)
        campo_texto.type(mensagem, delay=20)
        time.sleep(0.3)
        page.keyboard.press("Enter")
        time.sleep(0.5)
        log(f"   📤 Confirmação enviada em '{nome_grupo}'", Fore.GREEN)

    except Exception as e:
        log(f"   ⚠️ Falha ao enviar confirmação: {e}", Fore.YELLOW)


# =============================================================
# LOOP PRINCIPAL
# =============================================================

def executar_ciclo():
    print(Fore.BLUE + Style.BRIGHT + "\n" + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + f"   🚀 ROBÔ ABASTECIMENTO — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65 + "\n")

    # Agência Matriz da Norte Nordeste = id 2 (confirmado via API)
    EMPRESAS_ID = os.environ.get("BSOFT_EMPRESA_ID", "2")

    ids_processados = carregar_ids_processados()
    api = BsoftAPI()

    todos_cupons     = []
    lancamentos_ok   = 0
    lancamentos_erro = 0

    # ── 1. WhatsApp: coleta cupons ─────────────────────────────
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PASTA_SESSAO_WA,
            headless=True,
            viewport={"width": 1280, "height": 720},
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
            time.sleep(3)

            for codigo, nome_grupo in GRUPOS_FROTA.items():
                log(f"\n📱 Processando grupo: {nome_grupo}", Fore.YELLOW)
                cupons = coletar_cupons_grupo(page, nome_grupo, ids_processados)
                for c in cupons:
                    c["codigo_grupo"] = codigo
                todos_cupons.extend(cupons)

        except Exception as e:
            log(f"❌ Erro crítico no WhatsApp: {e}", Fore.RED)
        finally:
            browser.close()

    log(f"\n📋 Total de cupons para processar: {len(todos_cupons)}", Fore.CYAN)

    # ── 2. Para cada cupom: extrai → busca → lança ─────────────
    for cupom in todos_cupons:
        arquivo  = cupom["arquivo"]
        grupo    = cupom["grupo"]
        id_msg   = cupom["id_msg"]

        log(f"\n🔍 Processando: {os.path.basename(arquivo)} ({grupo})", Fore.YELLOW)

        entrada_log = {
            "id_msg":       id_msg,
            "grupo":        grupo,
            "arquivo":      os.path.basename(arquivo),
            "timestamp_wa": cupom.get("timestamp", ""),
            "remetente":    cupom.get("remetente", ""),
            "processado_em": datetime.now().isoformat(),
            "dados_gemini": None,
            "equipamento_id": None,
            "fornecedor_id":  None,
            "combustivel_id": None,
            "motorista_id":   None,
            "resultado_bsoft": None,
            "status": "ERRO",
            "erro": "",
        }

        try:
            # 2a. Gemini Vision
            log("   🤖 Extraindo dados com Gemini...", Fore.WHITE)
            dados = extrair_dados_cupom_gemini(arquivo)

            if not dados:
                entrada_log["erro"] = "Gemini não conseguiu extrair dados."
                salvar_log(entrada_log)
                lancamentos_erro += 1
                continue

            log(f"   📄 Dados: placa={dados.get('placa')} | litros={dados.get('litros')} | total={dados.get('valor_total')}", Fore.CYAN)
            entrada_log["dados_gemini"] = dados

            # 2b. Valida campos mínimos
            if not dados.get("placa") or not dados.get("litros") or not dados.get("valor_total"):
                entrada_log["erro"] = f"Dados incompletos: placa={dados.get('placa')} litros={dados.get('litros')} total={dados.get('valor_total')}"
                salvar_log(entrada_log)
                lancamentos_erro += 1
                continue

            # 2c. Busca equipamento pela placa
            equip_id = buscar_equipamento_por_placa(api, dados["placa"])
            if not equip_id:
                entrada_log["erro"] = f"Equipamento não encontrado para placa {dados.get('placa')}"
                salvar_log(entrada_log)
                lancamentos_erro += 1
                continue
            entrada_log["equipamento_id"] = equip_id

            # 2d. Busca fornecedor pelo CNPJ
            forn_id = None
            if dados.get("posto_cnpj"):
                forn_id = buscar_fornecedor_por_cnpj(api, dados["posto_cnpj"])
            if not forn_id:
                entrada_log["erro"] = f"Fornecedor não encontrado para CNPJ {dados.get('posto_cnpj')}"
                salvar_log(entrada_log)
                lancamentos_erro += 1
                continue
            entrada_log["fornecedor_id"] = forn_id

            # 2e. Busca combustível
            comb_id = buscar_combustivel_id(api, dados.get("combustivel", ""))
            if not comb_id:
                entrada_log["erro"] = f"Combustível não encontrado: {dados.get('combustivel')}"
                salvar_log(entrada_log)
                lancamentos_erro += 1
                continue
            entrada_log["combustivel_id"] = comb_id

            # 2f. Motorista via planilha (opcional — não bloqueia)
            motor_id = None
            if dados.get("data") and dados.get("placa"):
                motor_id = buscar_motorista_planilha(dados["placa"], dados["data"])
            entrada_log["motorista_id"] = motor_id

            # 2g. POST Bsoft
            dados["grupo_frota"] = cupom.get("grupo", "")
            log("   📤 Lançando na Bsoft...", Fore.WHITE)
            resultado = lancar_abastecimento(
                api, dados, equip_id, forn_id, comb_id, motor_id, EMPRESAS_ID
            )
            entrada_log["resultado_bsoft"] = resultado

            if resultado and (resultado.get("id") or resultado.get("success") or resultado.get("raw")):
                entrada_log["status"] = "OK"
                lancamentos_ok += 1
                log(f"   ✅ Lançado! Resultado: {resultado}", Fore.GREEN)
                ids_processados.add(id_msg)

                # Confirmação no WhatsApp
                msg_confirmacao = (
                    f"✅ *Abastecimento registrado na Bsoft!*\n"
                    f"🚛 Placa: {dados.get('placa', '-')}\n"
                    f"⛽ Combustível: {dados.get('combustivel', '-')}\n"
                    f"💧 Litros: {dados.get('litros', '-')}\n"
                    f"💰 Valor: {formatar_moeda(dados.get('valor_total', 0))}\n"
                    f"📅 Data: {dados.get('data', '-')}\n"
                    f"🏪 Posto: {dados.get('posto_nome', '-')}"
                )
                # Reabre WA só para enviar confirmação (rápido)
                _enviar_msg_wa(grupo, msg_confirmacao)
            else:
                entrada_log["status"] = "ERRO"
                entrada_log["erro"]   = f"Bsoft retornou: {resultado}"
                lancamentos_erro += 1
                log(f"   ❌ Falha no lançamento: {resultado}", Fore.RED)

        except Exception as e:
            entrada_log["erro"] = str(e)
            lancamentos_erro += 1
            log(f"   ❌ Exceção: {e}", Fore.RED)

        salvar_log(entrada_log)

    # Salva IDs processados para não repetir
    salvar_ids_processados(ids_processados)

    # Relatório final
    print(Fore.BLUE + "\n" + "=" * 65)
    print(Fore.GREEN  + f"  ✅ Lançamentos OK   : {lancamentos_ok}")
    print(Fore.RED    + f"  ❌ Lançamentos Erro : {lancamentos_erro}")
    print(Fore.CYAN   + f"  📋 Cupons coletados : {len(todos_cupons)}")
    print(Fore.BLUE   + "=" * 65)


def _enviar_msg_wa(nome_grupo: str, mensagem: str):
    """Abre uma sessão rápida do WA só para enviar uma mensagem."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=PASTA_SESSAO_WA,
                headless=True,
                viewport={"width": 1280, "height": 720},
            )
            page = browser.new_page()
            page.goto("https://web.whatsapp.com/", timeout=30000)
            page.wait_for_selector(
                'input[data-tab="3"], div[contenteditable="true"][data-tab="3"]',
                timeout=30000
            )
            time.sleep(2)
            enviar_confirmacao_whatsapp(page, nome_grupo, mensagem)
            browser.close()
    except Exception as e:
        log(f"   ⚠️ Não foi possível enviar confirmação WA: {e}", Fore.YELLOW)


# =============================================================
# AGENDAMENTO
# =============================================================

def main():
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + "   ROBÔ DE ABASTECIMENTO — AGENDADOR")
    print(Fore.BLUE + Style.BRIGHT + "   Execuções: 08:00 e 20:00")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)

    schedule.every().day.at("08:00").do(executar_ciclo)
    schedule.every().day.at("20:00").do(executar_ciclo)

    log("✅ Agendador iniciado. Aguardando próxima execução...", Fore.GREEN)
    log(f"   Próximas: {schedule.next_run()}", Fore.CYAN)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import sys
    if "--agora" in sys.argv:
        # Executa imediatamente (para teste)
        executar_ciclo()
    else:
        main()