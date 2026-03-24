import os
import time
import re
from datetime import datetime
from config import PASTA_ERROS, COLUNAS, ROTEAMENTO_PORTOS
from extrator_ia import extrair_com_ia
from sheets_api import adicionar_ou_mesclar_linha
from extrator_pdf import extrair_texto_pdf
from extrator_xml import extrair_texto_xml

def processar_arquivo(caminho_arquivo, spreadsheet_id):
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Erro: Arquivo não encontrado: {caminho_arquivo}")
        return False, []

    for i in range(3):
        try:
            with open(caminho_arquivo, 'rb'): pass
            break
        except IOError:
            time.sleep(1)
            if i == 2:
                print(f"❌ Erro: Arquivo bloqueado pelo sistema: {caminho_arquivo}")
                return False, []

    nome_arquivo = os.path.basename(caminho_arquivo)
    extensao = nome_arquivo.lower().split('.')[-1]
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
                print(f"❌ Fallback XML também falhou: {e2}")
                return False, []

    elif extensao in ['xlsx', 'xls', 'csv']:
        from EXTRATOR_EXCEL import extrair_texto_excel
        try:
            texto_extraido = extrair_texto_excel(caminho_arquivo)
        except Exception as e:
            print(f"❌ Erro ao ler Excel: {e}")
            return False, []

    if not texto_extraido or texto_extraido.strip() == "":
        return False, []

    texto_sanitizado = re.sub(r'[ \t]+', ' ', texto_extraido).strip()

    # extrair_com_ia agora retorna SEMPRE uma lista de dicts
    # Ex: 1 conteiner  ->  [{}]
    # Ex: 2 conteineres -> [{}, {}]  (cada um com sua NF vinculada)
    dados_json_lista = extrair_com_ia(texto_sanitizado)

    if not dados_json_lista:
        return False, []

    # Garante que e sempre lista (seguranca extra)
    if isinstance(dados_json_lista, dict):
        dados_json_lista = [dados_json_lista]

    nome_porto = "PADRAO"
    for pasta, s_id in ROTEAMENTO_PORTOS.items():
        if str(s_id).strip() == str(spreadsheet_id).strip():
            nome_porto = os.path.basename(pasta).replace("entrada_", "").upper()
            break

    try:
        meses_seguros_pt = {
            1: "JANEIRO", 2: "FEVEREIRO", 3: "MARCO", 4: "ABRIL",
            5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
            9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
        }
        aba_mes = meses_seguros_pt.get(datetime.now().month, "GERAL")
    except:
        aba_mes = "GERAL"

    status_final = True
    dados_processados = []

    for dados_json in dados_json_lista:

        # Regra fixa de Santos
        if nome_porto == "SANTOS":
            dados_json["CLIENTES"] = "RISADINHA"
            dados_json["DESTINO"] = "PRAIA GRANDE"

        # ================================================================
        # SEPARACAO DE CONTEINERES
        #
        # A IA ja deve retornar um JSON por conteiner (com sua NF vinculada).
        # Este bloco e um FALLBACK para o caso em que a IA ainda juntar
        # 2 conteineres num unico JSON (ex: CONTAINER: "MRKU123, MSCU456").
        #
        # Se a IA ja separou corretamente (1 conteiner por JSON), este loop
        # roda apenas 1 vez e nao altera nada.
        # ================================================================
        container_str = dados_json.get("CONTAINER", "")
        cont_matches = re.findall(r'[A-Za-z]{4}\s*\d{7}', container_str)

        if cont_matches:
            lista_containers = [re.sub(r'\s+', '', c).upper() for c in cont_matches]
            lista_containers = list(dict.fromkeys(lista_containers))
        else:
            lista_containers = [container_str.strip()] if container_str.strip() else [""]

        # Se a IA JA separou (1 conteiner no JSON) → multiplos_containers_fallback = False
        # Se a IA NAO separou (2+ conteineres no mesmo JSON) → aplica fallback
        multiplos_containers_fallback = len(lista_containers) > 1

        if multiplos_containers_fallback:
            print(f"    ⚠️ Fallback: IA nao separou os conteineres. Separando manualmente: {lista_containers}")

        for cont in lista_containers:
            dados_copia = dados_json.copy()
            dados_copia["CONTAINER"] = cont

            if multiplos_containers_fallback:
                dados_copia["NOTAS FISCAIS"] = ""
                dados_copia["VALOR DA NF"] = ""
                dados_copia["PESO DA MERCADORIA KG"] = ""
                print(f"    📦 Fallback linha: {cont} | NF/Valor aguardam chegada individual")

            st = adicionar_ou_mesclar_linha(spreadsheet_id, aba_mes, dados_copia)
            if not st:
                status_final = False

            # ================================================================
            # RESGATE DE CONTÊINER DA PLANILHA
            # Cenário: NF chegou sem contêiner (campo vazio).
            # O sheets_api fez merge pelo número da NF e encontrou a linha certa.
            # Mas o dados_copia ainda tem CONTAINER vazio.
            # Solução: busca no cache da planilha o contêiner que estava na linha
            # para que o main.py crie a pasta no lugar correto.
            # ================================================================
            if not dados_copia.get("CONTAINER"):
                try:
                    from sheets_api import CACHE_PLANILHA, simplificar_id
                    nf_doc = str(dados_copia.get("NOTAS FISCAIS", "")).strip().upper()
                    cte_doc = str(dados_copia.get("CT-E ARMADOR", dados_copia.get("CTE-E", ""))).strip().upper()

                    for nome_aba, conteudo in CACHE_PLANILHA.get("dados", {}).items():
                        for item in conteudo.get("linhas", []):
                            # Casa pela NF ou pelo CT-e
                            nfs_linha = [x.strip() for x in item.get("nf", "").split(",") if x.strip()]
                            cte_linha = item.get("cte_armador", "") or item.get("cte_nosso", "")

                            nf_bate = nf_doc and any(n in nfs_linha for n in nf_doc.split(",") if n.strip())
                            cte_bate = cte_doc and cte_doc in cte_linha

                            if (nf_bate or cte_bate) and item.get("container_limpo"):
                                dados_copia["CONTAINER"] = item["container_limpo"]
                                print(f"    🔍 Contêiner resgatado da planilha: {item['container_limpo']} (para criar pasta correta)")
                                break
                        if dados_copia.get("CONTAINER"):
                            break
                except Exception as e:
                    pass  # Se falhar, continua sem contêiner (vai para SEM_CONTAINER)

            dados_processados.append(dados_copia)

    return status_final, dados_processados
