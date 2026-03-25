import os
import time
import re
import schedule
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Imports diretos da arquitetura plana
from config import BASE_DIR, PLANILHA_ID, HEADLESS

init(autoreset=True)

CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_col_letter(idx):
    result = ""
    n = idx + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

def super_limpar(texto):
    t = re.sub(r'[^A-Z0-9]', '', str(texto).upper())
    t = t.replace('O', '0').replace('I', '1')
    return t

def limpar_viagem(viagem_texto):
    t = super_limpar(viagem_texto)
    if len(t) > 2 and t[-1] in ['N', 'S', 'E', 'W']:
        t = t[:-1]
    return t

def raspar_programacao_tecon():
    print(Fore.WHITE + "🌐 Acessando a Programação de Navios do Tecon Suape...")
    navios_site = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        try:
            page.goto("https://www.teconsuape.com/programacao/", timeout=30000)
            
            page.wait_for_selector("table tbody tr", timeout=15000)
            time.sleep(3) 
            
            dados = page.evaluate("""() => {
                const linhas = Array.from(document.querySelectorAll('table tbody tr'));
                return linhas.map(tr => {
                    const cols = Array.from(tr.querySelectorAll('td'));
                    if(cols.length < 11) return null;
                    
                    let situacao_val = cols[1].innerText.trim();
                    let ata_val = cols[2].innerText.trim();
                    let etb_val = cols[3].innerText.trim();
                    let navio_val = cols[9].innerText.trim();
                    let viagem_val = cols[10].innerText.trim();
                    
                    if (etb_val === "-" || etb_val === "") {
                        etb_val = ata_val;
                    }
                    
                    return {
                        situacao: situacao_val,
                        etb: etb_val,
                        navio: navio_val,
                        viagem: viagem_val
                    }
                }).filter(item => item !== null && item.navio !== "" && (item.etb.includes('/') || item.situacao.toUpperCase().includes('CANCELADO')));
            }""")
            
            ano_atual = str(datetime.now().year)
            
            print(Fore.CYAN + "\n📋 --- NAVIOS LIDOS NO SITE ---")
            for item in dados:
                etb_formatado = item['etb']
                if re.match(r'^\d{2}/\d{2}\s+\d{2}:\d{2}$', etb_formatado):
                    partes = etb_formatado.split(' ')
                    etb_formatado = f"{partes[0]}/{ano_atual} {partes[1]}"
                
                navios_site.append({
                    "navio_nome": item['navio'],
                    "viagem": item['viagem'],
                    "situacao": item['situacao'],
                    "etb_final": etb_formatado
                })
                print(Fore.WHITE + f"   🚢 Navio: {item['navio']} | Viagem: {item['viagem']} -> ETB: {etb_formatado}")
                
            print(Fore.CYAN + "-"*30 + "\n")
            print(Fore.GREEN + f"✅ Foram encontrados {len(navios_site)} navios válidos na programação.")
            return navios_site
            
        except Exception as e:
            print(Fore.RED + f"❌ Erro ao raspar o site do Tecon: {e}")
            return []
        finally:
            browser.close()

