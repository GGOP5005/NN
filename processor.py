import os
import time
import re
from datetime import datetime

from config import PASTA_ERROS, COLUNAS, ROTEAMENTO_PORTOS
from extrator_ia import extrair_com_ia
from sheets_api import adicionar_ou_mesclar_linha
from extrator_pdf import extrair_texto_pdf
from extrator_xml import extrair_texto_xml

# Import no topo — evita falha de importação condicional
try:
    from EXTRATOR_EXCEL import extrair_texto_excel
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False
    print("⚠️ EXTRATOR_EXCEL.py não encontrado. Suporte a .xlsx desativado.")


def processar_arquivo(caminho_arquivo, spreadsheet_id):
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Arquivo não encontrado: {caminho_arquivo}")
        return False, []

    # Aguarda arquivo ser totalmente gravado no disco
    for i in range(3):
        try:
            with open(caminho_arquivo, 'rb'): pass
            break
        except IOError:
            time.sleep(1)
            if i == 2:
                print(f"❌ Arquivo bloqueado: {caminho_arquivo}")
                return False, []

    nome_arquivo = os.path.basename(caminho_arquivo)
    extensao = nome_arquivo.lower().rsplit('.', 1)[-1]
    texto_extraido = ""

    if extensao == 'pdf':
        try:
            texto_extraido = extrair_texto_pdf(caminho_arquivo)
        except Exception as e:
            print(f"❌ Erro ao ler PDF: {e}")
            return False, []

    elif extensao == 'xml':
        try:
            texto_extraido = extrair_texto_xml(caminho_arquivo)
        except Exception as e:
            print(f"❌ Erro ao ler XML: {e}")
            try:
                with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                    texto_extraido = f.read()
            except Exception as e2:
                print(f"❌ Fallback XML falhou: {e2}")
                return False, []

    elif extensao in ['xlsx', 'xls', 'csv']:
        if not EXCEL_OK:
            print(f"❌ Suporte Excel não disponível. Instale pandas e openpyxl.")
            return False, []
        try:
            texto_extraido = extrair_texto_excel(caminho_arquivo)
        except Exception as e:
            print(f"❌ Erro ao ler Excel: {e}")
            return False, []

    else:
        print(f"❌ Formato não suportado: {extensao}")
        return False, []

    if not texto_extraido or not texto_extraido.strip():
        print(f"❌ Nenhum texto extraído de {nome_arquivo}")
        return False, []

    texto_sanitizado = re.sub(r'[ \t]+', ' ', texto_extraido).strip()
    dados_json_lista = extrair_com_ia(texto_sanitizado)

    if not dados_json_lista:
        print(f"❌ IA não retornou dados para {nome_arquivo}")
        return False, []

    if isinstance(dados_json_lista, dict):
        dados_json_lista = [dados_json_lista]

    # Identifica o porto pelo spreadsheet_id
    nome_porto = "PADRAO"
    for pasta, s_id in ROTEAMENTO_PORTOS.items():
        if str(s_id).strip() == str(spreadsheet_id).strip():
            nome_porto = os.path.basename(pasta).replace("entrada_", "").upper()
            break

    # Determina aba do mês atual
    try:
        meses_pt = {
            1: "JANEIRO", 2: "FEVEREIRO", 3: "MARCO", 4: "ABRIL",
            5: "MAIO",    6: "JUNHO",     7: "JULHO",  8: "AGOSTO",
            9: "SETEMBRO",10: "OUTUBRO",  11: "NOVEMBRO", 12: "DEZEMBRO"
        }
        aba_mes = meses_pt.get(datetime.now().month, "GERAL")
    except:
        aba_mes = "GERAL"

    status_final = True
    dados_processados = []

    for dados_json in dados_json_lista:

        # Regra específica Santos
        if nome_porto == "SANTOS":
            dados_json["CLIENTES"] = "RISADINHA"
            dados_json["DESTINO"]  = "PRAIA GRANDE"

        container_str = dados_json.get("CONTAINER", "")
        cont_matches = re.findall(r'[A-Za-z]{4}\s*\d{7}', container_str)

        if cont_matches:
            lista_containers = [re.sub(r'\s+', '', c).upper() for c in cont_matches]
            lista_containers = list(dict.fromkeys(lista_containers))
        else:
            lista_containers = [container_str.strip()] if container_str.strip() else [""]

        multiplos = len(lista_containers) > 1
        if multiplos:
            print(f"    ⚠️ Fallback multi-container: {lista_containers}")

        for cont in lista_containers:
            dados_copia = dados_json.copy()
            dados_copia["CONTAINER"] = cont

            if multiplos:
                dados_copia["NOTAS FISCAIS"]        = ""
                dados_copia["VALOR DA NF"]          = ""
                dados_copia["PESO DA MERCADORIA KG"]= ""

            # adicionar_ou_mesclar_linha retorna (bool, str)
            resultado = adicionar_ou_mesclar_linha(spreadsheet_id, aba_mes, dados_copia)
            
            # Robustez: aceita tanto tupla quanto bool simples (legacy)
            if isinstance(resultado, tuple):
                st, container_retorno = resultado
            else:
                st, container_retorno = resultado, ""

            if not st:
                status_final = False

            # Tenta recuperar container via cache se veio vazio
            if not dados_copia.get("CONTAINER"):
                try:
                    from sheets_api import CACHE_PLANILHA
                    nf_doc  = str(dados_copia.get("NOTAS FISCAIS", "")).strip().upper()
                    cte_doc = str(dados_copia.get("CT-E ARMADOR", dados_copia.get("CTE-E", ""))).strip().upper()

                    for _, conteudo in CACHE_PLANILHA.get("dados", {}).items():
                        for item in conteudo.get("linhas", []):
                            nfs_linha = [x.strip() for x in item.get("nf", "").split(",") if x.strip()]
                            cte_linha = item.get("cte_armador", "") or item.get("cte_nosso", "")

                            nf_bate  = nf_doc  and any(n in nfs_linha for n in nf_doc.split(",")  if n.strip())
                            cte_bate = cte_doc and cte_doc in cte_linha

                            if (nf_bate or cte_bate) and item.get("container_limpo"):
                                dados_copia["CONTAINER"] = item["container_limpo"]
                                print(f"    🔍 Container resgatado do cache: {item['container_limpo']}")
                                break
                        if dados_copia.get("CONTAINER"):
                            break
                except Exception:
                    pass

            dados_processados.append(dados_copia)

    return status_final, dados_processados