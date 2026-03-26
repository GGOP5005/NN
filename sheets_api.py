import os
import time
import re
import unicodedata
import string
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import COLUNAS, BASE_DIR, ROTEAMENTO_PORTOS

# --- CONFIGURAÇÃO ---
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

# --- CACHE GLOBAL ---
CACHE_PLANILHA = {
    "id_atual": None,
    "carregado": False,
    "dados": {},
    "abas_existentes": [],
}

MAPA_MESES = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "MARÇO": 3,
    "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
    "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10,
    "NOVEMBRO": 11, "DEZEMBRO": 12,
}

def get_col_letter(idx):
    """Converte índice numérico (base 0) para letra de coluna Excel."""
    result = ""
    n = idx + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

def simplificar_id(texto):
    if not texto: return ""
    return re.sub(r'[^A-Z0-9]', '', str(texto).upper())

def limpar_nome_entidade(nome):
    if not nome: return ""
    nome_comp = nome.upper().strip().replace("&", " E ")
    sufixos = [r"\bLTDA\b", r"\bEIRELI\b", r"\bS\.A\b", r"\bS/A\b", r"\bME\b", r"\bEPP\b", r"\bS\.A\.\b", r"\bMEI\b", r"\bLIMITADA\b", r"\- ME\b", r"\bCIA\b", r"\bC\.I\.A\b", r"\bCOMERCIO\b", r"\bINDUSTRIA\b", r"\bCOM\b", r"\bIND\b"]
    for padrao in sufixos: nome_comp = re.sub(padrao, "", nome_comp)
    return " ".join(nome_comp.replace(".", "").replace(",", "").replace("-", " ").strip().split())

def parse_float_br(val_str):
    if not val_str: return 0.0
    limpo = re.sub(r"[^\d,.]", "", str(val_str))
    if not limpo: return 0.0
    if "," in limpo and "." in limpo: limpo = limpo.replace(".", "").replace(",", ".")
    elif "," in limpo: limpo = limpo.replace(",", ".")
    elif "." in limpo:
        partes = limpo.split(".")
        if len(partes[-1]) == 3: limpo = limpo.replace(".", "")
    try: return float(limpo)
    except: return 0.0

def executar_com_resiliencia_infinita(requisicao, descricao="API Google"):
    tentativa = 1
    while True:
        try: return requisicao.execute()
        except HttpError as error:
            if error.resp.status in [429, 500, 503]:
                print(f"    ⛔ COTA ATINGIDA ({descricao}). A aguardar 70 segundos... (Tentativa {tentativa})")
                time.sleep(70)
                tentativa += 1
            else:
                print(f"    ❌ Erro fatal na API: {error}")
                raise error

def obter_limites_porto(spreadsheet_id):
    config = {"col_max": "Z", "tamanho": 26, "idx_inicio": 3, "idx_fim": 25, "nome_porto": "padrao"}
    for pasta, s_id in ROTEAMENTO_PORTOS.items():
        if str(s_id).strip() == str(spreadsheet_id).strip():
            p = pasta.lower()
            if "pecem" in p or "pecém" in p: 
                config["col_max"] = "AG"
                config["tamanho"] = 33
                config["idx_inicio"] = 3
                config["idx_fim"] = 32
                config["nome_porto"] = "pecem"
            elif "salvador" in p: 
                config["col_max"] = "Z"
                config["tamanho"] = 26
                config["idx_inicio"] = 2
                config["idx_fim"] = 25
                config["nome_porto"] = "salvador"
            elif "santos" in p: 
                config["nome_porto"] = "santos"
            elif "suape" in p or "manaus" in p: 
                config["col_max"] = "AC"
                config["tamanho"] = 29
                config["idx_inicio"] = 3
                config["idx_fim"] = 28
                config["nome_porto"] = "suape_manaus"
            break
    return config

def encontrar_indice_coluna(mapa_headers, chaves_possiveis):
    for chave in chaves_possiveis:
        if chave in mapa_headers: return mapa_headers[chave]
    return -1

