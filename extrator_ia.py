import os
from google import genai
from google.genai import types
import json
import re
import time
from config import LISTA_CHAVES_GEMINI, COLUNAS

MODELOS_CACHEADOS = {}

def listar_modelo_disponivel(client, chave):
    global MODELOS_CACHEADOS
    if chave in MODELOS_CACHEADOS:
        return MODELOS_CACHEADOS[chave]
    try:
        models = client.models.list()
        for m in models:
            nome = m.name.lower()
            if '2.5-flash' in nome and 'vision' not in nome and '8b' not in nome:
                MODELOS_CACHEADOS[chave] = m.name.split('/')[-1]
                return MODELOS_CACHEADOS[chave]
        for m in models:
            nome = m.name.lower()
            if 'flash' in nome and 'vision' not in nome and '8b' not in nome:
                MODELOS_CACHEADOS[chave] = m.name.split('/')[-1]
                return MODELOS_CACHEADOS[chave]
    except:
        pass
    return "gemini-1.5-flash"

def padronizar_valores(dados):
    mapeamento_padroes = {
        "CLIENTE": "CLIENTES",
        "VALOR": "VALOR DA NF",
        "PESO": "PESO DA MERCADORIA KG",
        "PESO KG": "PESO DA MERCADORIA KG",
        "NF": "NOTAS FISCAIS",
        "NOTA FISCAL": "NOTAS FISCAIS",
        "NAVIO": "NAVIO/VIAGEM ARMADOR",
        "VIAGEM": "NAVIO/VIAGEM ARMADOR",
    }
    
    dados_padronizados = {}
    for chave_esperada in COLUNAS:
        dados_padronizados[chave_esperada] = ""

    for chave, valor in dados.items():
        chave_upper = chave.upper().strip()
        chave_final = mapeamento_padroes.get(chave_upper, chave_upper)
        if chave_final in COLUNAS:
            if isinstance(valor, str):
                dados_padronizados[chave_final] = valor.strip().upper()
            else:
                dados_padronizados[chave_final] = str(valor).upper() if valor is not None else ""
                
    return dados_padronizados

def normalizar_item(item):
    for k, v in item.items():
        if isinstance(v, list):
            item[k] = ", ".join([str(x) for x in v if x])
    return item

def limpeza_seguranca(texto_original, dados_extraidos):
    if dados_extraidos.get("CONTAINER"):
        cont = str(dados_extraidos["CONTAINER"]).replace(" ", "").replace("-", "")
        if not re.match(r'^[A-Z]{4}\d{7}$', cont):
            dados_extraidos["CONTAINER"] = ""
            match_real = re.search(r'[A-Z]{4}\s*-?\s*\d{7}', texto_original)
            if match_real:
                dados_extraidos["CONTAINER"] = match_real.group(0).replace(" ", "").replace("-", "")
    
    if dados_extraidos.get("VALOR DA NF"):
        v = str(dados_extraidos["VALOR DA NF"]).replace("R$", "").strip()
        if v:
            v = v.replace(".", "").replace(",", ".")
            try:
                valor_float = float(v)
                dados_extraidos["VALOR DA NF"] = f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                dados_extraidos["VALOR DA NF"] = ""
                
    return dados_extraidos

def extrair_com_ia(texto):
    if not texto or len(texto.strip()) < 10:
        return []

    _indice_chave_atual = 0

    while _indice_chave_atual < len(LISTA_CHAVES_GEMINI):
        chave_atual = LISTA_CHAVES_GEMINI[_indice_chave_atual]
        client = genai.Client(api_key=chave_atual)
        modelo_escolhido = listar_modelo_disponivel(client, chave_atual)

        prompt = f"""
        Você é um assistente de logística portuária. Extraia os seguintes campos do documento:
        - CLIENTES (Nome da empresa destino/recebedor)
        - DESTINO (Cidade/Estado destino)
        - BOOKING
        - NAVIO/VIAGEM ARMADOR
        - VALOR DA NF (Apenas números)
        - PESO DA MERCADORIA KG
        - NOTAS FISCAIS
        - CT-E ARMADOR
        - CONTAINER (Exatamente 4 Letras e 7 Números. Ex: MEDU1234567)
        - TIPO
        - LACRE
        - DATA DE EMBARQUE
        - DEADLINE

        IMPORTANTE:
        Se houver MULTIPLOS CONTÊINERES no mesmo documento (ex: um packing list ou CTe com 2 ou mais contêineres listados), 
        você DEVE criar uma lista JSON com múltiplos objetos. Faça um objeto para CADA contêiner encontrado.

        Retorne APENAS um JSON puro (objeto único ou lista de objetos). Não use markdown.
        Documento:
        {texto}
        """

        try:
            response = client.models.generate_content(
                model=modelo_escolhido,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )

            raw = response.text.strip()
            raw = re.sub(r'^```json\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\s*```$', '', raw)

            parsed = json.loads(raw)

            if isinstance(parsed, dict):
                lista = [normalizar_item(parsed)]
            elif isinstance(parsed, list):
                lista = [normalizar_item(item) for item in parsed if isinstance(item, dict)]
            else:
                continue

            lista_final = []
            for item in lista:
                item = padronizar_valores(item)
                item = limpeza_seguranca(texto, item)
                lista_final.append(item)

            if lista_final:
                if len(lista_final) > 1:
                    print(f"    🔀 Multi-contêiner detectado pela IA: {len(lista_final)} contêineres")
                return lista_final

        except Exception as e:
            erro_str = str(e).upper()
            erros_temporarios = ["429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "OVERLOAD", "INTERNAL"]
            if any(termo in erro_str for termo in erros_temporarios):
                print(f"   🔄 Chave API {_indice_chave_atual + 1} sobrecarregada/erro. Trocando de chave...")
                _indice_chave_atual += 1
                time.sleep(2)
            else:
                print(f"   ❌ Erro do Gemini: {e}")
                return []
                
    print("   ❌ Todas as chaves da API falharam ou estão sobrecarregadas.")
    return []