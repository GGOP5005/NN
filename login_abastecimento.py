import os
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_SESSAO = os.path.join(BASE_DIR, "WA_Session_Abastecimento")
os.makedirs(PASTA_SESSAO, exist_ok=True)

print("=" * 50)
print("  LOGIN WHATSAPP — ROBÔ ABASTECIMENTO")
print("=" * 50)
print("1. O Chrome vai abrir com o WhatsApp Web")
print("2. Escaneie o QR Code com seu celular")
print("3. Aguarde as conversas carregarem")
print("4. Volte aqui e pressione ENTER")
print("=" * 50)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PASTA_SESSAO,
        headless=False,
        viewport={"width": 1280, "height": 720},
    )
    page = browser.new_page()
    page.goto("https://web.whatsapp.com/")
    input("\n>>> Pressione ENTER depois de escanear o QR Code e as conversas aparecerem...")
    browser.close()

print("\n✅ Sessão salva! Agora pode rodar o teste de abastecimento.")