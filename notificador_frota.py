import os
import sys
import time
import subprocess
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import BASE_DIR, ROTEAMENTO_PORTOS
from sheets_api import executar_com_resiliencia_infinita
from buscador_pdfs import encontrar_pasta_container

init(autoreset=True)

# --- CONFIGURAÇÕES ---
PLANILHA_SUAPE_ID = next((s_id for pasta, s_id in ROTEAMENTO_PORTOS.items() if "suape" in pasta.lower()), None)
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

WHATSAPP_SESSION_DIR = os.path.join(BASE_DIR, "sessao_whatsapp")

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def listar_meses_alvo():
    meses_mapa = {
        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
    }
    return [meses_mapa[datetime.now().month]]

def atualizar_celula_status(service, aba, col_letra, linha, valor):
    try:
        range_atualizacao = f"{aba}!{col_letra}{linha}"
        executar_com_resiliencia_infinita(service.spreadsheets().values().update(
            spreadsheetId=PLANILHA_SUAPE_ID,
            range=range_atualizacao,
            valueInputOption="USER_ENTERED",
            body={"values": [[valor]]}
        ))
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao atualizar planilha: {e}")

# ==========================================================
# 📄 TÁTICA HUMANA: COPIAR ARQUIVO (CTRL+C) VIA WINDOWS
# ==========================================================
def copiar_arquivos_windows(arquivos):
    if isinstance(arquivos, str): arquivos = [arquivos]
    caminhos = []
    for arq in arquivos:
        abs_path = os.path.abspath(arq).replace("'", "''")
        caminhos.append(f"'{abs_path}'")
    lista_ps = ",".join(caminhos)
    comando = f'powershell -command "Set-Clipboard -Path {lista_ps}"'
    subprocess.run(comando, shell=True, creationflags=0x08000000 if sys.platform == 'win32' else 0)

# ==========================================================
# 🧠 MAPA DE GRUPOS (CORRIGIDO PARA O NOME EXATO DO WHATSAPP)
# ==========================================================
def identificar_grupo_frota(nome_motorista):
    nome = str(nome_motorista).upper().strip()
    # Letras maiúsculas e minúsculas EXATAMENTE como aparecem no WhatsApp!
    if "DJHON" in nome or "DJOHN" in nome: return "001 Norte Nordeste"
    if "DAYVSON" in nome: return "002 Norte Nordeste"
    if "BRUNO" in nome: return "003 Norte Nordeste"
    if "JOSE" in nome or "JOSÉ" in nome or "JERONIMO" in nome or "JERÔNIMO" in nome: return "005 Norte Nordeste"
    if "THIAGO" in nome: return "006 Norte Nordeste"
    return None

def buscar_entregas_ok():
    print(Fore.YELLOW + "📊 Lendo a Planilha de Suape em busca de status 'OK' na Coluna I...")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    meses_alvo = listar_meses_alvo()
    
    entregas_pendentes = []

    for aba_atual in meses_alvo:
        try:
            res = executar_com_resiliencia_infinita(service.spreadsheets().values().get(spreadsheetId=PLANILHA_SUAPE_ID, range=f"{aba_atual}!A:AZ"))
            linhas = res.get('values', [])
            if not linhas: continue
            
            headers = [str(h).upper().strip() for h in linhas[0]]
            
            idx_monit = 8 
            col_monit_letra = "I"
            
            idx_cont = headers.index("CONTAINER") if "CONTAINER" in headers else (headers.index("CONTÊINER") if "CONTÊINER" in headers else 30)
            
            idx_motorista = -1
            for t in ["MOTORISTA", "DESPACHANTE", "NOME"]:
                if t in headers:
                    idx_motorista = headers.index(t)
                    break

            for i in range(1, len(linhas)):
                linha_dados = linhas[i]
                
                while len(linha_dados) < max(idx_monit, idx_cont, idx_motorista) + 1:
                    linha_dados.append("")
                    
                status = str(linha_dados[idx_monit]).upper().strip()
                container = str(linha_dados[idx_cont]).upper().strip()
                nome_motorista = str(linha_dados[idx_motorista]).strip() if idx_motorista != -1 else ""
                
                linha_completa = " ".join([str(celula).upper() for celula in linha_dados])

                if status in ["OK", "LIBERADO"]:
                    if "FROTA" in linha_completa:
                        grupo_zap = identificar_grupo_frota(nome_motorista)
                        
                        if container and grupo_zap:
                            entregas_pendentes.append({
                                "aba": aba_atual,
                                "linha": i + 1,
                                "container": container,
                                "nome_grupo": grupo_zap,
                                "col_monit": col_monit_letra,
                                "service": service
                            })
                    else:
                        print(Fore.YELLOW + f"   ⏭️ Contêiner {container} com 'OK' ignorado (Não pertence à FROTA).")
                            
        except Exception as e:
            print(Fore.RED + f"⚠️ Erro ao ler a aba {aba_atual}: {e}")

    return entregas_pendentes