def carregar_cache_inicial(spreadsheet_id, forcar=False):
    global CACHE_PLANILHA
    if CACHE_PLANILHA["id_atual"] != spreadsheet_id or forcar:
        CACHE_PLANILHA.update({"id_atual": spreadsheet_id, "carregado": False, "dados": {}, "abas_existentes": []})
    
    if CACHE_PLANILHA["carregado"]: return

    print("    📥 A carregar memória da planilha...")
    conf = obter_limites_porto(spreadsheet_id)
    
    try:
        meta = executar_com_resiliencia_infinita(service.spreadsheets().get(spreadsheetId=spreadsheet_id), "Listar Abas")
        abas_info = {s["properties"]["title"].upper(): s["properties"]["sheetId"] for s in meta.get("sheets", [])}
        abas = list(abas_info.keys())
        CACHE_PLANILHA["abas_existentes"] = abas

        mes_atual = datetime.now().month
        meses_alvo = [mes_atual - 1, mes_atual, (mes_atual % 12) + 1]

        for aba in abas:
            is_alvo = any(m for m, n in MAPA_MESES.items() if n in meses_alvo and m in aba)
            if not is_alvo and len(abas) > 1: continue

            res = executar_com_resiliencia_infinita(service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{aba}!A:{conf['col_max']}"), f"Ler {aba}")
            linhas = res.get("values", [])
            if not linhas: continue

            headers = [str(c).strip().upper() for c in linhas[0]]
            mapa = {nome: i for i, nome in enumerate(headers)}
            
            idx_nf = encontrar_indice_coluna(mapa, ["NOTAS FISCAIS", "NF", "NOTA FISCAL"])
            idx_cont = encontrar_indice_coluna(mapa, ["CONTAINER", "CNTR", "UNIDADE"])
            idx_cte_armador = encontrar_indice_coluna(mapa, ["CT-E ARMADOR", "CTE ARMADOR"])
            idx_cte_nosso = encontrar_indice_coluna(mapa, ["CTE-E", "CTE", "CT-E"])
            idx_lacre = encontrar_indice_coluna(mapa, ["LACRE", "SEAL"])
            idx_booking = encontrar_indice_coluna(mapa, ["BOOKING", "RESERVA", "BOOKING NO"])
            idx_cliente = encontrar_indice_coluna(mapa, ["CLIENTES", "CLIENTE", "DESTINATARIO", "DESTINATÁRIO", "EMPRESA"])

            lista_proc = []
            ult_l = 1
            for i in range(1, len(linhas)):
                row = linhas[i]
                tem_conteudo_real = False
                for c in range(conf["idx_inicio"], conf["idx_fim"] + 1):
                    if c < len(row):
                        val = str(row[c]).strip()
                        if val not in ["", "0", "0,00", "0.00", "-", "0,00%"]:
                            tem_conteudo_real = True
                            break
                
                if tem_conteudo_real:
                    ult_l = i + 1
                    lista_proc.append({
                        "linha_real": i + 1,
                        "nf": str(row[idx_nf]).strip().upper() if idx_nf != -1 and idx_nf < len(row) else "",
                        "container": str(row[idx_cont]).strip().upper() if idx_cont != -1 and idx_cont < len(row) else "",
                        "container_limpo": simplificar_id(str(row[idx_cont])) if idx_cont != -1 and idx_cont < len(row) else "",
                        "cte_armador": str(row[idx_cte_armador]).strip().upper() if idx_cte_armador != -1 and idx_cte_armador < len(row) else "",
                        "cte_nosso": str(row[idx_cte_nosso]).strip().upper() if idx_cte_nosso != -1 and idx_cte_nosso < len(row) else "",
                        "lacre": str(row[idx_lacre]).strip().upper() if idx_lacre != -1 and idx_lacre < len(row) else "",
                        "booking": str(row[idx_booking]).strip().upper() if idx_booking != -1 and idx_booking < len(row) else "",
                        "cliente": limpar_nome_entidade(str(row[idx_cliente])) if idx_cliente != -1 and idx_cliente < len(row) else ""
                    })

            CACHE_PLANILHA["dados"][aba] = {"mapa": mapa, "linhas": lista_proc, "proxima_linha": ult_l + 1, "sheet_id": abas_info.get(aba)}
        
        CACHE_PLANILHA["carregado"] = True
        print("    💾 Memória carregada com sucesso.")
        
    except Exception as e:
        print(f"    ❌ Erro crítico no Cache: {e}")

def buscar_container_por_nf(spreadsheet_id, nf_numero):
    if not nf_numero:
        return ""
    nf_busca = str(nf_numero).strip().upper().lstrip("0")
    carregar_cache_inicial(spreadsheet_id)

    for nome_aba, conteudo in CACHE_PLANILHA.get("dados", {}).items():
        for item in conteudo.get("linhas", []):
            nfs_linha = [x.strip().lstrip("0") for x in item.get("nf", "").replace(";", ",").split(",") if x.strip()]
            if nf_busca in nfs_linha:
                container = item.get("container_limpo", "").strip()
                if container:
                    print(f"    🔍 Contêiner recuperado da planilha para NF {nf_busca}: {container}")
                    return container
    return ""

def adicionar_ou_mesclar_linha(spreadsheet_id, aba_padrao, dados_novos):
    global CACHE_PLANILHA
    conf = obter_limites_porto(spreadsheet_id)

    tentativas = 0
    while tentativas < 2:
        carregar_cache_inicial(spreadsheet_id, forcar=(tentativas > 0))

        nf_n = str(dados_novos.get("NOTAS FISCAIS", dados_novos.get("NF", ""))).strip().upper()
        cte_armador_n = str(dados_novos.get("CT-E ARMADOR", "")).strip().upper()
        cte_nosso_n = str(dados_novos.get("CTE-E", "")).strip().upper()
        cont_n = str(dados_novos.get("CONTAINER", "")).strip().upper()
        lacre_n = str(dados_novos.get("LACRE", "")).strip().upper()
        booking_n = str(dados_novos.get("BOOKING", "")).strip().upper()
        cliente_n = limpar_nome_entidade(str(dados_novos.get("CLIENTES", "")))
        
        cont_n_limpo = simplificar_id(cont_n)

        if not any([nf_n, cte_armador_n, cte_nosso_n, cont_n_limpo, lacre_n, booking_n]):
            return False, ""

        aba_encontrada = aba_padrao.upper()

        def normalizar_texto(t):
            if not t: return ""
            return "".join(c for c in unicodedata.normalize("NFKD", str(t).upper().strip()) if not unicodedata.combining(c))

        meses_seguros = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARCO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}
        aba_alvo_norm = meses_seguros.get(datetime.now().month, "MARCO")

        for aba_existente in CACHE_PLANILHA["abas_existentes"]:
            if normalizar_texto(aba_existente) == aba_alvo_norm:
                aba_encontrada = aba_existente
                break

        linha_encontrada = -1
        modo = "NOVO"

        for nome_aba, conteudo in CACHE_PLANILHA["dados"].items():
            for item in conteudo["linhas"]:
                
                match_nf = False
                if nf_n:
                    nfs_planilha = [x.strip() for x in item.get("nf", "").replace(";", ",").split(",") if x.strip()]
                    nfs_novo = [x.strip() for x in nf_n.replace(";", ",").split(",") if x.strip()]
                    if any(n in nfs_planilha for n in nfs_novo): match_nf = True

                match_cte_armador = False
                if cte_armador_n:
                    ctes_p = [x.strip() for x in item.get("cte_armador", "").replace(";", ",").split(",") if x.strip()]
                    ctes_n = [x.strip() for x in cte_armador_n.replace(";", ",").split(",") if x.strip()]
                    if any(c in ctes_p for c in ctes_n): match_cte_armador = True

                match_cte_nosso = False
                if cte_nosso_n:
                    ctes_p = [x.strip() for x in item.get("cte_nosso", "").replace(";", ",").split(",") if x.strip()]
                    ctes_n = [x.strip() for x in cte_nosso_n.replace(";", ",").split(",") if x.strip()]
                    if any(c in ctes_p for c in ctes_n): match_cte_nosso = True

                match_cont = cont_n_limpo != "" and (cont_n_limpo in item.get("container_limpo", ""))
                match_lacre = lacre_n != "" and (lacre_n in item.get("lacre", ""))
                match_booking = booking_n != "" and (booking_n in item.get("booking", ""))
                cliente_linha = item.get("cliente", "")
                
                if match_cont:
                    linha_encontrada = item["linha_real"]
                    aba_encontrada = nome_aba
                    modo = "MESCLAR"
                    print(f"    ✨ Documento agrupado pelo CONTÊINER na Planilha: '{nome_aba}' L{linha_encontrada}")
                    break

                tem_container_na_linha = item.get("container_limpo", "") != ""
                tem_container_novo = cont_n_limpo != ""
                colisao_container = (tem_container_novo and tem_container_na_linha and cont_n_limpo not in item.get("container_limpo", ""))

                if colisao_container:
                    continue
                
                clientes_incompativeis = False
                if cliente_n and cliente_linha:
                    p1 = set(cliente_n.split())
                    p2 = set(cliente_linha.split())
                    gen = {"DE", "E", "DO", "DA", "LTDA", "COMERCIO", "INDUSTRIA", "MATERIAL", "MATERIAIS", "CONSTRUCAO", "CONSTRUCOES", "S/A", "SA", "ME", "EPP", "CIA"}
                    p1_uteis = p1 - gen
                    p2_uteis = p2 - gen
                    if p1_uteis and p2_uteis and not p1_uteis.intersection(p2_uteis):
                        clientes_incompativeis = True
                
                if not clientes_incompativeis:
                    if match_nf or match_cte_armador or match_cte_nosso or match_lacre or match_booking:
                        linha_encontrada = item["linha_real"]
                        aba_encontrada = nome_aba
                        modo = "MESCLAR"
                        print(f"    ✨ Documento agrupado por referência cruzada na Planilha: '{nome_aba}' L{linha_encontrada}")
                        break
                        
            if modo == "MESCLAR": break

        if modo == "NOVO":
            if aba_encontrada not in CACHE_PLANILHA["dados"]:
                # Tenta variantes com/sem acento (MARCO ↔ MARÇO)
                variantes = [aba_encontrada, aba_encontrada.replace("MARCO", "MARÇO"), aba_encontrada.replace("MARÇO", "MARCO")]
                encontrou_variante = False
                for var in variantes:
                    if var in CACHE_PLANILHA["dados"]:
                        aba_encontrada = var
                        encontrou_variante = True
                        break
                if not encontrou_variante:
                    # Último recurso: usa a primeira aba disponível nos dados
                    abas_com_dados = list(CACHE_PLANILHA["dados"].keys())
                    if abas_com_dados:
                        aba_encontrada = abas_com_dados[0]
                        print(f"    ⚠️ Aba '{aba_encontrada}' não encontrada. Usando '{aba_encontrada}' como fallback.")
                    else:
                        print(f"    ❌ BLOQUEADO: Nenhuma aba disponível no cache.")
                        return False, ""
            break

        if modo == "MESCLAR":
            info_aba = CACHE_PLANILHA["dados"].get(aba_encontrada)
            try:
                res = executar_com_resiliencia_infinita(
                    service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{aba_encontrada}!A{linha_encontrada}:{conf['col_max']}{linha_encontrada}")
                )
                vals = res.get("values", [])
                if vals and len(vals[0]) > 0:
                    break
                else:
                    tentativas += 1
                    continue
            except:
                tentativas += 1
                continue

    info_aba = CACHE_PLANILHA["dados"].get(aba_encontrada)
    if not info_aba: return False, ""

    TAMANHO = conf["tamanho"]
    mapa_colunas = info_aba["mapa"]
    linha_buffer = [""] * TAMANHO

    linha_dest = linha_encontrada if modo == "MESCLAR" else info_aba["proxima_linha"]

    try:
        res = executar_com_resiliencia_infinita(
            service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"{aba_encontrada}!A{linha_dest}:{conf['col_max']}{linha_dest}")
        )
        vals = res.get("values", [])
        if vals:
            for i, v in enumerate(vals[0]):
                if i < TAMANHO: linha_buffer[i] = str(v)
    except: pass

    tem_nf_nova = True
    if nf_n and modo == "MESCLAR":
        idx_nf_sheet = mapa_colunas.get("NOTAS FISCAIS", mapa_colunas.get("NF", mapa_colunas.get("NOTA FISCAL", -1)))
        if idx_nf_sheet != -1:
            nf_existentes_str = str(linha_buffer[idx_nf_sheet]).strip().upper()
            lista_exist = [limpar_nome_entidade(x) for x in nf_existentes_str.split(",") if x.strip()]
            lista_nova = [limpar_nome_entidade(x) for x in nf_n.replace(";", ",").split(",") if x.strip()]
            
            tem_nf_nova = False
            for nn in lista_nova:
                if nn and nn not in lista_exist:
                    tem_nf_nova = True
                    break

    apelidos = {"CLIENTE": "CLIENTES", "NOTA FISCAL": "NOTAS FISCAIS", "NF": "NOTAS FISCAIS", "CTE": "CTE-E", "BOOKING NO": "BOOKING", "NAVIO": "NAVIO/VIAGEM ARMADOR"}
    indices_para_atualizar = set()

    for chave, valor in dados_novos.items():
        k = chave.upper().strip()
        v = str(valor).strip()
        if not v: continue
        
        idx = mapa_colunas.get(k, mapa_colunas.get(apelidos.get(k, ""), -1))
        
        if idx != -1 and conf["idx_inicio"] <= idx <= conf["idx_fim"]:
            valor_atual = str(linha_buffer[idx]).strip()
            
            if k in ["CLIENTES", "CLIENTE"]:
                valor_atual_limpo = valor_atual if modo == "MESCLAR" else ""
                todos_clientes = [x.strip() for x in valor_atual_limpo.split(",") if x.strip()] + [x.strip() for x in v.split(",") if x.strip()]
                
                if conf.get("nome_porto") == "santos":
                    destinatarios_display = []
                    destinatarios_clean = set()
                    for c_str in todos_clientes:
                        d_disp = c_str.split("-", 1)[-1].strip() if "-" in c_str else c_str.strip()
                        d_clean = limpar_nome_entidade(d_disp)
                        if d_clean and d_clean not in destinatarios_clean:
                            destinatarios_clean.add(d_clean)
                            destinatarios_display.append(d_disp)
                    linha_buffer[idx] = " / ".join(destinatarios_display)
                else:
                    remetentes_display = []
                    remetentes_clean = set()
                    destinatarios_display = []
                    destinatarios_clean = set()
                    outros_display = []
                    
                    for c_str in todos_clientes:
                        if "-" in c_str:
                            parts = c_str.split("-", 1)
                            r_disp = parts[0].strip()
                            d_disp = parts[1].strip()
                            r_clean = limpar_nome_entidade(r_disp)
                            d_clean = limpar_nome_entidade(d_disp)
                            if r_clean and r_clean not in remetentes_clean:
                                remetentes_clean.add(r_clean)
                                remetentes_display.append(r_disp)
                            if d_clean and d_clean not in destinatarios_clean:
                                destinatarios_clean.add(d_clean)
                                destinatarios_display.append(d_disp)
                        else:
                            o_disp = c_str.strip()
                            o_clean = limpar_nome_entidade(o_disp)
                            if o_clean and o_clean not in remetentes_clean:
                                remetentes_clean.add(o_clean)
                                outros_display.append(o_disp)
                    
                    str_rem = " / ".join(remetentes_display) if remetentes_display else ""
                    str_dest = " / ".join(destinatarios_display) if destinatarios_display else ""
                    
                    if str_rem and str_dest:
                        nova_string = f"{str_rem} - {str_dest}"
                        if outros_display: nova_string += ", " + ", ".join(outros_display)
                        linha_buffer[idx] = nova_string
                    else:
                        linha_buffer[idx] = ", ".join(remetentes_display + destinatarios_display + outros_display)
                indices_para_atualizar.add(idx)

            elif k in ["NOTAS FISCAIS", "NF", "NOTA FISCAL", "CT-E ARMADOR", "CTE-E", "CTE", "DESTINO"]:
                lista_exist_disp = [x.strip() for x in valor_atual.split(",") if x.strip()] if modo == "MESCLAR" and valor_atual else []
                lista_nova_disp = [x.strip() for x in v.split(",") if x.strip()]
                exist_limpos = [limpar_nome_entidade(x) for x in lista_exist_disp]
                for item_novo in lista_nova_disp:
                    if item_novo and limpar_nome_entidade(item_novo) not in exist_limpos:
                        lista_exist_disp.append(item_novo)
                        exist_limpos.append(limpar_nome_entidade(item_novo))
                linha_buffer[idx] = ", ".join(lista_exist_disp)
                indices_para_atualizar.add(idx)
                
            elif k in ["VALOR DA NF", "PESO DA MERCADORIA KG"] and modo == "MESCLAR" and valor_atual and v:
                if nf_n and not tem_nf_nova:
                    continue
                try:
                    num_atual = parse_float_br(valor_atual)
                    num_novo = parse_float_br(v)
                    soma_total = num_atual + num_novo
                    if k == "VALOR DA NF": linha_buffer[idx] = f"R$ {soma_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    else: linha_buffer[idx] = f"{soma_total:,.0f}".replace(",", ".")
                    indices_para_atualizar.add(idx)
                except: pass
            else:
                if modo == "NOVO" or not valor_atual:
                    linha_buffer[idx] = v
                    indices_para_atualizar.add(idx)

    if indices_para_atualizar:
        data_requests = []
        for idx in indices_para_atualizar:
            col_letra = get_col_letter(idx)
            data_requests.append({
                "range": f"{aba_encontrada}!{col_letra}{linha_dest}",
                "values": [[linha_buffer[idx]]]
            })

        try:
            body_values = {"valueInputOption": "USER_ENTERED", "data": data_requests}
            executar_com_resiliencia_infinita(service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body_values))
            
            sheet_id_aba = info_aba.get("sheet_id")
            if sheet_id_aba is not None:
                format_requests = [{
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id_aba,
                            "startRowIndex": linha_dest - 1,
                            "endRowIndex": linha_dest,
                            "startColumnIndex": conf["idx_inicio"],
                            "endColumnIndex": conf["idx_fim"] + 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {"fontFamily": "Arial", "fontSize": 11}
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment,textFormat)"
                    }
                }]
                executar_com_resiliencia_infinita(service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": format_requests}), "Aplicar Formatação")

            msg = f"🔄 Unificado: '{aba_encontrada}' L{linha_dest}" if modo == "MESCLAR" else f"✅ Novo Registro Criado: '{aba_encontrada}' L{linha_dest}"
            print(msg)

            CACHE_PLANILHA["carregado"] = False

            idx_cont_ret = encontrar_indice_coluna(mapa_colunas, ["CONTAINER", "CNTR", "UNIDADE"])
            container_retorno = ""
            if idx_cont_ret != -1 and idx_cont_ret < len(linha_buffer):
                container_retorno = simplificar_id(str(linha_buffer[idx_cont_ret]))

            return True, container_retorno

        except Exception as e:
            print(f"❌ Erro ao gravar (Batch): {e}")
            return False, ""
    else:
        print("    ⚠️ Nenhum dado válido extraído para a área de ação.")
        return False, ""