import os
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
from config import BASE_DIR

init(autoreset=True)

def fazer_login_seguro():
    pasta_sessao = os.path.join(BASE_DIR, "WA_Session")
    
    print(Fore.BLUE + Style.BRIGHT + "===================================================")
    print(Fore.YELLOW + Style.BRIGHT + "        LOGIN MANUAL - WHATSAPP BUSINESS")
    print(Fore.BLUE + Style.BRIGHT + "===================================================")
    print(Fore.WHITE + "1. O navegador vai abrir na tela do WhatsApp Web.")
    print(Fore.WHITE + "2. Pegue o seu celular com o WhatsApp Business.")
    print(Fore.WHITE + "3. Vá em 'Aparelhos Conectados' e escaneie o QR Code.")
    print(Fore.WHITE + "4. Aguarde as suas conversas carregarem na tela.")
    print(Fore.BLUE + "===================================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=pasta_sessao, 
            headless=False,
            viewport={'width': 1280, 'height': 720}
        )
        page = browser.new_page()
        
        print(Fore.YELLOW + "⏳ Carregando a página de login...")
        page.goto("https://web.whatsapp.com/")
        
        # O robô vai ficar parado aqui até você dar a ordem para fechar
        input(Fore.GREEN + Style.BRIGHT + "\n👉 Pressione ENTER AQUI NESTA TELA PRETA apenas DEPOIS que tiver escaneado o QR Code e as conversas aparecerem... ")
        
        print(Fore.YELLOW + "\nSalvando a memória da sua sessão e fechando...")
        browser.close()
        print(Fore.GREEN + "✅ Sessão do WhatsApp Business salva com sucesso! O Robô Despachante já pode ser usado.")

if __name__ == "__main__":
    fazer_login_seguro()