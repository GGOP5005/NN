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
from datetime import datetime, date, timedelta
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

EMPRESAS_ID_DEFAULT = os.environ.get("BSOFT_EMPRESA_ID", "2")

# =============================================================
# CONFIGURAÇÕES
# =============================================================

# Grupos WhatsApp da frota (nome exato como aparece no WhatsApp)
GRUPOS_FROTA = {
    "001": "Abastecimento 001",
    "002": "Abastecimento 002",
    "003": "Abastecimento 003",
    "005": "Abastecimento 005",
    "006": "Abastecimento 006",
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
_cache_motoristas_id: dict = {
    # IDs confirmados via API (registros antigos não retornados na lista)
    "DJOHN BATISTA DOS SANTOS":    "1645",
    "DAYVSON ARAUJO DE BRITO":     "845",
    "JOSE JERONIMO DA SILVA":      "1078",
    "BRUNO DE LIMA FERREIRA":      "79",
}

# Mapa equipamentos_id → cod_rateio (Apropriação na Bsoft)
_MAPA_COD_RATEIO = {
    "2":  "20",  # KUZ-4E30/PE
    "10": "32",  # NIG-0F83/PI
    "9":  "31",  # PPR-2G32/PE
    "7":  "28",  # AZN-8C49/PE
    "5":  "23",  # QCA-3B07/PE
}

# Mapa de mês → nome da aba na planilha de cargas
ABAS_MESES = {
    1: 'JANEIRO', 2: 'FEVEREIRO', 3: 'MARÇO', 4: 'ABRIL',
    5: 'MAIO', 6: 'JUNHO', 7: 'JULHO', 8: 'AGOSTO',
    9: 'SETEMBRO', 10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO'
}


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
    try:
        os.makedirs(os.path.dirname(ARQUIVO_IDS_PROC), exist_ok=True)
        with open(ARQUIVO_IDS_PROC, "w", encoding="utf-8") as f:
            json.dump(list(ids), f)
        log(f"   💾 Cache salvo: {ARQUIVO_IDS_PROC} ({len(ids)} entradas)", Fore.CYAN)
    except Exception as e:
        log(f"   ❌ Erro ao salvar cache de IDs: {e}", Fore.RED)
        log(f"      Caminho: {ARQUIVO_IDS_PROC}", Fore.RED)


# =============================================================
# GEMINI VISION — EXTRAÇÃO DO CUPOM
# =============================================================

PROMPT_CUPOM = """
Você é um extrator de dados de cupons fiscais de abastecimento de combustível.
Analise a imagem e retorne APENAS um JSON com os campos abaixo.
Se um campo não estiver visível, retorne "".

ATENÇÃO:
- "placa": procure no RODAPÉ do cupom, geralmente após "Placa:" — formato AAA-0000 ou AAAA000
- "km_atual": procure após "Km:" ou "Hodômetro:" no rodapé — número inteiro sem ponto
- "motorista_cpf": procure após "CPF:" no rodapé
- Se a imagem NÃO for um cupom fiscal (ex: foto de hodômetro, display, painel), retorne todos os campos vazios exceto km_atual

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
  "placa": "Placa do veículo no formato original do cupom",
  "motorista": "Nome do motorista se aparecer",
  "motorista_cpf": "CPF do motorista somente números se aparecer",
  "km_atual": "Quilometragem como número inteiro (ex: 160194)",
  "numero_cupom": "Número do documento fiscal",
  "chave_acesso": "Chave de acesso NF-e (44 dígitos) se aparecer"
}

Retorne APENAS o JSON, sem texto adicional, sem markdown.
"""

# Cache de modelos por chave (igual ao extrator_ia.py)
_MODELOS_CACHEADOS: dict = {}


def _listar_modelo_disponivel(client, chave: str) -> str:
    """Igual ao extrator_ia.py — pega o melhor modelo disponível para a chave."""
    global _MODELOS_CACHEADOS
    if chave in _MODELOS_CACHEADOS:
        return _MODELOS_CACHEADOS[chave]
    try:
        models = client.models.list()
        # Prefere 2.5-flash
        for m in models:
            nome = m.name.lower()
            if '2.5-flash' in nome and 'vision' not in nome and '8b' not in nome:
                _MODELOS_CACHEADOS[chave] = m.name.split('/')[-1]
                return _MODELOS_CACHEADOS[chave]
        # Fallback: qualquer flash
        for m in models:
            nome = m.name.lower()
            if 'flash' in nome and 'vision' not in nome and '8b' not in nome:
                _MODELOS_CACHEADOS[chave] = m.name.split('/')[-1]
                return _MODELOS_CACHEADOS[chave]
    except Exception:
        pass
    return "gemini-1.5-flash"


def _ocr_imagem(caminho: str) -> str:
    try:
        from PIL import Image
        import pytesseract
        # Verifica se tesseract está instalado
        pytesseract.get_tesseract_version()
        img = Image.open(caminho)
        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.LANCZOS)
        return pytesseract.image_to_string(img, lang="por").strip()
    except Exception:
        return ""  # Tesseract não instalado ou falhou — vai direto pro Gemini Vision