def processar_planilha_e_atualizar(navios_site):
    if not navios_site:
        return
        
    print(Fore.WHITE + "📊 Cruzando os dados do Site com a sua Planilha...")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    
    try:
        meses_seguros = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}
        aba_alvo = meses_seguros.get(datetime.now().month, "GERAL")
        
        res = service.spreadsheets().values().get(spreadsheetId=PLANILHA_ID, range=f"{aba_alvo}!A:Z").execute()
        linhas = res.get("values", [])
        
        if not linhas: return

        cabecalho = [str(c).upper().strip() for c in linhas[0]]
        
        try: idx_navio = cabecalho.index("NAVIO/VIAGEM ARMADOR")
        except ValueError:
            print(Fore.RED + "❌ A coluna 'NAVIO/VIAGEM ARMADOR' não foi encontrada!")
            return
            
        idx_deadline = -1
        idx_monitoramento = -1
        
        for i, nome_col in enumerate(cabecalho):
            if "DEADLINE" in nome_col or "DEAD LINE" in nome_col:
                idx_deadline = i
            elif "MONITORAMENTO" in nome_col:
                idx_monitoramento = i
                
        if idx_deadline == -1:
            print(Fore.RED + "❌ A coluna 'DEADLINE' não foi encontrada no cabeçalho!")
            return

        col_letra_deadline = get_col_letter(idx_deadline)
        atualizacoes_batch = []
        navios_atualizados = 0

        for i, linha in enumerate(linhas):
            linha_real = i + 1
            if linha_real == 1: continue 
            
            if idx_monitoramento != -1 and len(linha) > idx_monitoramento:
                status_monitoramento = str(linha[idx_monitoramento]).upper().strip()
                if "COLETA" in status_monitoramento:
                    continue 
            
            if len(linha) > idx_navio:
                navio_planilha = str(linha[idx_navio]).strip()
                
                if navio_planilha:
                    chave_planilha = super_limpar(navio_planilha)
                    chave_viagem_planilha = limpar_viagem(navio_planilha)
                    
                    match_encontrado = False
                    status_final_tecon = ""
                    navio_match_nome = ""
                    
                    for n_site in navios_site:
                        n_site_clean = super_limpar(n_site['navio_nome'])
                        v_site_clean = limpar_viagem(n_site['viagem'])
                        v_site_sem_zero = v_site_clean.lstrip('0')
                        
                        if n_site_clean in chave_planilha:
                            if v_site_clean in chave_viagem_planilha or (v_site_sem_zero and v_site_sem_zero in chave_viagem_planilha):
                                match_encontrado = True
                                status_final_tecon = "CANCELADO" if "CANCELADO" in n_site['situacao'].upper() else n_site['etb_final']
                                navio_match_nome = f"{n_site['navio_nome']} {n_site['viagem']}"
                                break
                    
                    if match_encontrado:
                        valor_atual = str(linha[idx_deadline]).strip() if len(linha) > idx_deadline else ""
                        
                        if status_final_tecon and valor_atual != status_final_tecon:
                            atualizacoes_batch.append({
                                "range": f"{aba_alvo}!{col_letra_deadline}{linha_real}",
                                "values": [[status_final_tecon]]
                            })
                            print(Fore.CYAN + f"   🎯 [LINHA {linha_real}] {navio_match_nome} -> Novo Deadline: {status_final_tecon}")
                            navios_atualizados += 1

        if atualizacoes_batch:
            body = {"valueInputOption": "USER_ENTERED", "data": atualizacoes_batch}
            service.spreadsheets().values().batchUpdate(spreadsheetId=PLANILHA_ID, body=body).execute()
            print(Fore.GREEN + Style.BRIGHT + f"\n✅ {navios_atualizados} navio(s) atualizado(s) na planilha com sucesso!")
        else:
            print(Fore.WHITE + "☕ Nenhum deadline novo ou alterado para atualizar.")

    except Exception as e:
        print(Fore.RED + f"❌ Erro ao atualizar a planilha: {e}")

def iniciar_missao_navios():
    print(Fore.BLUE + "\n" + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + f" 🚢 INICIANDO VARREDURA DE NAVIOS ({datetime.now().strftime('%H:%M:%S')})")
    print(Fore.BLUE + "="*70)
    
    dados_site = raspar_programacao_tecon()
    processar_planilha_e_atualizar(dados_site)
    
    print(Fore.BLUE + "-"*70)
    print(Fore.GREEN + f"🏁 Missão de Navios finalizada.\n")

if __name__ == "__main__":
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "======================================================================")
    print(Fore.BLUE + Style.BRIGHT + "                ROBÔ DE NAVIOS - TECON SUAPE")
    print(Fore.BLUE + Style.BRIGHT + "======================================================================\n")
    print(Fore.GREEN + "⏰ Relógio Programado para: 09:00, 12:00, 16:00, 20:00")
    print(Fore.WHITE + "💤 O sistema está em modo de escuta.\n")
    
    schedule.every().day.at("09:00").do(iniciar_missao_navios)
    schedule.every().day.at("12:00").do(iniciar_missao_navios)
    schedule.every().day.at("16:00").do(iniciar_missao_navios)
    schedule.every().day.at("20:00").do(iniciar_missao_navios)

    iniciar_missao_navios()

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print(Fore.RED + "\n🛑 Encerrando o Monitor de Navios.")