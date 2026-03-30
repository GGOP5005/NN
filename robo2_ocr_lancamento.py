"""
robo2_ocr_lancamento.py
========================
Responsabilidade: processar imagens já baixadas pelo Robô 1.
  1. Aciona robo1 para baixar fotos novas
  2. Lê arquivos .jpg/.png da pasta cupons_abastecimento/
  3. OCR com Tesseract (caminho Windows fixo) + contraste 2x
  4. Se OCR fraco → Gemini Vision
  5. Lança na Bsoft
  6. Limpa arquivos processados

Agenda: 08:00 e 20:00
"""

import os
import sys
import json
import time
import re
import hashlib
import schedule
import unicodedata
from datetime import datetime, date
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BASE_DIR, LISTA_CHAVES_GEMINI
from api_bsoft import BsoftAPI

# Caminho fixo do Tesseract no Windows
TESSERACT_CMD = r"C:\Users\supor\Dropbox\DIVERSOS\IA\tesseract\tesseract.exe"

PASTA_CUPONS     = os.path.join(BASE_DIR, "cupons_abastecimento")
PASTA_LOGS       = os.path.join(BASE_DIR, "logs", "abastecimento")
ARQUIVO_IDS_PROC = os.path.join(BASE_DIR, "logs", "abastecimento", "ids_processados.json")

# Importa funções do robô original
from robo_abastecimento import (
    _listar_modelo_disponivel,
    buscar_equipamento_por_placa,
    buscar_fornecedor_por_cnpj,
    buscar_fornecedor_por_nome,
    buscar_combustivel_id,
    buscar_motorista_planilha,
    buscar_motorista_id_por_nome,
    buscar_motorista_id_por_cpf,
    lancar_abastecimento,
    salvar_log,
    formatar_moeda,
    _extrair_via_visao,
)

EMPRESAS_ID = os.environ.get("BSOFT_EMPRESA_ID", "2")
ANO_ATUAL   = datetime.now().year


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


# ── OCR ────────────────────────────────────────────────────────────────────

def ocr_tesseract(caminho: str) -> str:
    """
    OCR com Tesseract.
    - Upscale 2x para melhorar leitura de cupons térmicos
    - Contraste 2x para escurecer o texto e ajudar a distinguir '6' de '0'
    """
    try:
        import pytesseract
        from PIL import Image, ImageEnhance

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        img = Image.open(caminho).convert("L")  # Escala de cinza
        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(2.0)  # Dobra o contraste

        texto = pytesseract.image_to_string(img, lang="por")
        return texto.strip()
    except Exception as e:
        log(f"   ⚠️ Tesseract erro: {e}", Fore.YELLOW)
        return ""


def texto_parece_cupom(texto: str) -> bool:
    txt = texto.upper()
    hits = sum(1 for k in ["CNPJ", "LITROS", "DIESEL", "GASOLINA",
                            "COMBUSTIVEL", "NFE", "CUPOM", "ABASTEC"] if k in txt)
    return hits >= 2


PROMPT_PARSE = f"""Extraia dados deste cupom fiscal (texto OCR).
Retorne APENAS JSON sem markdown, sem explicações.
Se não for cupom de abastecimento, retorne todos campos vazios.

ATENÇÃO: Estamos no ano de {ANO_ATUAL}. O OCR frequentemente confunde o dígito '6' com '0' ou '8'
em impressoras de papel térmico. Se a data do documento parecer ser "2020", "2021", "2022",
"2023", "2025", "2028" ou "2029", CORRIJA o ano automaticamente para "{ANO_ATUAL}".

{{
  "posto_nome": "",
  "posto_cnpj": "somente digitos",
  "posto_cidade": "",
  "posto_uf": "",
  "data": "YYYY-MM-DD",
  "hora": "HH:MM:SS",
  "combustivel": "",
  "litros": "decimal com ponto",
  "valor_unitario": "decimal com ponto",
  "valor_total": "decimal com ponto",
  "placa": "formato original",
  "motorista": "",
  "motorista_cpf": "somente digitos",
  "km_atual": "inteiro",
  "numero_cupom": "",
  "chave_acesso": "44 digitos se houver"
}}

TEXTO OCR:
"""


def parse_texto_com_gemini(texto_ocr: str) -> dict | None:
    """Usa Gemini (modo texto) para estruturar o OCR em JSON. Barato e rápido."""
    from google import genai
    for chave in LISTA_CHAVES_GEMINI:
        try:
            client  = genai.Client(api_key=chave)
            modelo  = _listar_modelo_disponivel(client, chave)
            log(f"   🤖 Gemini texto: {modelo}", Fore.WHITE)
            r = client.models.generate_content(
                model=modelo,
                contents=[PROMPT_PARSE + texto_ocr]
            )
            txt = re.sub(r"```(?:json)?", "", r.text.strip()).strip().rstrip("`")
            return json.loads(txt)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
    return None


