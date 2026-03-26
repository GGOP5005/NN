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

# ======================================================================
# SCRAPER 1: TECON SUAPE (Programação Geral)
# ======================================================================
def raspar_programacao_tecon():
    print(Fore.WHITE + "🌐 Acessando a Programação de Navios do Tecon Suape...")
    navios_brutos = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS, 
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        try:
            page.goto("https://www.teconsuape.com/programacao/", timeout=30000)
            page.wait_for_selector("table tbody tr", timeout=15000)
            time.sleep(3) 
            
            def extrair_tabela():
                return page.evaluate("""() => {
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
            
            dados_atuais = extrair_tabela()
            if dados_atuais: navios_brutos.extend(dados_atuais)
            
            hoje = datetime.now()
            mes_seguinte = hoje.month + 1 if hoje.month < 12 else 1
            ano_seguinte = hoje.year if hoje.month < 12 else hoje.year + 1
            
            data_str = f"{ano_seguinte:04d}-{mes_seguinte:02d}-01"
            print(Fore.WHITE + f"   📅 Expandindo busca Tecon para o mês seguinte ({mes_seguinte:02d}/{ano_seguinte})...")
            
            try:
                page.fill("input#dataini", data_str)
                page.keyboard.press("Enter")
                try: page.locator("button.btn-primary").click(timeout=2000)
                except: pass
                time.sleep(5)
                
                dados_futuros = extrair_tabela()
                if dados_futuros: navios_brutos.extend(dados_futuros)
            except Exception as e:
                print(Fore.YELLOW + f"   ⚠️ Aviso: Não foi possível expandir para o mês seguinte: {e}")
            
            navios_site = []
            vistos = set()
            
            print(Fore.CYAN + "\n📋 --- NAVIOS LIDOS NO TECON ---")
            for item in navios_brutos:
                chave_unica = f"{item['navio']}_{item['viagem']}"
                if chave_unica in vistos: continue
                vistos.add(chave_unica)
                
                etb_formatado = item['etb']
                if re.match(r'^\d{2}/\d{2}\s+\d{2}:\d{2}$', etb_formatado):
                    partes = etb_formatado.split(' ')
                    dia_mes = partes[0].split('/')
                    mes_navio = int(dia_mes[1])
                    
                    ano_navio = hoje.year
                    if mes_navio < hoje.month - 2: ano_navio += 1
                        
                    etb_formatado = f"{partes[0]}/{ano_navio} {partes[1]}"
                
                navios_site.append({
                    "navio_nome": item['navio'],
                    "viagem": item['viagem'],
                    "situacao": item['situacao'],
                    "etb_final": etb_formatado
                })
                print(Fore.WHITE + f"   🚢 Navio: {item['navio']} | Viagem: {item['viagem']} -> ETB: {etb_formatado}")
                
            print(Fore.CYAN + "-"*30 + "\n")
            return navios_site
            
        except Exception as e:
            print(Fore.RED + f"❌ Erro ao raspar o site do Tecon: {e}")
            return []
        finally:
            browser.close()

# ======================================================================
# SCRAPER 2: MAERSK / ALIANÇA (Processamento Rápido em Lote com Chrome Real)
# ======================================================================
def raspar_lote_maersk(containers):
    resultados = {}
    if not containers: return resultados

    print(Fore.MAGENTA + f"   🌐 Abrindo Chrome Real para processar {len(containers)} contêiner(es) na Maersk...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            channel="chrome", 
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            page.goto("https://www.maersk.com/tracking/", timeout=45000)
            
            try: 
                page.wait_for_selector("button.coi-banner__accept", timeout=5000)
                page.locator("button.coi-banner__accept").first.click()
                time.sleep(1)
            except: pass
            
            page.wait_for_selector("#mc-input-track-input", timeout=20000)

            for container in containers:
                try:
                    print(Fore.MAGENTA + f"      🔍 Rastreando: {container}")
                    input_field = page.locator("#mc-input-track-input")
                    
                    input_field.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    time.sleep(0.5)
                    input_field.fill(container)
                    
                    page.click("mc-button.track__search__button")
                    
                    page.wait_for_selector("span:has-text('Vessel arrival')", timeout=20000)
                    time.sleep(1)
                    
                    dados_maersk = page.evaluate(r"""() => {
                        let navio = "";
                        let data = "";
                        const spans = document.querySelectorAll('span');
                        
                        for(let i=0; i<spans.length; i++){
                            let texto = spans[i].innerText;
                            if(texto.includes('Vessel arrival')){
                                
                                let match = texto.match(/\((.*?)\)/);
                                if(match && match[1]){
                                    navio = match[1].trim();
                                } else {
                                    navio = texto.replace('Vessel arrival', '').trim();
                                }
                                
                                let parent = spans[i].parentElement;
                                while(parent && parent.tagName !== 'BODY'){
                                    let dateNode = parent.querySelector('[data-test="milestone-date"]');
                                    if(dateNode){
                                        data = dateNode.innerText.trim();
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                                if(data) break;
                            }
                        }
                        return {navio: navio, data: data};
                    }""")
                    
                    if dados_maersk and dados_maersk['data']:
                        navio_limpo = dados_maersk['navio'].replace('(', '').replace(')', '').strip()
                        data_crua = dados_maersk['data']
                        
                        meses = {"Jan":"01", "Feb":"02", "Mar":"03", "Apr":"04", "May":"05", "Jun":"06", "Jul":"07", "Aug":"08", "Sep":"09", "Oct":"10", "Nov":"11", "Dec":"12"}
                        for eng, num in meses.items():
                            if eng in data_crua:
                                data_crua = data_crua.replace(eng, num)
                                break
                                
                        match = re.search(r'(\d{1,2})\s+(\d{2})\s+(\d{4})\s+(\d{2}:\d{2})', data_crua)
                        if match:
                            data_formatada = f"{int(match.group(1)):02d}/{match.group(2)}/{match.group(3)} {match.group(4)}"
                        else:
                            data_formatada = data_crua
                            
                        print(Fore.GREEN + f"      ✔️ Encontrado: Navio {navio_limpo} | ETB {data_formatada}")
                        resultados[container] = {"navio": navio_limpo, "data": data_formatada}
                    else:
                        print(Fore.YELLOW + f"      ⚠️ Sem eventos de 'Vessel arrival' para {container}")
                        resultados[container] = None
                        
                except Exception as e:
                    print(Fore.RED + f"      ⚠️ Arquivado ou Timeout para {container}")
                    resultados[container] = None
                    try:
                        page.goto("https://www.maersk.com/tracking/", timeout=30000)
                        page.wait_for_selector("#mc-input-track-input", timeout=15000)
                    except: pass
                    
        except Exception as e:
            print(Fore.RED + f"   ⚠️ Erro crítico ao conectar com Maersk: {e}")
        finally:
            browser.close()
            return resultados

# ======================================================================
# GESTOR PRINCIPAL
# ======================================================================
def processar_planilha_e_atualizar(navios_site):
    print(Fore.WHITE + "📊 Cruzando os dados do Site com a sua Planilha...")
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    
    try:
        meses_seguros = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}
        aba_alvo = meses_seguros.get(datetime.now().month, "GERAL")
        
        sheet_metadata = service.spreadsheets().get(spreadsheetId=PLANILHA_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_id_alvo = None
        for s in sheets:
            if s.get("properties", {}).get("title", "").upper() == aba_alvo.upper():
                sheet_id_alvo = s.get("properties", {}).get("sheetId", "")
                break
        
        res = service.spreadsheets().values().get(spreadsheetId=PLANILHA_ID, range=f"{aba_alvo}!A:AZ").execute()
        linhas = res.get("values", [])
        
        if not linhas: return

        # ÍNDICES RÍGIDOS (Blindado contra erros no cabeçalho)
        idx_booking = 11      # L
        idx_navio = 12        # M
        idx_deadline = 13     # N
        idx_monitoramento = 20# U
        idx_container = 26    # AA
        
        col_letra_deadline = get_col_letter(idx_deadline)
        atualizacoes_texto = []
        atualizacoes_cores = []
        navios_atualizados = 0

        tarefas_maersk = []
        tarefas_tecon = []

        for i, linha in enumerate(linhas):
            linha_real = i + 1
            if linha_real == 1: continue 
            
            while len(linha) <= max(idx_navio, idx_deadline, idx_monitoramento, idx_booking, idx_container):
                linha.append("")
                
            # ========================================================
            # TRAVA DE SEGURANÇA: STATUS "COLETA" NA COLUNA U
            # ========================================================
            status_monitoramento = str(linha[idx_monitoramento]).upper().strip()
            if "COLETA" in status_monitoramento:
                # Se for coleta, nós ignoramos e passamos imediatamente à próxima linha da planilha
                # print(Fore.YELLOW + f"   ⚠️ [LINHA {linha_real}] Ignorado: Status na coluna U contém 'COLETA'.")
                continue 
            
            navio_planilha = str(linha[idx_navio]).strip()
            booking_planilha = str(linha[idx_booking]).upper().strip()
            container_planilha = str(linha[idx_container]).upper().strip()
            valor_atual_deadline = str(linha[idx_deadline]).strip()
            
            if booking_planilha.startswith("6AIBK") and container_planilha:
                consultar_maersk = True
                if "CANCELADO" in valor_atual_deadline.upper():
                    consultar_maersk = False
                elif valor_atual_deadline:
                    match_data = re.search(r'(\d{2}/\d{2}/\d{4})', valor_atual_deadline)
                    if match_data:
                        try:
                            data_planilha = datetime.strptime(match_data.group(1), "%d/%m/%Y")
                            if (datetime.now() - data_planilha).days > 2:
                                consultar_maersk = False
                        except: pass
                
                if consultar_maersk:
                    tarefas_maersk.append({
                        "linha_real": linha_real,
                        "container": container_planilha,
                        "navio": navio_planilha,
                        "deadline": valor_atual_deadline
                    })
            else:
                if navio_planilha:
                    tarefas_tecon.append({
                        "linha_real": linha_real,
                        "navio": navio_planilha,
                        "deadline": valor_atual_deadline
                    })

        # PROCESSAR LOTE MAERSK
        if tarefas_maersk:
            containers_unicos = list(set([t["container"] for t in tarefas_maersk]))
            resultados_maersk = raspar_lote_maersk(containers_unicos)

            for tarefa in tarefas_maersk:
                dados_site = resultados_maersk.get(tarefa["container"])
                if dados_site:
                    navio_site = dados_site['navio']
                    data_site = dados_site['data']
                    
                    if data_site and tarefa["deadline"] != data_site:
                        atualizacoes_texto.append({
                            "range": f"{aba_alvo}!{col_letra_deadline}{tarefa['linha_real']}",
                            "values": [[data_site]]
                        })
                        print(Fore.CYAN + f"   🎯 [MAERSK - L{tarefa['linha_real']}] {navio_site} -> Novo Deadline: {data_site}")
                        navios_atualizados += 1
                        
                    navio_planilha_clean = super_limpar(tarefa["navio"])
                    navio_site_clean = super_limpar(navio_site)
                    
                    if navio_planilha_clean and navio_site_clean:
                        if navio_site_clean not in navio_planilha_clean and navio_planilha_clean not in navio_site_clean:
                            print(Fore.RED + f"   ⚠️ ALERTA MAERSK (L{tarefa['linha_real']}): Navio ({tarefa['navio']}) difere do site ({navio_site}). Marcando em VERMELHO!")
                            if sheet_id_alvo is not None:
                                atualizacoes_cores.append({
                                    "repeatCell": {
                                        "range": {
                                            "sheetId": sheet_id_alvo,
                                            "startRowIndex": tarefa["linha_real"] - 1,
                                            "endRowIndex": tarefa["linha_real"],
                                            "startColumnIndex": idx_navio,
                                            "endColumnIndex": idx_navio + 1
                                        },
                                        "cell": {
                                            "userEnteredFormat": {
                                                "backgroundColor": {"red": 1.0, "green": 0.4, "blue": 0.4}
                                            }
                                        },
                                        "fields": "userEnteredFormat.backgroundColor"
                                    }
                                })

        # PROCESSAR TECON
        if navios_site and tarefas_tecon:
            for tarefa in tarefas_tecon:
                chave_planilha = super_limpar(tarefa["navio"])
                chave_viagem_planilha = limpar_viagem(tarefa["navio"])
                
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
                    if status_final_tecon and tarefa["deadline"] != status_final_tecon:
                        atualizacoes_texto.append({
                            "range": f"{aba_alvo}!{col_letra_deadline}{tarefa['linha_real']}",
                            "values": [[status_final_tecon]]
                        })
                        print(Fore.CYAN + f"   🎯 [TECON - L{tarefa['linha_real']}] {navio_match_nome} -> Novo Deadline: {status_final_tecon}")
                        navios_atualizados += 1

        # APLICA AS ALTERAÇÕES NA PLANILHA GOOGLE
        if atualizacoes_texto:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=PLANILHA_ID, 
                body={"valueInputOption": "USER_ENTERED", "data": atualizacoes_texto}
            ).execute()
            
        if atualizacoes_cores and sheet_id_alvo is not None:
            service.spreadsheets().batchUpdate(
                spreadsheetId=PLANILHA_ID, 
                body={"requests": atualizacoes_cores}
            ).execute()
            
        if atualizacoes_texto or atualizacoes_cores:
            print(Fore.GREEN + Style.BRIGHT + f"\n✅ Sincronização concluída! {navios_atualizados} deadline(s) atualizados. {len(atualizacoes_cores)} alerta(s) de navio gerados.")
        else:
            print(Fore.WHITE + "☕ Tudo sincronizado. Nenhuma mudança detetada.")

    except Exception as e:
        print(Fore.RED + f"❌ Erro ao atualizar a planilha: {e}")

def iniciar_missao_navios():
    print(Fore.BLUE + "\n" + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + f" 🚢 INICIANDO VARREDURA DE NAVIOS E TRACKING ({datetime.now().strftime('%H:%M:%S')})")
    print(Fore.BLUE + "="*70)
    
    dados_site = raspar_programacao_tecon()
    processar_planilha_e_atualizar(dados_site)
    
    print(Fore.BLUE + "-"*70)
    print(Fore.GREEN + f"🏁 Missão de Navios finalizada.\n")

if __name__ == "__main__":
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "======================================================================")
    print(Fore.BLUE + Style.BRIGHT + "                ROBÔ DE NAVIOS - TECON & MAERSK")
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