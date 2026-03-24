from google import genai
from google.genai import types
import json
import re
import time
from config import LISTA_CHAVES_GEMINI, COLUNAS

# Cache de modelo separado por chave API
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
    chaves_atuais = list(dados.keys())
    for k in chaves_atuais:
        k_upper = k.upper().strip()
        if any(x in k_upper for x in ["NAVIO", "VESSEL", "VIAGEM"]):
            if k_upper != "NAVIO/VIAGEM ARMADOR" and not dados.get("NAVIO/VIAGEM ARMADOR"):
                dados["NAVIO/VIAGEM ARMADOR"] = dados[k]

    if "VALOR DA NF" in dados and dados["VALOR DA NF"]:
        try:
            val_str = str(dados["VALOR DA NF"])
            limpo = re.sub(r'[^\d,.]', '', val_str)
            if ',' in limpo and '.' in limpo: limpo = limpo.replace('.', '').replace(',', '.')
            elif ',' in limpo: limpo = limpo.replace(',', '.')
            val_float = float(limpo)
            formatado = f"R$ {val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            dados["VALOR DA NF"] = formatado
        except:
            pass

    if "PESO DA MERCADORIA KG" in dados and dados["PESO DA MERCADORIA KG"]:
        try:
            peso_str = str(dados["PESO DA MERCADORIA KG"])
            limpo = re.sub(r'[^\d,.]', '', peso_str)
            if ',' in limpo and '.' in limpo: limpo = limpo.replace('.', '').replace(',', '.')
            elif ',' in limpo: limpo = limpo.replace(',', '.')
            peso_float = float(limpo)
            formatado = f"{peso_float:,.0f}".replace(",", ".")
            dados["PESO DA MERCADORIA KG"] = formatado
        except:
            pass

    if "DESTINO" in dados and dados["DESTINO"]:
        dados["DESTINO"] = dados["DESTINO"].upper().strip()

    return dados

def limpeza_seguranca(texto, dados):
    texto_upper = texto.upper()

    navio_atual = str(dados.get("NAVIO/VIAGEM ARMADOR", "")).strip()
    if not navio_atual or navio_atual in ["NONE", "NULL", "N/A"]:
        match_navio1 = re.search(r'NAVIO/VIAGEM:\s*([A-Z0-9\s/]{5,40})(?=\s|$)', texto_upper)
        if match_navio1:
            dados["NAVIO/VIAGEM ARMADOR"] = match_navio1.group(1).strip()
        else:
            match_navio2 = re.search(r'IDENTIFICA[CÇ][AÃ]O DO NAVIO[^\s]*\s+([A-Z\s]{5,30})(?=\s|$)', texto_upper)
            if match_navio2:
                dados["NAVIO/VIAGEM ARMADOR"] = match_navio2.group(1).strip()

    texto_apenas_numeros = re.sub(r'[^\d]', '', texto_upper)
    nosso_cte_exportacao = "46099394000188" in texto_apenas_numeros

    tem_booking = any(x in texto_upper for x in ["CONFIRMAÇÃO DE BOOKING", "DEAD LINE FINAL", "PROPOSTA COMERCIAL"])
    tem_cte = any(x in texto_upper for x in ["DACTE", "CONHECIMENTO DE TRANSPORTE", "CT-E"])
    tem_danfe = any(x in texto_upper for x in ["DANFE", "NOTA FISCAL", "DOCUMENTO AUXILIAR DE NOTA FISCAL ELETRONICA"])

    if tem_booking:
        dados["VALOR DA NF"] = ""
        dados["PESO DA MERCADORIA KG"] = ""
        dados["NOTAS FISCAIS"] = ""
        dados["CT-E ARMADOR"] = ""
        dados["CTE-E"] = ""

    elif tem_cte:
        if not tem_danfe and not nosso_cte_exportacao:
            dados["VALOR DA NF"] = ""
            dados["PESO DA MERCADORIA KG"] = ""

        cte_armador = str(dados.get("CT-E ARMADOR", "")).strip()
        cte_nosso = str(dados.get("CTE-E", "")).strip()

        if cte_armador and nosso_cte_exportacao:
            dados["CTE-E"] = "".join(filter(str.isdigit, cte_armador))
            dados["CT-E ARMADOR"] = ""
        elif cte_armador:
            dados["CT-E ARMADOR"] = "".join(filter(str.isdigit, cte_armador))

        if cte_nosso:
            dados["CTE-E"] = "".join(filter(str.isdigit, cte_nosso))

    return dados