def corrigir_ano(dados: dict) -> dict:
    """
    Camada 3 de proteção: força correção do ano se OCR/IA ainda errou.
    Substitui anos impossíveis (2020, 2021, 2022, 2023, 2025, 2028, 2029) pelo ano atual.
    """
    data_str = dados.get("data", "")
    if data_str and len(data_str) >= 4:
        ano_str = data_str[:4]
        anos_errados = {"2020", "2021", "2022", "2023", "2025", "2028", "2029"}
        if ano_str in anos_errados:
            dados["data"] = str(ANO_ATUAL) + data_str[4:]
            log(f"   🔧 Ano corrigido: {ano_str} → {ANO_ATUAL}", Fore.YELLOW)
    return dados


def extrair_dados(caminho: str) -> dict | None:
    """
    Pipeline de extração com 3 camadas anti-erro de OCR:
    1. Tesseract (local, grátis) com contraste 2x
    2. Gemini texto com prompt instruindo correção de ano
    3. Gemini Vision como fallback final
    """
    log(f"   🔍 OCR Tesseract...", Fore.WHITE)
    texto = ocr_tesseract(caminho)

    if texto and texto_parece_cupom(texto):
        log(f"   📝 OCR ok ({len(texto)} chars) — parseando com Gemini texto...", Fore.WHITE)
        dados = parse_texto_com_gemini(texto)
        if dados and dados.get("placa") and dados.get("litros"):
            return corrigir_ano(dados)
        log(f"   ⚠️ Parse texto insuficiente — usando Gemini Vision...", Fore.YELLOW)
    else:
        log(f"   👁️ OCR fraco — usando Gemini Vision...", Fore.WHITE)

    dados = _extrair_via_visao(caminho)
    if dados:
        dados = corrigir_ano(dados)
    return dados


# ── LIMPEZA ────────────────────────────────────────────────────────────────

def limpar_pasta(ids_processados: set):
    """Remove imagens já processadas ou corrompidas da pasta de cupons."""
    if not os.path.exists(PASTA_CUPONS):
        return

    removidos = 0
    for f in Path(PASTA_CUPONS).glob("cupom_*"):
        try:
            if f.suffix in ('.jpg', '.png', '.jpeg', '.webp') and f.stat().st_size < 5000:
                f.unlink()
                removidos += 1
                continue

            if f.suffix in ('.jpg', '.png', '.jpeg', '.webp'):
                meta_path = f.with_suffix('.json')
                if meta_path.exists():
                    with open(meta_path, 'r', encoding='utf-8') as mf:
                        meta = json.load(mf)
                    if meta.get('processado'):
                        f.unlink()
                        meta_path.unlink()
                        removidos += 1
                else:
                    hash_arq = hashlib.md5(f.read_bytes()).hexdigest()
                    if hash_arq in ids_processados:
                        f.unlink()
                        removidos += 1
        except Exception:
            pass

    if removidos:
        log(f"   🧹 Limpeza: {removidos} arquivo(s) removido(s)", Fore.CYAN)


# ── CICLO PRINCIPAL ─────────────────────────────────────────────────────────

