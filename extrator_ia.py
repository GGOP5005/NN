import os
from google import genai
from google.genai import types
import json
import re
import time
from colorama import Fore, Style
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
                val_limpo = valor.strip().upper()
                
                # === CORREÇÃO DE DESTINO DUPLICADO ===
                if chave_final == "DESTINO":
                    # Limpa padrões repetidos criados pela IA, ex: "FORTALEZA-CE, FORTALEZA" -> "FORTALEZA-CE"
                    partes = [p.strip() for p in re.split(r'[,|]', val_limpo) if p.strip()]
                    if len(partes) > 1:
                        cidade_principal = partes[0].split('-')[0].strip()
                        for p in partes[1:]:
                            if cidade_principal in p or p in cidade_principal:
                                val_limpo = partes[0] # Fica só com a primeira parte se a segunda for redundante
                                break
                    dados_padronizados[chave_final] = val_limpo
                else:
                    dados_padronizados[chave_final] = val_limpo
            else:
                dados_padronizados[chave_final] = str(valor).upper() if valor is not None else ""
                
    return dados_padronizados

def normalizar_item(item):
    for k, v in item.items():
        if isinstance(v, list):
            item[k] = ", ".join([str(x) for x in v if x])
        if isinstance(v, str):
            val = v.replace("[", "").replace("]", "").replace("'", "").replace('"', '').strip()
            if val in ["NONE", "NULL", "N/A", "UNDEFINED"]: val = ""
            if (k == "NOTAS FISCAIS" or k == "NF") and val: val = val.lstrip('0')
            item[k] = val
    return item

def limpeza_seguranca(texto_original, dados_extraidos):
    texto_upper = texto_original.upper()
    
    # 1. Validação Absoluta de Contêiner
    if dados_extraidos.get("CONTAINER"):
        cont = str(dados_extraidos["CONTAINER"]).replace(" ", "").replace("-", "")
        if not re.match(r'^[A-Z]{4}\d{7}$', cont):
            dados_extraidos["CONTAINER"] = ""
            match_real = re.search(r'[A-Z]{4}\s*-?\s*\d{7}', texto_upper)
            if match_real:
                dados_extraidos["CONTAINER"] = match_real.group(0).replace(" ", "").replace("-", "")
                
    # 2. Regra de Ouro: CT-e Nosso vs CT-e Armador
    texto_apenas_numeros = re.sub(r'[^\d]', '', texto_upper)
    nosso_cte_exportacao = "46099394000188" in texto_apenas_numeros
    
    cte_armador = str(dados_extraidos.get("CT-E ARMADOR", "")).strip()
    cte_nosso = str(dados_extraidos.get("CTE-E", "")).strip()
    
    if nosso_cte_exportacao:
        if cte_armador and not cte_nosso:
            dados_extraidos["CTE-E"] = "".join(filter(str.isdigit, cte_armador))
            dados_extraidos["CT-E ARMADOR"] = ""
            
    # 3. Formatação Segura de Valores Monetários e Pesos
    if dados_extraidos.get("VALOR DA NF"):
        v = str(dados_extraidos["VALOR DA NF"]).replace("R$", "").strip()
        if v:
            v = re.sub(r'[^\d,.]', '', v)
            if ',' in v and '.' in v: v = v.replace('.', '').replace(',', '.')
            elif ',' in v: v = v.replace(',', '.')
            try:
                valor_float = float(v)
                dados_extraidos["VALOR DA NF"] = f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                dados_extraidos["VALOR DA NF"] = ""
                
    if dados_extraidos.get("PESO DA MERCADORIA KG"):
        p = str(dados_extraidos["PESO DA MERCADORIA KG"]).strip()
        if p:
            p = re.sub(r'[^\d,.]', '', p)
            if ',' in p and '.' in p: p = p.replace('.', '').replace(',', '.')
            elif ',' in p: p = p.replace(',', '.')
            try:
                peso_float = float(p)
                dados_extraidos["PESO DA MERCADORIA KG"] = f"{peso_float:,.0f}".replace(",", ".")
            except:
                dados_extraidos["PESO DA MERCADORIA KG"] = ""
                
    return dados_extraidos

