import os
import time
import re
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import BASE_DIR, ROTEAMENTO_PORTOS
from sheets_api import executar_com_resiliencia_infinita, get_col_letter

init(autoreset=True)

# --- CONFIGURAÇÕES DE MANAUS ---
URL_MANAUS = "https://service.superterminais.com.br:8443/river/"
MANAUS_USER = "suporte@nortenordeste.com.br"
MANAUS_PASS = "Norte@2026#"

PLANILHA_MANAUS_ID = next((s_id for pasta, s_id in ROTEAMENTO_PORTOS.items() if "manaus" in pasta.lower()), None)
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def raspar_programacao_manaus():
    print(Fore.YELLOW + "🌐 Acessando o portal do Terminal Manaus (Super Terminais)...")
    navios_encontrados = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            page.goto(URL_MANAUS, timeout=60000)
            
            # 1. Login
            page.wait_for_selector("#inputEmail", timeout=15000)
            page.fill("#inputEmail", MANAUS_USER)
            page.fill("#inputPassword", MANAUS_PASS)
            page.click("button[type='submit']")
            
            # 2. Tratamento de Pop-up de Sessão Ativa
            try:
                page.wait_for_selector("p:has-text('Existe uma sessão ativa')", timeout=5000)
                print(Fore.YELLOW + "   ⚠️ Derrubando sessão anterior...")
                page.click("button[data-bs-dismiss='modal']:has-text('Confirmar')")
                time.sleep(2)
            except:
                pass 
                
            # 3. Seleção da Empresa
            try:
                print(Fore.YELLOW + "   🏢 Selecionando o perfil da Transportadora...")
                page.wait_for_selector("#dlEmpresas", timeout=10000)
                caixa_empresa = page.locator("#dlEmpresas")
                caixa_empresa.click()
                
                valor_selecao = "18570: TRANSPORTADORA NORTE NORDESTE MULTIMODAL LTDA | Documento: 46099394000188 | Perfil: CLIENTE"
                caixa_empresa.fill("")
                time.sleep(1)
                page.keyboard.type(valor_selecao, delay=20)
                time.sleep(2)
                page.keyboard.press("Enter")
                print(Fore.GREEN + "   ✅ Empresa selecionada via teclado.")
                time.sleep(3)
            except Exception as e:
                print(Fore.RED + f"   ⚠️ Erro na seleção de empresa: {e}")
                
            # 4. Navegar para Programação de Navios
            print(Fore.YELLOW + "   🚢 Acessando a tabela de Navios...")
            
            try:
                # Clica no menu de navios usando regex para pegar qualquer variação do texto
                page.locator("text=/Programação de Navios/i").first.click()
            except:
                # Fallback usando javascript direto
                page.evaluate("Array.from(document.querySelectorAll('span, a')).find(el => el.textContent.includes('Programação de Navios'))?.click();")
            
            time.sleep(6) # Espera a tabela carregar os dados no fundo
            
            # 5. Extração de Dados Inteligente (Auto-Discover)
            print(Fore.CYAN + "\n🔍 DADOS CAPTURADOS NO PORTAL:")
            print(Fore.CYAN + "-" * 60)
            
            # Espera a tabela aparecer na tela
            page.wait_for_selector("table", timeout=15000)
            
            # Descobre as colunas lendo os cabeçalhos (th)
            colunas_texto = page.locator("th").all_inner_texts()
            if not colunas_texto:
                # Se não usar 'th', tenta pegar a primeira linha 'tr'
                colunas_texto = page.locator("tr").first.locator("td, th").all_inner_texts()
                
            headers = [str(c).upper().strip() for c in colunas_texto]
            
            idx_navio, idx_viagem, idx_chegada, idx_deadline = -1, -1, -1, -1
            
            # Mapeia onde está cada informação
            for i, h in enumerate(headers):
                if "NAVIO" in h: idx_navio = i
                if "VIAGEM" in h: idx_viagem = i
                if "CHEGADA" in h or "PREVISÃO" in h or "ETA" in h: idx_chegada = i
                if "DEADLINE" in h: idx_deadline = i

            # Pega todas as linhas da tabela
            linhas = page.locator("tbody tr").all()
            if not linhas:
                linhas = page.locator("tr").all()
            
            for i, linha in enumerate(linhas):
                celulas = linha.locator("td").all_inner_texts()
                if not celulas or len(celulas) < 3: 
                    continue # Ignora linhas vazias ou de cabeçalho
                    
                try:
                    # Se não encontrou o índice pelo cabeçalho, assume colunas 0 e 1 padrão
                    nome_navio = celulas[idx_navio].strip().upper() if idx_navio != -1 else celulas[0].strip().upper()
                    viagem = celulas[idx_viagem].strip().upper() if idx_viagem != -1 and idx_viagem < len(celulas) else ""
                    chegada = celulas[idx_chegada].strip() if idx_chegada != -1 and idx_chegada < len(celulas) else ""
                    deadline = celulas[idx_deadline].strip() if idx_deadline != -1 and idx_deadline < len(celulas) else ""
                    
                    data_referencia = deadline if deadline else chegada
                    
                    if nome_navio and nome_navio != "NAVIO":
                        chave_navio = f"{nome_navio} / {viagem}" if viagem else nome_navio
                        navios_encontrados[nome_navio] = data_referencia
                        print(Fore.GREEN + f"   🛳️ Navio: {chave_navio.ljust(30)} | Data: {data_referencia}")
                except Exception as e:
                    pass

            if not navios_encontrados:
                print(Fore.RED + "   ❌ Não consegui extrair as linhas da tabela. A estrutura pode ser diferente.")
                # Debug de emergência: Imprime o HTML da tabela para podermos consertar se falhar
                html_tabela = page.locator("table").first.inner_html()
                print(Fore.WHITE + f"   [DEBUG ESTRUTURA]: {html_tabela[:500]}...")

            print(Fore.CYAN + "-" * 60 + "\n")
                    
        except Exception as e:
            print(Fore.RED + f"❌ Erro ao navegar no portal de Manaus: {e}")
        finally:
            browser.close()
            
    return navios_encontrados

