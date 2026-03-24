import os
import time
import re
import unicodedata
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import BASE_DIR, ROTEAMENTO_PORTOS, HEADLESS
from sheets_api import executar_com_resiliencia_infinita, MAPA_MESES, get_col_letter
from buscador_pdfs import encontrar_pasta_container
from extrator_pdf import extrair_texto_pdf

init(autoreset=True)

# --- CONFIGURAÇÕES DO TECON SALVADOR ---
URL_SALVADOR = "https://portal.teconsvonline.com.br/login"
EMAIL_SALVADOR = "WSNRTMNC"
SENHA_SALVADOR = "SAWFUS0"

# Encontra o ID da planilha de Salvador dinamicamente
PLANILHA_SALVADOR_ID = next((s_id for pasta, s_id in ROTEAMENTO_PORTOS.items() if "salvador" in pasta.lower()), None)

CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')

def extrair_chave_cte_44_digitos(pasta_container):
    """Varre os PDFs da pasta do contêiner procurando uma sequência exata de 44 números"""
    if not pasta_container or not os.path.exists(pasta_container):
        return None
    
    for arquivo in os.listdir(pasta_container):
        if arquivo.lower().endswith('.pdf'):
            caminho_completo = os.path.join(pasta_container, arquivo)
            texto_pdf = extrair_texto_pdf(caminho_completo)
            texto_so_numeros = re.sub(r'\D', '', texto_pdf)
            matches = re.findall(r'\d{44}', texto_so_numeros)
            if matches:
                return matches[0] 
    return None

def buscar_containers_salvador(service, aba):
    """Busca contêineres na planilha de Salvador que precisam ser processados"""
    alvos = []
    try:
        res = executar_com_resiliencia_infinita(
            service.spreadsheets().get(spreadsheetId=PLANILHA_SALVADOR_ID, ranges=[f"{aba}!A:AZ"], includeGridData=True)
        )
        grid = res['sheets'][0]['data'][0]
        row_data = grid.get('rowData', [])
        if not row_data: return alvos
        
        def obter_val(celula):
            if not isinstance(celula, dict): return ""
            v = celula.get('formattedValue', "")
            return "" if v is None else str(v).strip().upper()

        headers = [obter_val(c) for c in row_data[0].get('values', [])]
        
        idx_container = headers.index("CONTAINER") if "CONTAINER" in headers else -1
        idx_monitoramento = headers.index("MONITORAMENTO") if "MONITORAMENTO" in headers else -1
        idx_saida = headers.index("SAIDA DO PORTO") if "SAIDA DO PORTO" in headers else headers.index("SAÍDA DO PORTO") if "SAÍDA DO PORTO" in headers else -1
        idx_cte_armador = headers.index("CT-E ARMADOR") if "CT-E ARMADOR" in headers else -1
        idx_booking = headers.index("BOOKING") if "BOOKING" in headers else -1

        if idx_container == -1: return alvos

        for i in range(1, len(row_data)):
            linha_real = i + 1
            cells = row_data[i].get('values', [])
            
            while len(cells) < 30: cells.append({})
            
            container = obter_val(cells[idx_container])
            monitoramento = obter_val(cells[idx_monitoramento]) if idx_monitoramento != -1 else ""
            cte_armador = obter_val(cells[idx_cte_armador]) if idx_cte_armador != -1 else ""
            navio_saida = obter_val(cells[idx_saida]) if idx_saida != -1 else ""
            
            if container and len(container) >= 10:
                monitoramento_limpo = remover_acentos(monitoramento).upper()
                
                if monitoramento == "" or (monitoramento == "FALTA BOOKING" and cte_armador) or "NAO LIBERADO" in monitoramento_limpo:
                    alvos.append({
                        "linha": linha_real,
                        "container": re.sub(r'[^A-Z0-9]', '', container),
                        "cte_armador": cte_armador,
                        "navio_saida": navio_saida,
                        "monitoramento": monitoramento,
                        "col_monitoramento": get_col_letter(idx_monitoramento) if idx_monitoramento != -1 else "R",
                        "col_saida": get_col_letter(idx_saida) if idx_saida != -1 else "M",
                        "col_booking": get_col_letter(idx_booking) if idx_booking != -1 else "K"
                    })
        return alvos
    except Exception as e:
        print(Fore.RED + f"❌ Erro ao ler planilha de Salvador: {e}")
        return []

def atualizar_celula_salvador(service, aba, coluna_letra, linha, valor):
    try:
        range_att = f"{aba}!{coluna_letra}{linha}"
        executar_com_resiliencia_infinita(
            service.spreadsheets().values().update(
                spreadsheetId=PLANILHA_SALVADOR_ID, 
                range=range_att, 
                valueInputOption="USER_ENTERED", 
                body={"values": [[valor]]}
            )
        )
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao atualizar planilha: {e}")

