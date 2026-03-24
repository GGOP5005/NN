import os
import sys
import locale
from datetime import datetime
from dotenv import load_dotenv

# Tenta ajustar data para Português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.utf-8')
except:
    try: locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
    except: pass 

# Define o diretório base
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Carrega as senhas do arquivo .env
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)

# --- API KEY (Projeto 1) ---
LISTA_CHAVES_GEMINI = [
    "AIzaSyDdWKkSd02f-YnvJHohjufItZo2KKd4nzg", 
    "AIzaSyAz6HKWtWJwOsOVIpS8KFbLqiCFZ9vv0rw",                 
    "AIzaSyATV3MDPLs5CkuqQQYzYRfDhjww7m-W4yM",
    "AIzaSyAOqeOeo2VS127yheGnUbCocPDnSR6JpVk",
    "AIzaSyCgEPaLBUDfEcc5Xonxwo4f25tSDox1iQ4",
    "AIzaSyBXEOqEAbSlODnO49Qj6P69xFzwXDKV4fs",
    "AIzaSyDeZ96HNRCFSM5ola6cqBtHtJ1QgJV1hBQ",
    "AIzaSyB2qMatbkUdwEVDwySEUe_X1NeaSqvjOs0"                 
]

# =====================================================================
# --- PASTAS DE SISTEMA E ARQUITETURA NORTE NORDESTE ---
# =====================================================================
DROPBOX_DIR = r"C:\Users\supor\Dropbox\ENTRADAS"

# Acha a pasta raiz do Dropbox (C:\Users\supor\Dropbox)
DROPBOX_ROOT = os.path.dirname(DROPBOX_DIR)

PASTA_ERROS = os.path.join(DROPBOX_DIR, "Erros")
PASTA_LOGS = os.path.join(BASE_DIR, "Logs") 

# IMPORTANTE: Ensina o buscador do Tecon a olhar para a pasta do ano correto!
ano_atual = str(datetime.now().year)
PASTA_RAIZ_DOCUMENTOS = os.path.join(DROPBOX_ROOT, "NORTE NORDESTE", f"DOCUMENTAÇÃO DE ENTREGA SUAPE {ano_atual}")

# --- MAPEAMENTO PLANILHAS ---
ROTEAMENTO_PORTOS = {
    os.path.join(DROPBOX_DIR, "entrada_manaus"): "1ekdnK1eGvJrSkY8trB4683TMUxI0CZml1xL3PEG5uXo",
    os.path.join(DROPBOX_DIR, "entrada_pecem"): "1K_2q19dF4q-AJHMGSyPNSOml0sar2vJemZJyxbo9siw",
    os.path.join(DROPBOX_DIR, "entrada_salvador"): "1SL3tF_BSIePacACo8_ZDGfq1yYgrstdcUhSCvdJunlo", 
    os.path.join(DROPBOX_DIR, "entrada_santos"): "15elDT9CrIHc6qx8LEVPp1ACSxNK73Idzk0j2gBJbu1Q",
    os.path.join(DROPBOX_DIR, "entrada_suape"): "1nb1fZeBN4wJtHgeQ-J0DtrLhK0KomTuOGg2UI_cKcu0", 
}

COLUNAS = [
    "CLIENTES", "DESTINO", "BOOKING", "NAVIO/VIAGEM ARMADOR",
    "VALOR DA NF", "PESO DA MERCADORIA KG", "NOTAS FISCAIS",
    "CT-E ARMADOR", "CONTAINER", "TIPO", "LACRE"
]

# =====================================================================
# --- CONFIGURAÇÕES DO PROJETO 4 (BACKUP E ORGANIZAÇÃO) ---
# =====================================================================
PASTA_BACKUP_RAIZ = r"G:\Meu Drive\NORTE NORDESTE" # MUDE PARA O CAMINHO DO SEU DRIVE DE BACKUP

# =====================================================================
# --- CONFIGURAÇÕES DO TECON SUAPE (Projeto 2) ---
# =====================================================================
TECON_CPF = os.getenv("TECON_CPF")
TECON_SENHA = os.getenv("TECON_SENHA")
PLANILHA_ID = os.getenv("PLANILHA_ID", "1nb1fZeBN4wJtHgeQ-J0DtrLhK0KomTuOGg2UI_cKcu0")

CNPJ_TRANSPORTADORA = "46099394000188"
HEADLESS = False