def processar_planilha_manaus(navios_site):
    if not PLANILHA_MANAUS_ID or not navios_site:
        print(Fore.RED + "❌ Nenhuma informação para atualizar na Planilha.")
        return

    print(Fore.YELLOW + f"📝 Atualizando a Planilha de Manaus...")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    
    mes_atual = datetime.now().month
    meses_mapa = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}
    aba_atual = meses_mapa.get(mes_atual, "MARÇO")

    try:
        res = executar_com_resiliencia_infinita(service.spreadsheets().values().get(spreadsheetId=PLANILHA_MANAUS_ID, range=f"{aba_atual}!A:AZ"))
        linhas = res.get('values', [])
        if not linhas: return
        
        headers = [str(h).upper().strip() for h in linhas[0]]
        idx_navio = headers.index("NAVIO/VIAGEM ARMADOR") if "NAVIO/VIAGEM ARMADOR" in headers else 10 
        idx_deadline = headers.index("DEADLINE") if "DEADLINE" in headers else 11 
        col_deadline_letra = get_col_letter(idx_deadline)

        requests = []
        for i in range(1, len(linhas)):
            row = linhas[i]
            if len(row) > idx_navio:
                navio_planilha = str(row[idx_navio]).upper().strip()
                
                for navio_site, data_site in navios_site.items():
                    # O "in" aqui permite que se na planilha estiver "LOG IN POLARIS / 1234S" ele reconheça o "LOG IN POLARIS"
                    if navio_site in navio_planilha and data_site:
                        deadline_atual = str(row[idx_deadline]).strip() if len(row) > idx_deadline else ""
                        if deadline_atual != data_site:
                            requests.append({
                                "range": f"{aba_atual}!{col_deadline_letra}{i+1}",
                                "values": [[data_site]]
                            })
                        break

        if requests:
            body_values = {"valueInputOption": "USER_ENTERED", "data": requests}
            executar_com_resiliencia_infinita(service.spreadsheets().values().batchUpdate(spreadsheetId=PLANILHA_MANAUS_ID, body=body_values))
            print(Fore.GREEN + f"✅ {len(requests)} deadlines atualizados com sucesso na aba {aba_atual}!")
        else:
            print(Fore.WHITE + "✅ Todos os navios na planilha já estão com o deadline atualizado.")

    except Exception as e:
        print(Fore.RED + f"❌ Erro ao atualizar planilha: {e}")

if __name__ == "__main__":
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "=" * 70)
    print(Fore.BLUE + Style.BRIGHT + "        ROBÔ DE NAVIOS - SUPER TERMINAIS (MANAUS)")
    print(Fore.BLUE + Style.BRIGHT + "=" * 70 + "\n")
    
    dados_extraidos = raspar_programacao_manaus()
    processar_planilha_manaus(dados_extraidos)