# =====================================================================
# 🤖 NAVEGAÇÃO HUMANA (CLIQUE NOS MENUS)
# =====================================================================
def clicar_menu_lateral(page, nome_pai, nome_filho):
    """Abre a gaveta do menu lateral apenas se o filho não estiver visível e clica no filho"""
    submenu = page.locator(f'span.sidebar-label:has-text("{nome_filho}")').first
    if not submenu.is_visible():
        page.locator(f'span.sidebar-label:has-text("{nome_pai}")').first.click()
        time.sleep(1.5) # Tempo para a animação do menu abrir
    submenu.click()
    time.sleep(2.0) # Tempo para a página carregar após o clique

# =====================================================================
# 🤖 ROBÔ PLAYWRIGHT - TECON SALVADOR (WILSON SONS)
# =====================================================================
def processar_salvador():
    if not PLANILHA_SALVADOR_ID:
        print(Fore.RED + "❌ Planilha de Salvador não configurada no ROTEAMENTO_PORTOS.")
        return

    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    
    mes_atual = datetime.now().month
    aba_atual = MAPA_MESES.get(mes_atual, "MARÇO")
    
    print(Fore.BLUE + "===================================================")
    print(Fore.BLUE + "        ROBÔ TECON SALVADOR (WILSON SONS)")
    print(Fore.BLUE + "===================================================\n")
    
    alvos = buscar_containers_salvador(service, aba_atual)
    if not alvos:
        print(Fore.YELLOW + "👍 Nenhum contêiner pendente em Salvador no momento.")
        return
        
    print(Fore.CYAN + f"🎯 Encontrados {len(alvos)} contêiner(es) para processar.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        
        try:
            # 1. LOGIN
            print(Fore.WHITE + "⏳ Acessando portal Tecon Salvador...")
            page.goto(URL_SALVADOR)
            page.wait_for_selector('input.noneCase', timeout=20000)
            
            page.locator('input[type="text"].noneCase').fill(EMAIL_SALVADOR)
            page.locator('input[type="password"].noneCase').fill(SENHA_SALVADOR)
            page.keyboard.press('Enter')
            
            page.wait_for_selector('span.sidebar-label:has-text("Consultas")', timeout=20000)
            print(Fore.GREEN + "✅ Login efetuado com sucesso!")
            time.sleep(2)

            for alvo in alvos:
                container = alvo['container']
                linha = alvo['linha']
                monitoramento_atual = remover_acentos(alvo.get('monitoramento', '')).upper()
                print(Fore.MAGENTA + f"\n📦 Processando Contêiner: {container}")
                
                # 2. CONSULTAR SE ESTÁ NO TERMINAL (VIA MENU)
                print(Fore.WHITE + "   🔎 Navegando no menu para consultar contêiner...")
                clicar_menu_lateral(page, "Consultas", "Containers")
                
                input_busca = page.locator('input[name="Cód. Container"]')
                input_busca.wait_for(state="visible", timeout=15000)
                input_busca.fill("")
                input_busca.fill(container)
                page.locator('button.btn-filtrar:has-text("Filtrar")').click()
                time.sleep(3)
                
                # Verifica Status
                if page.locator('span.situacao.no-terminal:has-text("No terminal")').is_visible():
                    print(Fore.GREEN + "   ✅ Contêiner NO TERMINAL!")
                    
                    # 3. PEGAR O CÓDIGO DO NAVIO (SAÍDA DO PORTO)
                    if not alvo['navio_saida']:
                        print(Fore.WHITE + "   👁️ Extraindo código do Navio (Evo)...")
                        page.locator('b:has-text("VER DETALHES")').first.click()
                        time.sleep(2)
                        
                        label_evo = page.locator('label.label-secondary').first.inner_text()
                        codigo_navio = label_evo.split('-')[0].strip() 
                        
                        if codigo_navio:
                            print(Fore.CYAN + f"   🚢 Código de Navio Extraído: {codigo_navio}")
                            atualizar_celula_salvador(service, aba_atual, alvo['col_saida'], linha, codigo_navio)
                            alvo['navio_saida'] = codigo_navio
                        
                        page.keyboard.press('Escape') 
                        time.sleep(1)

                    if not alvo.get('monitoramento'):
                        atualizar_celula_salvador(service, aba_atual, alvo['col_monitoramento'], linha, "FALTA BOOKING")
                    
                    # 4. SOLICITAR LIBERAÇÃO (CABOTAGEM) SE TIVER O CTE
                    if alvo['cte_armador'] and alvo['navio_saida'] and "NAO LIBERADO" not in monitoramento_atual:
                        print(Fore.WHITE + "   📑 Navegando para Nova Liberação de Cabotagem...")
                        
                        pasta_local = encontrar_pasta_container(container)
                        chave_44 = extrair_chave_cte_44_digitos(pasta_local)
                        
                        if not chave_44:
                            print(Fore.YELLOW + "   ⚠️ Chave de Acesso (44 dígitos) não encontrada nos PDFs. Pulando emissão.")
                            continue
                            
                        print(Fore.GREEN + f"   🔑 Chave CTE Encontrada: {chave_44}")
                        
                        # CLICA NO MENU EM VEZ DE URL DIRETA
                        clicar_menu_lateral(page, "Liberação Documental", "Cabotagem")
                        
                        # Clica no botão de Nova Liberação
                        btn_nova_liberacao = page.locator('button.btn-secondary:has-text("Nova Liberação")')
                        btn_nova_liberacao.wait_for(state="visible", timeout=10000)
                        btn_nova_liberacao.click()
                        time.sleep(3) 
                        
                        try:
                            print(Fore.WHITE + "   ✍️ Preenchendo formulário React...")
                            input_navio = page.locator('input[id^="react-select-"][type="text"]').first
                            input_navio.fill(alvo['navio_saida'])
                            time.sleep(1.5)
                            page.keyboard.press('Enter')
                            
                            inputs_form = page.locator('input.form-control').all()
                            
                            for inp in inputs_form:
                                maxlength = inp.get_attribute('maxlength')
                                if maxlength == "44":
                                    inp.fill(chave_44)
                                    break
                            
                            page.locator('input[placeholder=""]').nth(0).fill(alvo['cte_armador']) 
                            page.locator('input[placeholder=""]').nth(1).fill(container) 
                            
                            input_regime = page.locator('input[id^="react-select-"][type="text"]').nth(1)
                            input_regime.fill("Porta / Porto")
                            time.sleep(1)
                            page.keyboard.press('Enter')
                            
                            page.locator('input[type="text"]').last.fill("grupo@nortenordeste.com.br")
                            
                            page.locator('label.btn-modal-confirmar:has-text("SALVAR")').click()
                            print(Fore.GREEN + "   ✅ Liberação Salva com Sucesso!")
                            time.sleep(3)
                            
                        except Exception as ef:
                            print(Fore.RED + f"   ❌ Erro ao preencher formulário de liberação: {ef}")
                            continue
                    elif "NAO LIBERADO" in monitoramento_atual:
                        print(Fore.WHITE + "   ⏭️ O passe já foi emitido antes. Pulando para checagem de status...")

                    # 5. VERIFICAR SE FOI LIBERADO E PEGAR O BOOKING
                    if alvo['navio_saida']:
                        print(Fore.WHITE + "   🔎 Navegando para checar status da Cabotagem...")
                        clicar_menu_lateral(page, "Liberação Documental", "Cabotagem")
                        
                        input_navio_filtro = page.locator('input[id^="react-select-"][type="text"]').first
                        input_navio_filtro.wait_for(state="visible")
                        input_navio_filtro.fill(alvo['navio_saida'])
                        time.sleep(1.5)
                        page.keyboard.press('Enter')
                        
                        page.locator('button.btn-filtrar:has-text("Filtrar")').click()
                        time.sleep(3)
                        
                        if page.locator('.situacao-btn.liberado').first.is_visible():
                            print(Fore.GREEN + "   ✅ Status: LIBERADO!")
                            
                            tds = page.locator('td').all_inner_texts()
                            booking_lido = ""
                            for td_text in tds:
                                td_clean = td_text.strip()
                                if len(td_clean) > 8 and any(c.isalpha() for c in td_clean) and any(c.isdigit() for c in td_clean):
                                    if "EVO" not in td_clean: 
                                        booking_lido = td_clean
                                        break
                                        
                            if booking_lido:
                                print(Fore.CYAN + f"   🎫 Booking Capturado: {booking_lido}")
                                atualizar_celula_salvador(service, aba_atual, alvo['col_booking'], linha, booking_lido)
                                atualizar_celula_salvador(service, aba_atual, alvo['col_monitoramento'], linha, "LIBERADO")
                            else:
                                print(Fore.YELLOW + "   ⚠️ Liberado, mas não consegui ler a string do Booking na tabela.")
                                atualizar_celula_salvador(service, aba_atual, alvo['col_monitoramento'], linha, "LIBERADO")
                        else:
                            print(Fore.YELLOW + "   ⏳ Ainda não está LIBERADO (Aguardando análise da Wilson Sons).")
                            if "NAO LIBERADO" not in monitoramento_atual:
                                atualizar_celula_salvador(service, aba_atual, alvo['col_monitoramento'], linha, "NÃO LIBERADO")
                            
                else:
                    print(Fore.YELLOW + "   ⚠️ Contêiner não está no terminal. Pulando...")
                    
        except Exception as e:
            print(Fore.RED + f"\n❌ Erro crítico no Playwright (Salvador): {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    processar_salvador()