def extrair_com_ia(texto):
    if not texto or len(texto.strip()) < 10:
        return []

    prompt = f"""
    Atue como um extrator de dados logísticos RÍGIDO. Extraia dados do texto para preencher OBRIGATORIAMENTE o JSON abaixo.
    
    GABARITO JSON (Retorne EXATAMENTE esta estrutura):
    {{
      "CLIENTES": "",
      "DESTINO": "",
      "BOOKING": "",
      "NAVIO/VIAGEM ARMADOR": "",
      "VALOR DA NF": "",
      "PESO DA MERCADORIA KG": "",
      "NOTAS FISCAIS": "",
      "CT-E ARMADOR": "",
      "CTE-E": "",
      "CONTAINER": "",
      "TIPO": "",
      "LACRE": "",
      "DATA DE EMBARQUE": "",
      "DEADLINE": ""
    }}

    =========== REGRAS DE PREENCHIMENTO ===========
    1. TUDO EM CAIXA ALTA. Deixe vazio ("") se não encontrar a informação.
    2. 'CLIENTES': Extraia OBRIGATORIAMENTE no formato "REMETENTE - DESTINATARIO" (se existirem os dois). Remova sufixos inúteis (LTDA, S.A., ME, EPP, EIRELI, IND E COM). Se o documento tiver só o comprador/destinatário, ponha só ele.
    3. 'NAVIO/VIAGEM ARMADOR': Extraia Navio e Viagem juntos (Ex: BARTOLOMEU DIAS / 611N). Ignore o nome da empresa armadora se vier no final (Ex: Hapag-Lloyd, Aliança, MSC).
    4. 'DESTINO': Extraia APENAS a Cidade e UF do DESTINATÁRIO no formato "CIDADE-UF" (Ex: FORTALEZA-CE). Não inclua endereço completo ou repita a cidade.
    5. 'TIPO': O tamanho e o tipo do contêiner (Ex: 20 DRY, 40 HC, 40 NOR). Leia com atenção.
    6. 'NOTAS FISCAIS': Apenas números, sem zeros à esquerda. Se houver mais de uma DIFERENTE, separe por VÍRGULA.
    7. DIFERENÇA DE DOCUMENTOS:
       - NOTA FISCAL (DANFE): Extrai para "NOTAS FISCAIS".
       - CT-E ARMADOR: CT-e emitido por terceiros ou armadores. Extrai para "CT-E ARMADOR".
       - NOSSO CT-E: Se o emissor do CT-E tiver o CNPJ 46.099.394/0001-88 (TRANSPORTADORA NORTE NORDESTE), coloque o número na chave "CTE-E" e deixe "CT-E ARMADOR" VAZIO.
    8. SOMA INTELIGENTE (PESO E VALOR): 
       - Se houver VÁRIAS Notas Fiscais **DIFERENTES** para o MESMO contêiner, SOME os valores ('VALOR DA NF') e os pesos ('PESO DA MERCADORIA KG').
       - ATENÇÃO: NÃO SOME se for a MESMA Nota Fiscal repetida várias vezes no texto.
    9. 'CONTAINER' e 'LACRE': Exatamente 4 letras e 7 números para contêiner.
    10. MULTI-CONTÊINER: Se o documento referenciar MÚLTIPLOS CONTÊINERES (ex: um CT-e para 2 contêineres), você DEVE retornar uma LISTA DE OBJETOS JSON (`[ {{...}}, {{...}} ]`), um para CADA contêiner. Repita as NFs, Valores, Pesos e Clientes em todos os objetos gerados a partir do mesmo documento.

    Retorne APENAS um JSON puro (Array de objetos ou Objeto único). Não use marcações Markdown (````json`).
    TEXTO: 
    {texto}
    """

    _indice_chave_atual = 0

    while _indice_chave_atual < len(LISTA_CHAVES_GEMINI):
        chave_atual = LISTA_CHAVES_GEMINI[_indice_chave_atual]
        client = genai.Client(api_key=chave_atual)
        modelo_escolhido = listar_modelo_disponivel(client, chave_atual)

        print(Fore.WHITE + f"    ...Processando IA ({_indice_chave_atual+1}/{len(LISTA_CHAVES_GEMINI)}): {modelo_escolhido}")

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
            # print(Fore.BLACK + Style.BRIGHT + f"    [DEBUG IA RAW]: {raw}") # Pode descomentar se quiser ver exatamente o que a IA cospe
            
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
                    print(Fore.YELLOW + Style.BRIGHT + f"    🔀 Multi-contêiner detectado pela IA: {len(lista_final)} contêineres lidos no documento!")
                
                for item in lista_final:
                     print(Fore.CYAN + f"    🧠 Extraído: {json.dumps(item, ensure_ascii=False)}")
                
                return lista_final

        except Exception as e:
            erro_str = str(e).upper()
            erros_temporarios = ["429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "OVERLOAD", "INTERNAL"]
            if any(termo in erro_str for termo in erros_temporarios):
                print(Fore.YELLOW + f"   🔄 Chave API {_indice_chave_atual + 1} sobrecarregada. Trocando de chave...")
                _indice_chave_atual += 1
                time.sleep(2)
            else:
                print(Fore.RED + f"   ❌ Erro de processamento na IA: {e}")
                return []
                
    print(Fore.RED + "   ❌ Todas as chaves da API falharam ou estão sobrecarregadas.")
    return []