def _texto_parece_cupom(texto: str) -> bool:
    txt = texto.upper()
    hits = sum(1 for k in ["CNPJ","LITROS","DIESEL","GASOLINA","COMBUSTIVEL","NFE","CUPOM"] if k in txt)
    return hits >= 2


_PROMPT_TEXTO = """Extraia dados deste cupom fiscal (texto OCR). Retorne APENAS JSON sem markdown:
{"posto_nome":"","posto_cnpj":"","posto_cidade":"","posto_uf":"","data":"YYYY-MM-DD",
"combustivel":"","litros":"","valor_unitario":"","valor_total":"","placa":"",
"motorista":"","motorista_cpf":"","km_atual":"","numero_cupom":"","chave_acesso":""}
TEXTO:
"""


def _extrair_via_texto(texto_ocr: str) -> dict | None:
    from google import genai
    import re, json as _j
    for chave in LISTA_CHAVES_GEMINI:
        try:
            client  = genai.Client(api_key=chave)
            models  = client.models.list()
            modelo  = _listar_modelo_disponivel(models)
            log(f"   🤖 Modo texto: {modelo}", Fore.WHITE)
            r = client.models.generate_content(model=modelo, contents=[_PROMPT_TEXTO + texto_ocr])
            txt = re.sub(r"```(?:json)?", "", r.text.strip()).strip().rstrip("`")
            return _j.loads(txt)
        except _j.JSONDecodeError:
            return None
        except Exception as e:
            if "429" in str(e): time.sleep(5)
    return None


def extrair_dados_cupom_gemini(caminho_arquivo: str) -> dict | None:
    """Tenta OCR+texto primeiro, usa visao so como fallback."""
    texto = _ocr_imagem(caminho_arquivo)
    if texto and _texto_parece_cupom(texto):
        log(f"   📝 OCR ok, modo texto", Fore.WHITE)
        res = _extrair_via_texto(texto)
        if res and res.get("placa") and res.get("litros"):
            return res
        log(f"   ⚠️ Texto insuficiente, usando visao", Fore.YELLOW)
    else:
        log(f"   👁️ OCR fraco, usando Gemini Vision", Fore.WHITE)
    return _extrair_via_visao(caminho_arquivo)