def normalizar_item(dados):
    """Normaliza um dict de dados: limpa valores, remove nulos, etc."""
    for k, v in dados.items():
        if isinstance(v, list):
            dados[k] = " - ".join(str(x) for x in v)
        if isinstance(v, str):
            val = v.replace("[", "").replace("]", "").replace("'", "").replace('"', '').upper().strip()
            if val in ["NONE", "NULL", "N/A", "UNDEFINED"]:
                val = ""
            if k == "NOTAS FISCAIS" and val:
                val = val.lstrip('0')
            dados[k] = val
    return dados

def detectar_containers_nas_observacoes(texto):
    """
    Detecta ANTES de chamar a IA se o texto tem múltiplos contêineres
    nas observações do CT-e, no padrão:
      'Container - Lacre: MRKU2792430 - MLBR1162322'
      'Container - Lacre: MRKU2977178 - MLBR1162314'

    Retorna lista de dicts: [{"container": "MRKU...", "lacre": "MLBR..."}, ...]
    Retorna lista vazia se não encontrar o padrão.
    """
    texto_upper = texto.upper()

    # Padrão 1: "Container - Lacre: CODIGO - LACRE" (formato Aliança/Armadores)
    padrao1 = re.findall(
        r'CONTAINER\s*[-–]\s*LACRE\s*:\s*([A-Z]{4}\d{7})\s*[-–]\s*([A-Z0-9]{4,15})',
        texto_upper
    )

    # Padrão 2: contêiner e lacre em pares na mesma linha (formato alternativo)
    padrao2 = re.findall(
        r'\b([A-Z]{4}\d{7})\b.*?LACRE[:\s]*([A-Z0-9]{4,15})',
        texto_upper
    )

    resultados = []
    vistos = set()

    for cont, lacre in (padrao1 or padrao2):
        cont = re.sub(r'\s+', '', cont)
        if cont not in vistos:
            vistos.add(cont)
            resultados.append({"container": cont, "lacre": lacre.strip()})

    return resultados


def detectar_nfs_originarias(texto):
    """
    Extrai as NFs referenciadas nos DOCUMENTOS ORIGINÁRIOS do CT-e.
    Retorna lista de números de NF na ordem em que aparecem.
    Ex: ["33636", "33633"]
    """
    texto_upper = texto.upper()
    nfs = []

    # Padrão: "NF-E ... NÚMERO ... 000033636" ou "NF-E 001 000033636"
    # Extrai da chave de acesso (posição 25-34) se disponível
    chaves = re.findall(r'\d{44}', texto_upper)
    for chave in chaves:
        if chave[20:22] == "55":  # NF-e
            num = str(int(chave[25:34]))
            if num and num not in nfs:
                nfs.append(num)

    # Fallback: busca por "NÚMERO ... 000033636" nas tabelas de docs originários
    if not nfs:
        matches = re.findall(r'\b0*([1-9]\d{4,8})\b', texto_upper)
        # Filtra apenas números que parecem NF (5-9 dígitos)
        for m in matches:
            if 5 <= len(m) <= 9 and m not in nfs:
                nfs.append(m)

    return nfs


