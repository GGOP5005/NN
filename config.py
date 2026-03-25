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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)

LISTA_CHAVES_GEMINI = [
    "AIzaSyDdWKkSd02f-YnvJHohjufItZo2KKd4nzg", 
    "AIzaSyAz6HKWtWJwOsOVIpS8KFbLqiCFZ9vv0rw",                 
    "AIzaSyATV3MDPLs5CkuqQQYzYRfDhjww7m-W4yM",
    "AIzaSyAOqeOeo2VS127yheGnUbCocPDnSR6JpVk",
    "AIzaSyCgEPaLBUDfEcc5Xonxwo4f25ttW-97uM"
]

TECON_CPF = os.environ.get("TECON_CPF")
TECON_SENHA = os.environ.get("TECON_SENHA")

CNPJ_TRANSPORTADORA = "46099394000188"
HEADLESS = True

PLANILHA_ID = os.environ.get("PLANILHA_ID")
if not PLANILHA_ID:
    PLANILHA_ID = "1nb1fZeBN4wJtHgeQ-J0DtrLhK0KomTuOGg2UI_cKcu0"

# Dicionários e Pastas Base
DROPBOX_DIR = r"C:\Users\supor\Dropbox\Norte Nordeste\FILA_DE_PROCESSAMENTO"
PASTA_ERROS = os.path.join(DROPBOX_DIR, "00_ERROS_DE_LEITURA")

ano_atual = datetime.now().year
PASTA_RAIZ_DOCUMENTOS = os.path.join(os.path.dirname(DROPBOX_DIR), f"DOCUMENTAÇÃO DE ENTREGA SUAPE {ano_atual}")

ROTEAMENTO_PORTOS = {
    os.path.join(DROPBOX_DIR, "entrada_manaus"): "1ekdnK1eGvJrSkY8trB4683TMUxI0CZml1xL3PEG5uXo",
    os.path.join(DROPBOX_DIR, "entrada_pecem"): "1K_2q19dF4q-AJHMGSyPNSOml0sar2vJemZJyxbo9siw",
    os.path.join(DROPBOX_DIR, "entrada_salvador"): "1SL3tF_BSIePacACo8_ZDGfq1yYgrstdcUhSCvdJunlo", 
    os.path.join(DROPBOX_DIR, "entrada_santos"): "15elDT9CrIHc6qx8LEVPp1ACSxNK73Idzk0j2gBJbu1Q",
    os.path.join(DROPBOX_DIR, "entrada_suape"): PLANILHA_ID, 
}

COLUNAS = [
    "CLIENTES", "DESTINO", "BOOKING", "NAVIO/VIAGEM ARMADOR",
    "VALOR DA NF", "PESO DA MERCADORIA KG", "NOTAS FISCAIS",
    "CT-E ARMADOR", "CONTAINER", "TIPO", "LACRE", "DATA DE EMBARQUE", "DEADLINE"
]