def executar_ciclo():
    print(Fore.BLUE + Style.BRIGHT + "\n" + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + f"   🔄 ROBÔ 2 OCR+LANÇAMENTO — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65 + "\n")

    # Aciona o Robô 1 para baixar fotos novas
    log("📲 Acionando Robô 1 para baixar novas fotos...", Fore.YELLOW)
    try:
        import robo1_downloader_wa as r1
        r1.executar()
    except Exception as e:
        log(f"   ⚠️ Robô 1 falhou: {e}", Fore.YELLOW)

    ids_processados = carregar_ids_processados()
    api = BsoftAPI()
    ok = erro = 0

    # Lista arquivos pendentes (JSON com processado=False)
    pendentes = []
    if os.path.exists(PASTA_CUPONS):
        for meta_path in sorted(Path(PASTA_CUPONS).glob("cupom_*.json")):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                if not meta.get('processado'):
                    img_path = meta_path.parent / meta['arquivo']
                    if img_path.exists():
                        pendentes.append((meta_path, meta, img_path))
            except Exception:
                pass

    log(f"📋 {len(pendentes)} cupom(ns) pendente(s) para processar.", Fore.CYAN)

    for meta_path, meta, img_path in pendentes:
        arquivo = str(img_path)
        grupo   = meta.get('grupo', '')
        id_msg  = meta.get('id_msg', '')

        log(f"\n🔍 {img_path.name} ({grupo})", Fore.YELLOW)

        entrada_log = {
            "id_msg": id_msg, "grupo": grupo,
            "arquivo": img_path.name,
            "processado_em": datetime.now().isoformat(),
            "dados_ocr": None, "equipamento_id": None,
            "fornecedor_id": None, "combustivel_id": None,
            "motorista_id": None, "resultado_bsoft": None,
            "status": "ERRO", "erro": "",
        }

        try:
            dados = extrair_dados(arquivo)
            if not dados:
                entrada_log["erro"] = "Extração falhou (Gemini e OCR)"
                salvar_log(entrada_log)
                meta['processado'] = True
                meta['erro'] = 'extracao_falhou'
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False)
                erro += 1
                continue

            entrada_log["dados_ocr"] = dados
            log(f"   placa={dados.get('placa')} | litros={dados.get('litros')} | total={dados.get('valor_total')} | data={dados.get('data')}", Fore.CYAN)

            # Filtra cupons incompletos (fotos de hodômetro, etc.)
            if not dados.get("placa") or not dados.get("litros") or not dados.get("valor_total"):
                entrada_log["erro"] = "Dados incompletos"
                salvar_log(entrada_log)
                hash_arq = hashlib.md5(open(arquivo, 'rb').read()).hexdigest()
                ids_processados.add(hash_arq)
                ids_processados.add(id_msg)
                meta['processado'] = True
                meta['erro'] = 'dados_incompletos'
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False)
                erro += 1
                continue

            # Filtra cupons velhos (> 80h)
            if dados.get("data"):
                try:
                    data_cupom = datetime.strptime(dados["data"], "%Y-%m-%d")
                    diff_h = (datetime.now() - data_cupom).total_seconds() / 3600
                    if diff_h > 80:
                        log(f"   🗓️ Cupom antigo ({dados['data']}, {diff_h:.0f}h) — ignorado.", Fore.YELLOW)
                        meta['processado'] = True
                        meta['erro'] = f'cupom_antigo_{dados["data"]}'
                        with open(meta_path, 'w', encoding='utf-8') as f:
                            json.dump(meta, f, ensure_ascii=False)
                        ids_processados.add(id_msg)
                        erro += 1
                        continue
                except Exception:
                    pass

            # Busca IDs Bsoft
            equip_id = buscar_equipamento_por_placa(api, dados["placa"])
            if not equip_id:
                entrada_log["erro"] = f"Placa {dados['placa']} não encontrada"
                salvar_log(entrada_log)
                erro += 1
                continue
            entrada_log["equipamento_id"] = equip_id

            forn_id = None
            if dados.get("posto_cnpj"):
                forn_id = buscar_fornecedor_por_cnpj(api, dados["posto_cnpj"], dados.get("posto_nome", ""))
            if not forn_id and dados.get("posto_nome"):
                forn_id = buscar_fornecedor_por_nome(api, dados["posto_nome"], dados.get("posto_cnpj", ""))
            if not forn_id:
                entrada_log["erro"] = "Fornecedor não encontrado"
                salvar_log(entrada_log)
                erro += 1
                continue
            entrada_log["fornecedor_id"] = forn_id

            comb_id = buscar_combustivel_id(api, dados.get("combustivel", ""))
            if not comb_id:
                entrada_log["erro"] = "Combustível não encontrado"
                salvar_log(entrada_log)
                erro += 1
                continue
            entrada_log["combustivel_id"] = comb_id

            motor_id = None
            if dados.get("motorista_cpf"):
                motor_id = buscar_motorista_id_por_cpf(api, dados["motorista_cpf"])
            if not motor_id and dados.get("data") and dados.get("placa"):
                nome_mot = buscar_motorista_planilha(dados["placa"], dados["data"])
                if nome_mot:
                    motor_id = buscar_motorista_id_por_nome(api, nome_mot)
            if not motor_id and dados.get("motorista"):
                motor_id = buscar_motorista_id_por_nome(api, dados["motorista"])
            entrada_log["motorista_id"] = motor_id

            # Lança na Bsoft
            dados["grupo_frota"] = grupo
            resultado = lancar_abastecimento(api, dados, equip_id, forn_id, comb_id, motor_id, EMPRESAS_ID)
            entrada_log["resultado_bsoft"] = resultado

            if resultado and (resultado.get("id") or resultado.get("codAbastecimento") or resultado.get("success")):
                entrada_log["status"] = "OK"
                ok += 1
                ids_processados.add(id_msg)
                meta['processado'] = True
                meta['bsoft_id'] = resultado.get("id") or resultado.get("codAbastecimento")
                log(f"   ✅ Lançado! {resultado}", Fore.GREEN)
            else:
                entrada_log["status"] = "ERRO"
                entrada_log["erro"] = str(resultado)
                erro += 1
                log(f"   ❌ Falha: {resultado}", Fore.RED)

        except Exception as e:
            entrada_log["erro"] = str(e)
            erro += 1
            log(f"   ❌ Exceção: {e}", Fore.RED)

        salvar_log(entrada_log)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)

    salvar_ids_processados(ids_processados)
    limpar_pasta(ids_processados)

    print(Fore.BLUE + "\n" + "=" * 65)
    print(Fore.GREEN + f"  ✅ OK    : {ok}")
    print(Fore.RED   + f"  ❌ Erro  : {erro}")
    print(Fore.BLUE  + "=" * 65)


def main():
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + "   ROBÔ 2 — OCR + LANÇAMENTO BSOFT")
    print(Fore.BLUE + Style.BRIGHT + "   Execuções: 08:00 e 20:00")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)

    schedule.every().day.at("08:00").do(executar_ciclo)
    schedule.every().day.at("20:00").do(executar_ciclo)

    log("✅ Agendador iniciado.", Fore.GREEN)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--agora" in sys.argv:
        executar_ciclo()
    else:
        main()