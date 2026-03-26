import os
import re
import json
import time
from google import genai
from google.genai import types
from config import LISTA_CHAVES_GEMINI, COLUNAS

MODELOS_CACHEADOS = {}

def listar_modelo_disponivel(client, chave):
    """Retorna o melhor modelo Gemini disponível para a chave."""
    global MODELOS_CACHEADOS
    if chave in MODELOS_CACHEADOS:
        return MODELOS_CACHEADOS[chave]
    try:
        models = list(client.models.list())
        # Preferência: 2.5-flash → 1.5-flash → 1.5-pro
        for preferido in ['2.5-flash', '1.5-flash', '1.5-pro']:
            for m in models:
                nome = m.name.lower()
                if preferido in nome and 'vision' not in nome and '8b' not in nome:
                    modelo = m.name.split('/')[-1]
                    MODELOS_CACHEADOS[chave] = modelo
                    return modelo
    except Exception as e:
        print(f"   ⚠️ Não conseguiu listar modelos: {e}")
    # Fallback seguro
    return "gemini-1.5-flash"


def padronizar_valores(dados):
    mapeamento = {
        "CLIENTE":           "CLIENTES",
        "VALOR":             "VALOR DA NF",
        "PESO":              "PESO DA MERCADORIA KG",
        "PESO KG":           "PESO DA MERCADORIA KG",
        "NF":                "NOTAS FISCAIS",
        "NOTA FISCAL":       "NOTAS FISCAIS",
        "NAVIO":             "NAVIO/VIAGEM ARMADOR",
        "VIAGEM":            "NAVIO/VIAGEM ARMADOR",
        "DATA EMBARQUE":     "DATA DE EMBARQUE",
        "EMBARQUE":          "DATA DE EMBARQUE",
    }
    resultado = {col: "" for col in COLUNAS}
    for chave, valor in dados.items():
        k = chave.upper().strip()
        k_final = mapeamento.get(k, k)
        if k_final in COLUNAS:
            resultado[k_final] = str(valor).strip().upper() if valor is not None else ""
    return resultado


def normalizar_item(item):
    """Converte listas para string separada por vírgula."""
    for k, v in item.items():
        if isinstance(v, list):
            item[k] = ", ".join([str(x) for x in v if x])
        elif v is None:
            item[k] = ""
    return item


def limpeza_seguranca(texto_original, dados):
    # Valida formato do container
    if dados.get("CONTAINER"):
        cont = re.sub(r'[\s\-]', '', str(dados["CONTAINER"]))
        if not re.match(r'^[A-Z]{4}\d{7}$', cont):
            dados["CONTAINER"] = ""
            match = re.search(r'[A-Z]{4}\s*-?\s*\d{7}', texto_original)
            if match:
                dados["CONTAINER"] = re.sub(r'[\s\-]', '', match.group(0))

    # Formata valor monetário
    if dados.get("VALOR DA NF"):
        v = re.sub(r'[R$\s]', '', str(dados["VALOR DA NF"]))
        v = v.replace(".", "").replace(",", ".") if "," in v else v
        try:
            vf = float(v)
            dados["VALOR DA NF"] = f"R$ {vf:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            dados["VALOR DA NF"] = ""

    return dados


def extrair_com_ia(texto):
    if not texto or len(texto.strip()) < 10:
        return []

    prompt = f"""
Você é um assistente de logística portuária especializado em extrair dados de documentos fiscais.

Extraia APENAS os campos abaixo do documento. Para cada campo não encontrado, use string vazia "".

Campos obrigatórios:
- CLIENTES: Nome completo da empresa destinatária/recebedora
- DESTINO: Cidade e Estado (ex: "São Paulo/SP")
- BOOKING: Número do booking/reserva
- NAVIO/VIAGEM ARMADOR: Nome do navio + número da viagem
- VALOR DA NF: Valor total em R$ (apenas números e vírgula)
- PESO DA MERCADORIA KG: Peso bruto em kg
- NOTAS FISCAIS: Números das NFs separados por vírgula
- CT-E ARMADOR: Número do CT-e do armador
- CONTAINER: Exatamente 4 letras maiúsculas + 7 dígitos (ex: MSCU1234567). Se houver múltiplos, retorne lista de objetos
- TIPO: Tipo do container (ex: 20GP, 40HC)
- LACRE: Número do lacre
- DATA DE EMBARQUE: Data no formato DD/MM/AAAA
- DEADLINE: Data limite no formato DD/MM/AAAA

REGRAS IMPORTANTES:
1. Se o documento tiver MÚLTIPLOS CONTÊINERES, retorne uma LISTA JSON com um objeto por contêiner
2. Retorne APENAS JSON puro sem markdown, sem ```json, sem explicações
3. Não invente dados — use "" para campos ausentes

Documento:
{texto[:8000]}
"""

    indice = 0
    while indice < len(LISTA_CHAVES_GEMINI):
        chave = LISTA_CHAVES_GEMINI[indice]
        try:
            client = genai.Client(api_key=chave)
            modelo = listar_modelo_disponivel(client, chave)

            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )

            raw = response.text.strip()
            # Remove blocos de código markdown se a API retornar assim mesmo
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\s*```$', '', raw)
            raw = raw.strip()

            # Tenta parsear o JSON
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as je:
                # Tenta extrair JSON da resposta mesmo com texto extra
                match = re.search(r'(\[.*\]|\{.*\})', raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(1))
                else:
                    print(f"   ⚠️ JSON inválido da IA: {je}. Raw: {raw[:200]}")
                    indice += 1
                    continue

            # Normaliza para lista
            if isinstance(parsed, dict):
                lista = [normalizar_item(parsed)]
            elif isinstance(parsed, list):
                lista = [normalizar_item(item) for item in parsed if isinstance(item, dict)]
            else:
                indice += 1
                continue

            # Padroniza e limpa
            lista_final = []
            for item in lista:
                item = padronizar_valores(item)
                item = limpeza_seguranca(texto, item)
                lista_final.append(item)

            if lista_final:
                if len(lista_final) > 1:
                    print(f"    🔀 Multi-contêiner: {len(lista_final)} detectados pela IA")
                return lista_final

        except Exception as e:
            erro = str(e).upper()
            erros_temp = ["429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "OVERLOAD", "INTERNAL"]
            if any(t in erro for t in erros_temp):
                print(f"   🔄 Chave {indice + 1} sobrecarregada. Trocando...")
                indice += 1
                time.sleep(3)
            else:
                print(f"   ❌ Erro da API Gemini: {e}")
                return []

    print("   ❌ Todas as chaves falharam ou estão sobrecarregadas.")
    return []