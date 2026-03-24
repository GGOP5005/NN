import os
import re
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import BASE_DIR, PLANILHA_ID

# --- CONFIGURAÇÃO ---
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

def obter_aba_atual():
    meses_seguros = {
        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARCO", 4: "ABRIL",
        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
    }
    mes_atual = datetime.now().month
    
    try:
        meta = service.spreadsheets().get(spreadsheetId=PLANILHA_ID).execute()
        abas_existentes = [s["properties"]["title"].upper() for s in meta.get("sheets", [])]
        
        aba_alvo = meses_seguros.get(mes_atual, "MARCO")
        if aba_alvo == "MARCO" and "MARÇO" in abas_existentes:
            return "MARÇO"
        elif aba_alvo in abas_existentes:
            return aba_alvo
        return abas_existentes[0]
    except:
        return "MARÇO"

# CORREÇÃO BUG 4: get_col_letter unificada com sheets_api.py
# Versão antiga: chr(65 + idx) só funcionava até a coluna Z (índice 25)
# Esta versão funciona para A-Z e AA-ZZ corretamente
def get_col_letter(idx):
    """Converte índice numérico (base 0) para letra de coluna Excel.
    Ex: 0='A', 25='Z', 26='AA', 27='AB', 51='AZ', 52='BA'
    """
    result = ""
    n = idx + 1  # converte para base 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

def buscar_containers_por_status(status_alvos):
    """Função mestre que busca os contêineres independentemente de onde a coluna esteja"""
    aba = obter_aba_atual()
    fila = []
    try:
        # 🔥 RADAR EXPANDIDO PARA AZ (Para garantir que pega a coluna AA ou além)
        res = service.spreadsheets().values().get(spreadsheetId=PLANILHA_ID, range=f"{aba}!A:AZ").execute()
        linhas = res.get("values", [])
        if not linhas: return fila

        headers = [str(h).upper().strip() for h in linhas[0]]
        
        # 🔥 BUSCA DINÂMICA: Descobre sozinho onde estão as colunas!
        idx_status = headers.index("MONITORAMENTO") if "MONITORAMENTO" in headers else 20
        idx_container = headers.index("CONTAINER") if "CONTAINER" in headers else 26

        for i, linha in enumerate(linhas):
            linha_real = i + 1 
            if linha_real == 1: continue 
            
            # Previne erros se a linha estiver vazia nas últimas colunas
            status = str(linha[idx_status]).upper().strip() if len(linha) > idx_status else ""
            container = str(linha[idx_container]).upper().strip() if len(linha) > idx_container else ""
            
            if any(alvo in status for alvo in status_alvos):
                cont_limpo = re.sub(r'[^A-Z0-9]', '', container)
                if cont_limpo and len(cont_limpo) >= 11:
                    fila.append({"linha": linha_real, "numero": cont_limpo, "aba": aba})
        return fila
    except Exception as e:
        print(f"❌ Erro ao buscar status {status_alvos}: {e}")
        return []

def buscar_containers_pendentes():
    """Fase 1: Busca quem ainda não chegou no porto"""
    return buscar_containers_por_status(["NÃO LIBERADO", "NÃO LIBERADO/FALTA CTE", "NAO LIBERADO"])

def buscar_containers_falta_passe():
    """Fase 2: Busca quem chegou, mas ainda não teve o passe solicitado"""
    return buscar_containers_por_status(["FALTA PASSE"])

def buscar_containers_passe_solicitado():
    """Fase 3: Busca quem aguarda aprovação ou quem falhou na leitura da data na rodada anterior"""
    return buscar_containers_por_status(["PASSE SOLICITADO", "DATA NÃO LIDA", "DATA NAO LIDA"])

def atualizar_status_planilha(linha, novo_status, aba):
    try:
        # Descobre a coluna exata de Monitoramento para não sobrescrever a errada
        res = service.spreadsheets().values().get(spreadsheetId=PLANILHA_ID, range=f"{aba}!A1:AZ1").execute()
        headers = [str(h).upper().strip() for h in res.get("values", [[]])[0]]
        idx_status = headers.index("MONITORAMENTO") if "MONITORAMENTO" in headers else 20
        # CORREÇÃO BUG 5: usa get_col_letter corrigida (não chr(65+idx) que quebra acima de Z)
        col_letra = get_col_letter(idx_status)

        body = {"values": [[novo_status]]}
        range_atualizacao = f"{aba}!{col_letra}{linha}"
        
        service.spreadsheets().values().update(
            spreadsheetId=PLANILHA_ID, range=range_atualizacao, valueInputOption="USER_ENTERED", body=body
        ).execute()
        
        print(f"   ✅ GRAVADO: L{linha} -> '{novo_status}'")
        return True
    except Exception as e:
        print(f"   ❌ Erro ao atualizar planilha: {e}")
        return False