def _extrair_via_visao(caminho_arquivo: str) -> dict | None:
    """Gemini Vision para extrair dados do cupom."""
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
            client  = genai.Client(api_key=chave)
            modelo  = _listar_modelo_disponivel(client, chave)
            log(f"   🤖 Usando modelo: {modelo}", Fore.WHITE)
            resposta = client.models.generate_content(
                model=modelo,
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
            msg_e = str(e)
            log(f"   ⚠️ Chave falhou ({chave[:8]}...): {msg_e[:120]}", Fore.YELLOW)
            # Rate limit — aguarda antes de tentar próxima chave
            if "429" in msg_e or "RESOURCE_EXHAUSTED" in msg_e:
                time.sleep(5)

    return None


# =============================================================
# CACHE BSOFT — EQUIPAMENTOS / FORNECEDORES / COMBUSTÍVEIS
# =============================================================

def _similaridade_placa(p1: str, p2: str) -> int:
    """Conta quantos caracteres batem na mesma posição (para corrigir OCR)."""
    return sum(a == b for a, b in zip(p1, p2))


def buscar_equipamento_por_placa(api: BsoftAPI, placa: str) -> str | None:
    """
    Busca equipamento pelo campo 'equipamento' que vem no formato 'PLACA/UF'.
    Ex: 'KUZ-4E30/PE' → id='2'
    Faz match fuzzy para corrigir erros de OCR (ex: QCA-3007 → QCA-3B07).
    """
    placa_norm = limpar_placa(placa)
    if placa_norm in _cache_equipamentos:
        return _cache_equipamentos[placa_norm]

    equipamentos = api.get("manutencao/v1/equipamentos")
    if not equipamentos:
        return None

    lista = equipamentos if isinstance(equipamentos, list) else equipamentos.get("data", [])

    # 1. Match exato
    for eq in lista:
        campo = str(eq.get("equipamento") or "")
        placa_campo = limpar_placa(campo.split("/")[0])
        if placa_campo == placa_norm:
            eid = str(eq.get("id") or "")
            _cache_equipamentos[placa_norm] = eid
            log(f"   ✅ Equipamento: {campo} → id={eid}", Fore.GREEN)
            return eid

    # 2. Match fuzzy — tolera até 2 caracteres errados (OCR)
    melhor_score = 0
    melhor_eq    = None
    melhor_campo = ""
    for eq in lista:
        campo = str(eq.get("equipamento") or "")
        placa_campo = limpar_placa(campo.split("/")[0])
        if len(placa_campo) != len(placa_norm):
            continue
        score = _similaridade_placa(placa_norm, placa_campo)
        if score > melhor_score:
            melhor_score = score
            melhor_eq    = eq
            melhor_campo = campo

    # Aceita se diferença for de até 2 caracteres
    if melhor_eq and melhor_score >= len(placa_norm) - 2:
        eid = str(melhor_eq.get("id") or "")
        _cache_equipamentos[placa_norm] = eid
        log(f"   ✅ Equipamento (fuzzy {melhor_score}/{len(placa_norm)}): {placa} → {melhor_campo} → id={eid}", Fore.GREEN)
        return eid

    log(f"   ❌ Placa {placa} não encontrada nos equipamentos Bsoft.", Fore.RED)
    log(f"      Placas disponíveis: {[e.get('equipamento','') for e in lista]}", Fore.YELLOW)
    return None


def _cnpj_similar(c1: str, c2: str) -> int:
    """Conta dígitos iguais na mesma posição. CNPJs com 1 dígito errado retornam 13."""
    return sum(a == b for a, b in zip(c1, c2))


def buscar_fornecedor_por_cnpj(api: BsoftAPI, cnpj: str, nome_posto: str = "") -> str | None:
    cnpj_norm = limpar_cnpj(cnpj)
    if cnpj_norm in _cache_fornecedores:
        return _cache_fornecedores[cnpj_norm]

    resultado = api.get("pessoas/v1/pessoas/juridicas", params={"cnpj": cnpj_norm, "ini": 0, "fim": 10}, paginar=False)
    lista = resultado if isinstance(resultado, list) else (resultado or {}).get("data", [])

    # 1. Match exato
    for pessoa in lista:
        cnpj_pessoa = limpar_cnpj(pessoa.get("cnpj") or "")
        if cnpj_pessoa == cnpj_norm:
            fid = str(pessoa.get("id") or pessoa.get("codPessoa") or "")
            _cache_fornecedores[cnpj_norm] = fid
            log(f"   ✅ Fornecedor CNPJ exato: {cnpj} → id={fid}", Fore.GREEN)
            return fid

    # 2. Fuzzy CNPJ — testa variações do CNPJ trocando 1 dígito por vez
    # (A API Bsoft não filtra por nome, só por CNPJ exato)
    log(f"   🔍 Testando variações do CNPJ {cnpj_norm}...", Fore.YELLOW)
    for pos in range(len(cnpj_norm)):
        digito_original = cnpj_norm[pos]
        for d in '0123456789':
            if d == digito_original:
                continue
            cnpj_var = cnpj_norm[:pos] + d + cnpj_norm[pos+1:]
            res_var = api.get("pessoas/v1/pessoas/juridicas",
                              params={"cnpj": cnpj_var, "ini": 0, "fim": 5},
                              paginar=False)
            lista_var = res_var if isinstance(res_var, list) else (res_var or {}).get("data", [])
            for pessoa in lista_var:
                cnpj_pessoa = limpar_cnpj(pessoa.get("cnpj") or "")
                if cnpj_pessoa == cnpj_var:
                    fid = str(pessoa.get("id") or pessoa.get("codPessoa") or "")
                    log(f"   ✅ CNPJ variação pos={pos} '{cnpj_var}': '{pessoa.get('razaoSocial')}' → id={fid}", Fore.GREEN)
                    _cache_fornecedores[cnpj_norm] = fid
                    _cache_fornecedores[cnpj_var]  = fid
                    return fid

    log(f"   ❌ Fornecedor CNPJ {cnpj} não encontrado.", Fore.RED)
    return None


def buscar_fornecedor_por_nome(api: BsoftAPI, nome: str, cnpj_original: str = "") -> str | None:
    """
    Fallback: busca fornecedor por nome quando CNPJ falhar (OCR pode errar 1 dígito).
    Guarda no cache com o CNPJ original para futuras buscas.
    """
    if not nome:
        return None

    nome_norm = normalizar(nome)
    IGNORAR = {'LTDA','COMERCIO','INDUSTRIA','POSTO','SERVICOS','DERIVADOS',
               'PETROLEO','COMBUSTIVEL','COMBUSTIVEIS','DE','DO','DA','E'}
    palavras = [p for p in nome_norm.split() if len(p) >= 4 and p not in IGNORAR]
    if not palavras:
        return None

    # Tenta cada palavra como termo de busca até achar
    for termo in palavras[:4]:
        log(f"   🔍 Buscando fornecedor por nome: '{termo}'...", Fore.YELLOW)
        resultado = api.get("pessoas/v1/pessoas/juridicas",
                            params={"razaoSocial": termo, "ini": 0, "fim": 20},
                            paginar=False)
        if not resultado:
            continue

        lista = resultado if isinstance(resultado, list) else resultado.get("data", [])
        for pessoa in lista:
            nome_pessoa = normalizar(pessoa.get("razaoSocial") or pessoa.get("nomeFantasia") or "")
            # Verifica se pelo menos 2 palavras do nome batem
            batem = sum(1 for p in palavras[:3] if p in nome_pessoa)
            if batem >= 2:
                fid = str(pessoa.get("id") or pessoa.get("codPessoa") or "")
                cnpj_bsoft = limpar_cnpj(pessoa.get("cnpj") or "")
                log(f"   ✅ Fornecedor por nome: '{pessoa.get('razaoSocial')}' → id={fid}", Fore.GREEN)
                if cnpj_original:
                    _cache_fornecedores[limpar_cnpj(cnpj_original)] = fid
                if cnpj_bsoft:
                    _cache_fornecedores[cnpj_bsoft] = fid
                return fid

    log(f"   ❌ Fornecedor '{nome}' não encontrado por nome.", Fore.RED)
    return None


# Mapa fixo baseado nos combustíveis reais da Bsoft (confirmado via API)
_MAPA_COMBUSTIVEIS = {
    "DIESEL S-10": "2",
    "DIESEL S10":  "2",
    "S10":         "2",
    "S-10":        "2",
    "GASOLINA":    "4",
    "ETANOL":      "3",
    "DIESEL":      "1",  # genérico — deve ficar por último
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

def buscar_motorista_id_por_cpf(api: BsoftAPI, cpf: str) -> str | None:
    """Busca o ID do motorista na Bsoft pelo CPF."""
    cpf_norm = ''.join(filter(str.isdigit, cpf or ''))
    if not cpf_norm or len(cpf_norm) < 11:
        return None
    if cpf_norm in _cache_motoristas_id:
        return _cache_motoristas_id[cpf_norm]
    try:
        r = api.get("pessoas/v1/pessoas/fisicas", params={"cpf": cpf_norm, "ini": 0, "fim": 5}, paginar=False)
        lista = r if isinstance(r, list) else (r or {}).get("data", [])
        for p in lista:
            if ''.join(filter(str.isdigit, p.get("cpf") or '')) == cpf_norm:
                fid = str(p.get("id") or "")
                if fid:
                    log(f"   ✅ Motorista por CPF: '{p.get('nome')}' (id={fid})", Fore.GREEN)
                    _cache_motoristas_id[cpf_norm] = fid
                    return fid
    except Exception:
        pass
    return None


def buscar_motorista_id_por_nome(api: BsoftAPI, nome: str) -> str | None:
    """Busca o ID do motorista na Bsoft pelo nome (pessoas físicas)."""
    nome_norm = normalizar(nome).strip()
    if nome_norm in _cache_motoristas_id:
        return _cache_motoristas_id[nome_norm]

    # Pega primeiro e último nome para busca
    partes = nome_norm.split()
    if not partes:
        return None

    # Tenta buscar por primeiro nome
    # A API suporta busca por ID direto: GET /pessoas/v1/pessoas/fisicas/:id
    # Mas não filtra por nome — precisa paginar e comparar localmente
    # Estratégia: tenta ids 1..200 (registros antigos) e depois os 100 mais recentes
    palavras_busca = nome_norm.split()
    primeiro_nome  = palavras_busca[0] if palavras_busca else ""

    def checar_lista(lista):
        for pessoa in lista:
            nome_pessoa = normalizar(pessoa.get("nome") or "").strip()
            palavras_pessoa = set(nome_pessoa.split())
            if primeiro_nome not in palavras_pessoa:
                continue
            intersecao = set(palavras_busca) & palavras_pessoa
            if len(intersecao) >= 2:
                fid = str(pessoa.get("id") or "")
                if fid:
                    log(f"   ✅ Motorista ID: '{nome}' → '{nome_pessoa}' (id={fid})", Fore.GREEN)
                    _cache_motoristas_id[nome_norm] = fid
                    return fid
        return None

    # Passo 1: pega os 100 mais recentes (cobre motoristas novos)
    r1 = api.get("pessoas/v1/pessoas/fisicas", params={"ini": 0, "fim": 100}, paginar=False)
    lista1 = r1 if isinstance(r1, list) else (r1 or {}).get("data", [])
    fid = checar_lista(lista1)
    if fid:
        return fid

    # Passo 2: tenta IDs antigos (1..150) para motoristas cadastrados há tempo
    ids_recentes = {str(p.get("id")) for p in lista1}
    for id_test in range(1, 151):
        if str(id_test) in ids_recentes:
            continue
        try:
            r = api.get(f"pessoas/v1/pessoas/fisicas/{id_test}", paginar=False)
            lista = r if isinstance(r, list) else ([r] if r and isinstance(r, dict) else [])
            fid = checar_lista(lista)
            if fid:
                return fid
        except Exception:
            pass

    log(f"   ⚠️ Motorista '{nome}' não encontrado na Bsoft.", Fore.YELLOW)
    return None


def buscar_motorista_planilha(placa: str, data_abastecimento: str) -> str | None:
    """
    Busca motorista na planilha de cargas pelo mês do abastecimento.
    Aba = nome do mês (MARÇO, ABRIL...) | Coluna CAVALO = placa | Coluna MOTORISTA = nome
    Retorna nome do motorista (a planilha não tem ID Bsoft).
    """
    chave = (limpar_placa(placa), data_abastecimento)
    if chave in _cache_motoristas:
        return _cache_motoristas[chave]

    try:
        # Determina a aba pelo mês da data do abastecimento
        data_obj = datetime.strptime(data_abastecimento, "%Y-%m-%d")
        aba = ABAS_MESES.get(data_obj.month)
        if not aba:
            return None

        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials

        CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
        SCOPES     = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds      = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        service    = build("sheets", "v4", credentials=creds)

        res = service.spreadsheets().values().get(
            spreadsheetId=PLANILHA_ID,
            range=f"{aba}!A:H"
        ).execute()

        linhas = res.get("values", [])
        if not linhas:
            return None

        headers = [normalizar(str(h)) for h in linhas[0]]
        idx_cavalo   = next((i for i, h in enumerate(headers) if "CAVALO" in h), 4)
        idx_motorist = next((i for i, h in enumerate(headers) if "MOTORISTA" in h), 6)

        placa_busca = limpar_placa(placa)

        for linha in linhas[1:]:
            if len(linha) <= idx_cavalo:
                continue
            placa_cell = limpar_placa(str(linha[idx_cavalo]) if idx_cavalo < len(linha) else "")
            # Match fuzzy de placa (OCR pode errar)
            if placa_cell == placa_busca or (
                len(placa_cell) == len(placa_busca) and
                sum(a == b for a, b in zip(placa_cell, placa_busca)) >= len(placa_busca) - 2
            ):
                nome = str(linha[idx_motorist]).strip() if idx_motorist < len(linha) else ""
                if nome:
                    _cache_motoristas[chave] = nome
                    log(f"   ✅ Motorista planilha ({aba}): {nome}", Fore.GREEN)
                    return nome

    except Exception as e:
        log(f"   ⚠️ Erro ao consultar planilha: {e}", Fore.YELLOW)

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
        "empresas_id":        "2",  # Matriz Norte Nordeste (fixo)
        "programado":         "N",
        "cod_rateio":         _MAPA_COD_RATEIO.get(str(equipamento_id), "0"),
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

    # Motorista — só envia se for numérico (ID Bsoft)
    if motorista_id and str(motorista_id).strip().isdigit():
        body["operadorMotorista_id"] = str(motorista_id).strip()

    # Documento fiscal — abastecimentos usam REC (Recibo) por padrão
    body["tipoDocumento_id"] = "REC"
    if dados.get("numero_cupom"):
        body["nroDoc"] = str(dados["numero_cupom"])

    # Chave de acesso NF-e
    if dados.get("chave_acesso"):
        body["chaveAcesso"] = re.sub(r"\D", "", dados["chave_acesso"])

    log(f"   📦 Body POST abastecimento: {json.dumps(body, ensure_ascii=False)}", Fore.CYAN)
    resultado = api.post("manutencao/v1/abastecimentos", body)

    # Retry sem motorista se o ID for inválido para o equipamento
    if resultado:
        msg_erro = resultado.get("message", "")
        if "operadorMotorista_id" in msg_erro and "fora do intervalo" in msg_erro:
            log("   ⚠️ Motorista fora do intervalo — relançando sem operadorMotorista_id...", Fore.YELLOW)
            body.pop("operadorMotorista_id", None)
            resultado = api.post("manutencao/v1/abastecimentos", body) or {}

    return resultado or {}


# =============================================================
# WHATSAPP — COLETA DE CUPONS
# =============================================================

def _extrair_anexo_blob(msg_node, page_ref) -> str | None:
    """Baixa imagem via hover+download button (funciona mesmo com lazy loading)."""
    os.makedirs(PASTA_CUPONS, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(PASTA_CUPONS, f"cupom_{ts}.jpg")

    try:
        msg_node.scroll_into_view_if_needed()
        time.sleep(1.0)

        # Tenta 1: blob já carregado no DOM
        srcs = msg_node.evaluate("""node => {
            return Array.from(node.querySelectorAll('img'))
                .map(img => img.src)
                .filter(src => src && src.startsWith('blob:'));
        }""")
        if srcs:
            b64 = page_ref.evaluate(f"""async () => {{
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
            if b64 and ',' in b64:
                dados = base64.b64decode(b64.split(',')[1])
                if len(dados) > 5000:
                    with open(dest, 'wb') as f:
                        f.write(dados)
                    return dest

        # Tenta 2: hover → botão download
        try:
            msg_node.hover()
            time.sleep(0.5)
            btn = msg_node.locator('span[data-icon="download"], button[aria-label*="ownload"]').first
            if btn.count() > 0 and btn.is_visible():
                with page_ref.expect_download(timeout=15000) as dl_info:
                    btn.click(force=True)
                dl = dl_info.value
                ext = os.path.splitext(dl.suggested_filename)[1] or ".jpg"
                dest2 = os.path.join(PASTA_CUPONS, f"cupom_{int(time.time())}{ext}")
                dl.save_as(dest2)
                return dest2
        except Exception:
            pass

        # Tenta 3: screenshot da área da imagem (último recurso)
        img = msg_node.locator('img').first
        if img.count() > 0:
            screenshot = img.screenshot()
            if len(screenshot) > 5000:
                with open(dest, 'wb') as f:
                    f.write(screenshot)
                return dest

        return None

    except Exception:
        return None


def coletar_cupons_grupo(page, nome_grupo: str, ids_processados: set) -> list:
    """
    Abre o grupo, rola até o fim, e baixa as últimas 7 imagens recebidas.
    Usa a mesma abordagem do despachante: locator().all() para pegar mensagens visíveis.
    """
    cupons = []

    try:
        # Abre o grupo
        busca = page.locator('input[data-tab="3"], div[contenteditable="true"][data-tab="3"]').first
        busca.click()
        time.sleep(0.5)
        busca.fill("")
        busca.type(nome_grupo, delay=50)
        time.sleep(2)

        grupo_loc = page.locator(f'span[title="{nome_grupo}"]').first
        if grupo_loc.count() == 0:
            log(f"   ⚠️ Grupo '{nome_grupo}' não encontrado.", Fore.YELLOW)
            return cupons

        grupo_loc.click()
        time.sleep(2)

        # Garante que o chat abriu
        try:
            page.wait_for_selector('div.message-in, div.message-out', timeout=5000)
        except Exception:
            grupo_loc.click(force=True)
            time.sleep(3)

        # WhatsApp já abre na última mensagem — apenas aguarda carregar
        time.sleep(1.5)

        # Pega todas as mensagens recebidas com imagem — igual ao despachante
        todas = page.locator('div.message-in').all()
        msgs_com_imagem = []
        for i, msg in enumerate(todas):
            try:
                if msg.locator('img').count() > 0:
                    data_id = msg.get_attribute('data-id') or f"noid_{i}"
                    msgs_com_imagem.append({"msg": msg, "data_id": data_id, "nth": i})
            except Exception:
                pass

        # Pega só as últimas 7
        ultimas = msgs_com_imagem[-7:]
        log(f"   📱 Grupo '{nome_grupo}': {len(msgs_com_imagem)} mídias — baixando últimas {len(ultimas)}.", Fore.CYAN)

        for item in ultimas:
            data_id = item["data_id"]
            msg     = item["msg"]

            # ID legível para noid
            if data_id.startswith("noid_"):
                grupo_slug = nome_grupo.replace(" ", "").lower()
                data_id = f"{grupo_slug}_{item['nth']:03d}"

            if data_id in ids_processados:
                log(f"   ⏭️  {data_id[:40]} já no cache", Fore.WHITE)
                continue

            arquivo = _extrair_anexo_blob(msg, page)
            if not arquivo:
                log(f"   ⚠️  blob vazio para {data_id[:30]}", Fore.YELLOW)
                continue

            tamanho = os.path.getsize(arquivo)
            if tamanho < 5000:
                os.remove(arquivo)
                continue

            hash_arq = hashlib.md5(open(arquivo, "rb").read()).hexdigest()
            if hash_arq in ids_processados:
                os.remove(arquivo)
                ids_processados.add(data_id)
                continue

            log(f"   📥 Baixado: {os.path.basename(arquivo)} ({tamanho//1024}KB)", Fore.CYAN)
            cupons.append({
                "id_msg":    data_id,
                "grupo":     nome_grupo,
                "arquivo":   arquivo,
                "timestamp": "",
                "remetente": "",
            })
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
            headless=False,
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

            # 2b. Filtra pela data do cupom (≤ 80h)
            data_cupom_str = dados.get("data", "")
            if data_cupom_str:
                try:
                    data_cupom = datetime.strptime(data_cupom_str, "%Y-%m-%d")
                    diff_h = (datetime.now() - data_cupom).total_seconds() / 3600
                    if diff_h > 80:
                        log(f"   🗓️ Cupom data={data_cupom_str} diff={diff_h:.0f}h > 80h — ignorado.", Fore.YELLOW)
                        ids_processados.add(id_msg)
                        salvar_ids_processados(ids_processados)
                        lancamentos_erro += 1
                        continue
                except Exception:
                    pass

            # 2c. Valida campos mínimos
            if not dados.get("placa") or not dados.get("litros") or not dados.get("valor_total"):
                entrada_log["erro"] = f"Dados incompletos (foto hodômetro?): placa={dados.get('placa')} litros={dados.get('litros')} total={dados.get('valor_total')}"
                salvar_log(entrada_log)
                # Salva hash e id no cache para não baixar de novo
                hash_arq = hashlib.md5(open(cupom["arquivo"], "rb").read()).hexdigest()
                ids_processados.add(hash_arq)
                ids_processados.add(id_msg)
                salvar_ids_processados(ids_processados)
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

            # 2d. Busca fornecedor pelo CNPJ, com fallback por nome
            forn_id = None
            if dados.get("posto_cnpj"):
                forn_id = buscar_fornecedor_por_cnpj(api, dados["posto_cnpj"], dados.get("posto_nome",""))
            if not forn_id and dados.get("posto_nome"):
                forn_id = buscar_fornecedor_por_nome(api, dados["posto_nome"], dados.get("posto_cnpj",""))
            if not forn_id:
                entrada_log["erro"] = f"Fornecedor não encontrado: CNPJ={dados.get('posto_cnpj')} Nome={dados.get('posto_nome')}"
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

            # 2f. Motorista — CPF do cupom → planilha → nome
            motor_id = None
            # Tenta CPF direto do cupom (mais rápido e preciso)
            if dados.get("motorista_cpf"):
                motor_id = buscar_motorista_id_por_cpf(api, dados["motorista_cpf"])
            # Tenta pela planilha (placa + data → nome → id)
            if not motor_id and dados.get("data") and dados.get("placa"):
                nome_motorista = buscar_motorista_planilha(dados["placa"], dados["data"])
                if nome_motorista:
                    motor_id = buscar_motorista_id_por_nome(api, nome_motorista)
            # Fallback: nome do cupom
            if not motor_id and dados.get("motorista"):
                motor_id = buscar_motorista_id_por_nome(api, dados["motorista"])
            entrada_log["motorista_id"] = motor_id

            # 2g. POST Bsoft
            dados["grupo_frota"] = cupom.get("grupo", "")
            log("   📤 Lançando na Bsoft...", Fore.WHITE)
            resultado = lancar_abastecimento(
                api, dados, equip_id, forn_id, comb_id, motor_id, EMPRESAS_ID
            )
            entrada_log["resultado_bsoft"] = resultado

            if resultado and (resultado.get("id") or resultado.get("success") or resultado.get("raw") or resultado.get("codAbastecimento")):
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