def enviar_whatsapp_frota(entregas):
    if not entregas:
        print(Fore.GREEN + "✅ Nenhuma entrega da FROTA com status 'OK' pendente de envio no momento.")
        return

    print(Fore.YELLOW + f"🚀 Encontradas {len(entregas)} liberações da FROTA prontas para envio!")
    
    os.makedirs(WHATSAPP_SESSION_DIR, exist_ok=True)

    with sync_playwright() as p:
        print(Fore.WHITE + "🌐 Abrindo WhatsApp Web...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=WHATSAPP_SESSION_DIR,
            headless=False,
            channel="chrome",
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        page.goto("https://web.whatsapp.com/", timeout=60000)
        
        print(Fore.YELLOW + "⏳ Aguardando autenticação do WhatsApp...")
        try:
            page.wait_for_selector('div[contenteditable="true"][data-tab="3"]', timeout=60000)
            print(Fore.GREEN + "✅ WhatsApp Web autenticado!")
            time.sleep(3)
        except:
            print(Fore.RED + "❌ Timeout ao logar no WhatsApp.")
            context.close()
            return

        for item in entregas:
            cont = item["container"]
            grupo = item["nome_grupo"]
            
            print(Fore.CYAN + f"\n📦 Processando envio para: {cont} -> Grupo: [{grupo}]")
            
            pasta_container = encontrar_pasta_container(cont)
            lista_pdfs = []
            
            if pasta_container:
                for ficheiro in os.listdir(pasta_container):
                    if ficheiro.lower().endswith('.pdf'):
                        lista_pdfs.append(os.path.join(pasta_container, ficheiro))
            
            if not lista_pdfs:
                print(Fore.RED + f"   ⚠️ Nenhum PDF encontrado na pasta. Pulando...")
                continue
                
            print(Fore.GREEN + f"   📄 Encontrados {len(lista_pdfs)} PDF(s).")
            
            try:
                # ===============================================================
                # 1. ENTRAR NA CONVERSA (Localizando pelo título exato)
                # ===============================================================
                print(Fore.YELLOW + f"   🔍 Localizando grupo '{grupo}'...")
                
                # Procura a barra de pesquisa para trazer o contato à tona
                busca = page.locator('div[contenteditable="true"][data-tab="3"]')
                busca.click()
                busca.fill("")
                time.sleep(0.5)
                busca.fill(grupo)
                time.sleep(2)
                
                # AGORA SIM! Ele vai achar com as maiúsculas e minúsculas corretas
                chat_alvo = page.locator(f'span[title="{grupo}"]').first
                
                if chat_alvo.is_visible():
                    chat_alvo.click()
                    time.sleep(2)
                else:
                    print(Fore.RED + f"   ❌ O grupo {grupo} não apareceu!")
                    continue

                # ===============================================================
                # 2. COLAR OS PDFs COM CTRL+V E ENVIAR
                # ===============================================================
                print(Fore.YELLOW + "   📎 Usando CTRL+V para colar PDFs...")
                copiar_arquivos_windows(lista_pdfs)
                
                caixa_texto_envio = page.locator('footer div[contenteditable="true"]').first
                caixa_texto_envio.click()
                time.sleep(1)
                
                page.keyboard.press('Control+V')
                time.sleep(4) 
                
                page.locator('span[data-icon="send"], span[data-icon="wds-ic-send-filled"]').first.click(timeout=10000)
                time.sleep(5 + (len(lista_pdfs) * 2)) 
                
                # ===============================================================
                # 3. ENVIAR A MENSAGEM DE TEXTO 
                # ===============================================================
                print(Fore.YELLOW + "   💬 Enviando mensagem...")
                mensagem = f"Olá! Segue a documentação de liberação do contêiner *{cont}*.\nBoa viagem e conduza com segurança! 🚛"
                
                caixa_texto_envio.click()
                time.sleep(1)
                caixa_texto_envio.fill(mensagem)
                page.keyboard.press('Enter')
                time.sleep(2)
                
                print(Fore.GREEN + f"   ✅ Mensagem enviada com sucesso no grupo {grupo}!")
                
                # ===============================================================
                # 4. ATUALIZAR PLANILHA
                # ===============================================================
                print(Fore.YELLOW + "   📝 Marcando como 'ENVIADO' na Coluna I...")
                atualizar_celula_status(item["service"], item["aba"], item["col_monit"], item["linha"], "ENVIADO")
                
                # Limpa a caixa de pesquisa para não atrapalhar o próximo
                try:
                    page.locator('button[aria-label="Fechar pesquisa"], span[data-icon="x"]').first.click()
                except: pass

            except Exception as e:
                print(Fore.RED + f"   ❌ Erro ao enviar para {grupo}: {e}")

        context.close()

if __name__ == "__main__":
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "=" * 70)
    print(Fore.BLUE + Style.BRIGHT + "       ROBÔ DE NOTIFICAÇÃO WHATSAPP - FROTA SUAPE")
    print(Fore.BLUE + Style.BRIGHT + "=" * 70 + "\n")
    
    lista_entregas = buscar_entregas_ok()
    enviar_whatsapp_frota(lista_entregas)