import os
import chromadb
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DB = os.path.join(BASE_DIR, "JARVIS_CEREBRO")
cliente_chroma = chromadb.PersistentClient(path=PASTA_DB)

# Cria uma gaveta separada só para as Regras e Manuais da Empresa
colecao_regras = cliente_chroma.get_or_create_collection(name="regras_empresa")

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def menu_ensinar():
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "===================================================")
    print(Fore.BLUE + Style.BRIGHT + "        SISTEMA DE APRENDIZADO - JARVIS 3.0")
    print(Fore.BLUE + Style.BRIGHT + "===================================================\n")
    print(Fore.WHITE + "Digite a regra, política ou aviso que deseja que a I.A. memorize para sempre.")
    print(Fore.WHITE + "Ex: 'A tabela de frete da VEXA mudou. O valor para Suape agora é R$ 1200.'")
    print(Fore.YELLOW + "Digite 'sair' para encerrar.\n")

    while True:
        nova_regra = input(Fore.GREEN + "Nova Regra: ")
        if nova_regra.lower() == 'sair':
            break
        
        if nova_regra.strip():
            id_regra = f"regra_{int(datetime.now().timestamp() * 1000)}"
            data_hoje = datetime.now().strftime("%d/%m/%Y")
            
            colecao_regras.add(
                documents=[nova_regra],
                metadatas=[{"tipo": "regra_interna", "data": data_hoje, "autor": "Diretoria"}],
                ids=[id_regra]
            )
            print(Fore.CYAN + "✅ Regra injetada no córtex do Jarvis com sucesso!\n")

if __name__ == "__main__":
    menu_ensinar()