def extrair_com_ia(texto):
    """
    Extrai dados logísticos do texto usando o Gemini.

    Retorna SEMPRE uma lista de dicts — um por contêiner.
    Caso haja apenas 1 contêiner, retorna lista com 1 elemento.

    PRÉ-PROCESSAMENTO (antes da IA):
    Detecta múltiplos contêineres nas observações via regex.
    Se encontrar, injeta no prompt os pares contêiner→NF já mapeados,
    garantindo que a IA separe corretamente mesmo em PDFs com texto truncado.
    """
    # ================================================================
    # PRÉ-DETECÇÃO: verifica multi-contêiner ANTES de chamar a IA
    # Isso garante separação correta mesmo quando o PDF trunca as obs.
    # ================================================================
    containers_obs = detectar_containers_nas_observacoes(texto)
    nfs_originarias = detectar_nfs_originarias(texto)

    hint_multicontainer = ""
    if len(containers_obs) > 1:
        pares = []
        for idx, item in enumerate(containers_obs):
            nf = nfs_originarias[idx] if idx < len(nfs_originarias) else ""
            pares.append(f"  Contêiner {idx+1}: {item['container']} | Lacre: {item['lacre']} | NF: {nf}")
        hint_multicontainer = f"""
    ⚠️ ATENÇÃO CRÍTICA: Este documento tem {len(containers_obs)} CONTÊINERES DETECTADOS automaticamente:
{chr(10).join(pares)}

    Você DEVE retornar uma LISTA com {len(containers_obs)} objetos JSON.
    Cada objeto com seu contêiner e NF corretos conforme acima.
    NÃO retorne um único JSON. NÃO misture as NFs.
    """
        print(f"    🔍 Pré-detecção: {len(containers_obs)} contêineres encontrados nas observações → hint injetado no prompt")

    prompt = f"""
    Atue como um extrator de dados logísticos RÍGIDO para uma transportadora brasileira.
    Analise o texto abaixo e retorne os dados no formato especificado.
    {hint_multicontainer}
    =========== FORMATO DE RETORNO ===========

    CASO 1 — Documento com UM contêiner:
    Retorne UM ÚNICO objeto JSON:
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
      "LACRE": ""
    }}

    CASO 2 — CT-e com MÚLTIPLOS contêineres (identificados nas Observações):
    Retorne uma LISTA de JSONs, um por contêiner, cada um com SUA NF vinculada:
    [
      {{
        "CLIENTES": "",
        "DESTINO": "",
        "BOOKING": "",
        "NAVIO/VIAGEM ARMADOR": "",
        "VALOR DA NF": "",
        "PESO DA MERCADORIA KG": "",
        "NOTAS FISCAIS": "NF DO CONTAINER 1",
        "CT-E ARMADOR": "",
        "CTE-E": "",
        "CONTAINER": "CODIGO DO CONTAINER 1",
        "TIPO": "",
        "LACRE": "LACRE DO CONTAINER 1"
      }},
      {{
        "CLIENTES": "",
        "DESTINO": "",
        "BOOKING": "",
        "NAVIO/VIAGEM ARMADOR": "",
        "VALOR DA NF": "",
        "PESO DA MERCADORIA KG": "",
        "NOTAS FISCAIS": "NF DO CONTAINER 2",
        "CT-E ARMADOR": "",
        "CTE-E": "",
        "CONTAINER": "CODIGO DO CONTAINER 2",
        "TIPO": "",
        "LACRE": "LACRE DO CONTAINER 2"
      }}
    ]

    =========== REGRAS DE PREENCHIMENTO ===========
    1. TUDO EM CAIXA ALTA. Deixe vazio ("") se não encontrar.
    2. 'CLIENTES': Formato "REMETENTE - DESTINATARIO". Remova sufixos (LTDA, S.A., IND E COM, CONSTRUCOES, DE MADEIRAS).
    3. 'NAVIO/VIAGEM ARMADOR': Vasculhe com LUPA. Se encontrar "MAERSK", "MSC", "CMA CGM", "ALIANÇA", "HAPAG" ou "Navio/Viagem:", extraia o nome que vem DEPOIS. Se o armador vier DEPOIS do nome do navio (ex: "ALIANCA LEBLON/611S ALIANCA"), NÃO extraia o nome do armador, apenas "ALIANCA LEBLON/611S".
    4. 'DESTINO': "CIDADE-UF" do DESTINATÁRIO (quem compra/recebe a mercadoria).
    5. 'NOTAS FISCAIS': Apenas números sem zeros à esquerda. Separe por VÍRGULA se houver mais de uma NO MESMO CONTÊINER.
    6. 'CONTAINER': Código do contêiner (4 letras + 7 números). Ex: MRKU2792430.
    7. 'LACRE': Número do lacre do contêiner.
    8. 'BOOKING': Procure por "Booking:", "Reserva:" ou "Ctrl:".
    9. 'PESO DA MERCADORIA KG': Apenas o número, sem "KG". Peso bruto total.
    10. 'VALOR DA NF': Valor comercial da carga, NÃO o valor do frete.
    11. 'CT-E ARMADOR': Número do CT-e SE o emissor for armador ou transportadora TERCEIRA (ex: Aliança, Log-in, Mercosul, MSC).
    12. 'CTE-E': Número do CT-e SOMENTE SE o emissor for 'NORTE NORDESTE' (CNPJ 46.099.394/0001-88). Caso contrário deixe VAZIO.
    13. Se o texto for apenas "CONFIRMAÇÃO DE BOOKING", deixe NOTAS FISCAIS, VALOR DA NF e PESO vazios.

    =========== REGRA ESPECIAL MULTI-CONTÊINER ===========
    Se nas OBSERVAÇÕES do CT-e aparecer mais de um contêiner no formato:
    "Container - Lacre: [CODIGO] - [LACRE]"
    Então:
    - Crie UM objeto JSON por contêiner
    - Vincule a NF CORRETA a cada contêiner pela ORDEM em que aparecem
      nos DOCUMENTOS ORIGINÁRIOS (a 1ª NF listada é do 1º contêiner, etc.)
    - Campos comuns (CLIENTES, DESTINO, NAVIO, BOOKING, CT-E) são iguais em todos
    - VALOR DA NF e PESO ficam VAZIOS em cada linha (cada NF tem seu próprio valor)

    Retorne APENAS o JSON ou lista JSON pura. Sem texto extra, sem Markdown.
    TEXTO: {texto}
    """

    for i, chave in enumerate(LISTA_CHAVES_GEMINI):
        try:
            client = genai.Client(api_key=chave)
            nome_modelo = listar_modelo_disponivel(client, chave)

            print(f"    ...Processando com Chave {i+1}/{len(LISTA_CHAVES_GEMINI)} (Modelo: {nome_modelo})")

            response = client.models.generate_content(
                model=nome_modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )

            print(f"    🧠 RAW IA: {response.text[:300]}{'...' if len(response.text) > 300 else ''}")

            raw = response.text.strip()
            # Remove blocos markdown se a IA os incluir mesmo com response_mime_type
            raw = re.sub(r'^```json\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\s*```$', '', raw)

            parsed = json.loads(raw)

            # Normaliza para sempre ser uma lista
            if isinstance(parsed, dict):
                # IA retornou um único JSON — coloca numa lista
                lista = [normalizar_item(parsed)]
            elif isinstance(parsed, list):
                # IA retornou lista de JSONs (multi-contêiner)
                lista = [normalizar_item(item) for item in parsed if isinstance(item, dict)]
            else:
                print(f"    ⚠️ Formato inesperado da IA: {type(parsed)}")
                continue

            # Aplica padronização e limpeza de segurança em cada item
            lista_final = []
            for item in lista:
                item = padronizar_valores(item)
                item = limpeza_seguranca(texto, item)
                lista_final.append(item)

            if lista_final:
                if len(lista_final) > 1:
                    print(f"    🔀 Multi-contêiner detectado pela IA: {len(lista_final)} contêineres")
                    for idx, it in enumerate(lista_final):
                        print(f"       #{idx+1}: {it.get('CONTAINER','')} | NF: {it.get('NOTAS FISCAIS','')} | Lacre: {it.get('LACRE','')}")
                return lista_final

        except Exception as e:
            erro_str = str(e).upper()
            erros_temporarios = ["429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "OVERLOAD", "INTERNAL"]
            if any(termo in erro_str for termo in erros_temporarios):
                print(f"    ⚠️ Chave {i+1} indisponível ({str(e)[:60]}). Tentando próxima...")
                continue
            else:
                print(f"    ❌ Erro fatal na Chave {i+1}: {e}")
                break

    return None
