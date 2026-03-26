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

# Define o diretório base (funciona tanto no .py quanto em .exe compilado)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================================================
# 1. CARREGA CREDENCIAIS DO .ENV
# =========================================================
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)

TECON_CPF            = os.environ.get("TECON_CPF", "")
TECON_SENHA          = os.environ.get("TECON_SENHA", "")
PLANILHA_ID          = os.environ.get("PLANILHA_ID", "1nb1fZeBN4wJtHgeQ-J0DtrLhK0KomTuOGg2UI_cKcu0")
PECEM_EMAIL          = os.environ.get("PECEM_EMAIL", "")
PECEM_SENHA_EMAIL    = os.environ.get("PECEM_SENHA_EMAIL", "")

# =========================================================
# 2. CARREGA CHAVES DA I.A DO CHAVES.PY
# =========================================================
try:
    from chaves import LISTA_CHAVES_GEMINI
    print(f"✅ SUCESSO: {len(LISTA_CHAVES_GEMINI)} chaves Gemini carregadas!")
except ImportError:
    print("\n" + "="*60)
    print("❌ ERRO CRÍTICO: ARQUIVO 'chaves.py' NÃO ENCONTRADO! ❌")
    print("Certifique-se de que criou o arquivo chaves.py na mesma pasta.")
    print("="*60 + "\n")
    LISTA_CHAVES_GEMINI = []

# =========================================================
# CONFIGURAÇÕES GERAIS E CAMINHOS
# =========================================================
CNPJ_TRANSPORTADORA = "46099394000188"
HEADLESS = False
ano_atual = datetime.now().year

# --- PASTAS PRINCIPAIS ---
# DROPBOX_DIR é a pasta de ENTRADAS (usada por main.py e processor.py)
DROPBOX_DIR       = r"C:\Users\supor\Dropbox\ENTRADAS"
PASTA_ENTRADAS    = DROPBOX_DIR   # alias — ambos apontam para o mesmo lugar

# Raiz do Dropbox (pasta pai de ENTRADAS)
DROPBOX_ROOT      = os.path.dirname(DROPBOX_DIR)

# Norte Nordeste no Dropbox (usado por buscador_pdfs)
PASTA_NORTE_NORDESTE   = os.path.join(DROPBOX_ROOT, "Norte Nordeste")
PASTA_RAIZ_DOCUMENTOS  = PASTA_NORTE_NORDESTE   # buscador_pdfs faz walk aqui

PASTA_ERROS   = os.path.join(DROPBOX_DIR, "00_ERROS_DE_LEITURA")
PASTA_LOGS    = os.path.join(BASE_DIR, "Logs")

ROTEAMENTO_PORTOS = {
    os.path.join(PASTA_ENTRADAS, "entrada_manaus"):   "1ekdnK1eGvJrSkY8trB4683TMUxI0CZml1xL3PEG5uXo",
    os.path.join(PASTA_ENTRADAS, "entrada_pecem"):    "1K_2q19dF4q-AJHMGSyPNSOml0sar2vJemZJyxbo9siw",
    os.path.join(PASTA_ENTRADAS, "entrada_salvador"): "1SL3tF_BSIePacACo8_ZDGfq1yYgrstdcUhSCvdJunlo",
    os.path.join(PASTA_ENTRADAS, "entrada_santos"):   "15elDT9CrIHc6qx8LEVPp1ACSxNK73Idzk0j2gBJbu1Q",
    os.path.join(PASTA_ENTRADAS, "entrada_suape"):    PLANILHA_ID,
}

COLUNAS = [
    "CLIENTES", "DESTINO", "BOOKING", "NAVIO/VIAGEM ARMADOR",
    "VALOR DA NF", "PESO DA MERCADORIA KG", "NOTAS FISCAIS",
    "CT-E ARMADOR", "CONTAINER", "TIPO", "LACRE",
    "DATA DE EMBARQUE", "DEADLINE"
]

# =========================================================
# 3. CONFIGURAÇÕES DA API BSOFT TMS
# =========================================================
BSOFT_DOMINIO  = os.environ.get("BSOFT_DOMINIO", "nortenordeste.bsoft.app")
BSOFT_USUARIO  = os.environ.get("BSOFT_API_USER", "GABRIEL.SANTOS")
BSOFT_SENHA    = os.environ.get("BSOFT_API_PASS", "GG@p5005")
BSOFT_BASE_URL = f"https://{BSOFT_DOMINIO}/services/index.php"