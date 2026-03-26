from playwright.sync_api import sync_playwright
import time
import unicodedata
import base64
import re
import os
import tempfile
import requests
from datetime import datetime
from colorama import init, Fore, Style

# Importações da arquitetura atual
from config import TECON_CPF, TECON_SENHA, HEADLESS, CNPJ_TRANSPORTADORA
from buscador_pdfs import encontrar_pasta_container, classificar_e_extrair_pdfs
from extrator_pdf import extrair_texto_pdf

init(autoreset=True)

def remover_acentos(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFD', texto)
    return texto.encode('ascii', 'ignore').decode('utf-8')

def login_tecon(page):
    print("🚀 Acessando portal Tecon Suape...")
    try:
        page.goto("https://www.teconsuape.com/portalservicos/#!/login")
        page.wait_for_selector("input[placeholder='CPF']", timeout=15000)
        page.fill("input[placeholder='CPF']", TECON_CPF)
        page.fill("input[placeholder='Senha']", TECON_SENHA)
        page.click("button:has-text('ENTRAR')")
        page.wait_for_selector("text=Agendamentos", timeout=20000)
        return True
    except: return False

def fechar_popups_tecon(page):
    try:
        botoes_ok = page.locator("button:has-text('OK')").all()
        for btn in botoes_ok:
            if btn.is_visible():
                btn.click()
                time.sleep(0.5)
        page.keyboard.press("Escape")
    except: pass 

def limpar_conteineres_extras(page, container_alvo):
    print(Fore.YELLOW + f"   ⏳ CT-e Multi-contêiner: Removendo carga extra (Mantendo apenas {container_alvo})...")
    try:
        page.evaluate(f"""
            const alvo = '{container_alvo}'.replace(/\\s/g, '').toUpperCase();
            const botoes = document.querySelectorAll("a[data-ng-click*='removeContainer']");
            
            botoes.forEach(btn => {{
                let parent = btn.parentElement;
                let meuInput = null;
                while (parent && parent.tagName !== 'BODY') {{
                    let inputs = parent.querySelectorAll("input[name='containerNbr']");
                    if (inputs.length === 1) {{
                        meuInput = inputs[0]; 
                        break;
                    }} else if (inputs.length > 1) {{
                        break; 
                    }}
                    parent = parent.parentElement;
                }}
                if (meuInput) {{
                    let valor = meuInput.value.replace(/\\s/g, '').toUpperCase();
                    if (!valor.includes(alvo)) {{
                        btn.click(); 
                    }}
                }} else {{
                    btn.click();
                }}
            }});
        """)
        time.sleep(3) 
        print(Fore.GREEN + f"   ✅ Limpeza concluída. Lista pronta!")
    except Exception as e:
        print(Fore.RED + f"   ⚠️ Falha ao tentar limpar a lista: {e}")

# =========================================================
# FASE 1: CONSULTAR SE CHEGOU NO PORTO
# =========================================================
def processar_lote_tecon(lista_containers):
    resultados = {}
    if not lista_containers: return resultados
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        try:
            if login_tecon(page):
                page.goto("https://www.teconsuape.com/portalservicos/#!/agendamentos/novo/conteiner")
                page.wait_for_selector("input[type='text']", timeout=15000)
                time.sleep(1)
                for numero in lista_containers:
                    try:
                        print(f"🔍 Fase 1 | Verificando: {numero}")
                        input_field = page.locator("input[type='text']").first
                        input_field.fill("") 
                        input_field.type(numero, delay=50)
                        page.click("button:has-text('INCLUIR')")
                        time.sleep(5) 
                        texto = remover_acentos(page.locator("body").inner_text()).lower()
                        if any(x in texto for x in ["nao disponivel", "nao encontrado", "erro"]):
                            resultados[numero] = "EM_TRANSITO"
                        elif any(x in texto for x in ["confirmar agendamento", "transportadora", "selecionar"]):
                            resultados[numero] = "DISPONIVEL"
                            page.goto("https://www.teconsuape.com/portalservicos/#!/agendamentos/novo/conteiner")
                            time.sleep(2)
                            page.wait_for_selector("input[type='text']", timeout=15000)
                        else: resultados[numero] = "EM_TRANSITO"
                        fechar_popups_tecon(page)
                    except: resultados[numero] = "ERRO"
        except: pass
        finally:
            browser.close()
            return resultados

# =========================================================
# FASE 2: ROBÔ FATURISTA (UPLOAD DOS PDFS E CONTÊINERES EXTRAS)
# =========================================================
def preencher_documento(page, tipo_doc, numero_doc, caminho_pdf, is_ultimo=False):
    try:
        page.locator("a.chosen-single:visible").last.click(force=True)
        time.sleep(1)
        page.locator("li.active-result:visible").get_by_text(tipo_doc, exact=True).first.click()
        time.sleep(1) 
        campo_numero = page.locator("input[name='documentNumberOrName']:visible").last
        if campo_numero.is_visible(): campo_numero.fill(numero_doc)
        page.locator("input[type='file'][name='file']").last.set_input_files(caminho_pdf)
        time.sleep(2) 
        if not is_ultimo:
            page.locator("button[data-ng-click='addInputDocumentType()']:visible").last.click(force=True)
            time.sleep(1)
        return True
    except Exception as e:
        print(f"   ❌ Erro ao subir o arquivo {tipo_doc} {numero_doc}: {e}")
        return False

def solicitar_passes_tecon(lista_containers):
    resultados = {}
    if not lista_containers: return resultados
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        try:
            if login_tecon(page):
                for numero in lista_containers:
                    if resultados.get(numero) == "SOLICITADO":
                        continue

                    print(f"\n🚀 Fase 2 | Iniciando faturamento de: {numero}")
                    try:
                        pasta = encontrar_pasta_container(numero)
                    except Exception as e:
                        print(Fore.RED + f"   ❌ Erro ao buscar pasta de {numero}: {e}")
                        resultados[numero] = "ERRO"
                        continue

                    if not pasta:
                        print(f"   ⚠️ Pasta não encontrada. Aguardando documentos.")
                        resultados[numero] = "SEM_ARQUIVOS"
                        continue

                    try:
                        nfs, ctes = classificar_e_extrair_pdfs(pasta)
                    except Exception as e:
                        print(Fore.RED + f"   ❌ Erro ao classificar PDFs de {numero}: {e}")
                        resultados[numero] = "ERRO"
                        continue

                    if not nfs or not ctes:
                        faltando = []
                        if not nfs: faltando.append("Nota Fiscal (NF)")
                        if not ctes: faltando.append("Conhecimento de Transporte (CT-e)")
                        print(f"   ⏳ Faturamento bloqueado. Falta: {' e '.join(faltando)} na pasta.")
                        resultados[numero] = "AGUARDANDO_DOCS"
                        continue

                    try:
                        page.goto("https://www.teconsuape.com/portalservicos/#!/atendimento-cliente/billing/novo")
                        time.sleep(4) 
                        page.locator("a.chosen-single:visible").first.click(force=True)
                        time.sleep(1) 
                        page.locator("li.active-result:visible").get_by_text("Cabotagem", exact=True).first.click()
                        time.sleep(2) 
                        page.locator("input[name='cpfCnpj']:visible").first.fill(CNPJ_TRANSPORTADORA)
                        page.locator("button[title='Pesquisar CPF/CNPJ']:visible").click()
                        
                        botao_sim_1 = page.locator("button.swal2-confirm:visible")
                        botao_sim_1.wait_for(state="visible", timeout=10000)
                        botao_sim_1.click()
                        time.sleep(3) 
                        
                        total_docs = len(nfs) + len(ctes)
                        docs_processados = 0
                        for nf in nfs:
                            docs_processados += 1
                            preencher_documento(page, "NF", nf["numero"], nf["caminho"], (docs_processados == total_docs))
                        for cte in ctes:
                            docs_processados += 1
                            preencher_documento(page, "CT-e", cte["numero"], cte["caminho"], (docs_processados == total_docs))

                        page.locator("#billUniqueDateYes").click(force=True)
                        data_hoje = datetime.now().strftime("%d/%m/%Y")
                        page.locator("input[ng-model='data.uniqueDate']:visible").fill(data_hoje)
                        
                        campo_conteiner = page.locator("input[name='containerNbr']:visible")
                        campo_conteiner.fill(numero)
                        campo_conteiner.press("Tab") 
                        time.sleep(1)
                        
                        page.locator("button[data-ng-click*='validateContainer']:visible").click()
                        page.locator("body").click(force=True)
                        time.sleep(3) 
                        
                        texto_tela = remover_acentos(page.locator("body").inner_text()).lower()
                        if "erro" in texto_tela or "invalido" in texto_tela or "nao encontrado" in texto_tela:
                            fechar_popups_tecon(page)
                            resultados[numero] = "ERRO"
                            continue 
                            
                        try:
                            page.locator("button.swal2-confirm:has-text('OK'):visible").click(timeout=3000)
                            time.sleep(1)
                        except: pass

                        limpar_conteineres_extras(page, numero)
                        
                        texto_tela_upper = page.locator("body").inner_text().upper()
                        todos_conteineres = set(re.findall(r'\b[A-Z]{4}\d{7}\b', texto_tela_upper))
                        conteineres_extras = todos_conteineres - {numero.upper()}
                        
                        if conteineres_extras:
                            print(f"   🔄 O Tecon puxou automaticamente na tela: {conteineres_extras}")
                            docs_ja_subidos = set([nf["numero"] for nf in nfs] + [cte["numero"] for cte in ctes])
                            for cont_extra in conteineres_extras:
                                pasta_extra = encontrar_pasta_container(cont_extra)
                                if pasta_extra:
                                    nfs_extra, ctes_extra = classificar_e_extrair_pdfs(pasta_extra)
                                    docs_para_subir = []
                                    for nf_e in nfs_extra:
                                        if nf_e["numero"] and nf_e["numero"] not in docs_ja_subidos:
                                            docs_para_subir.append(("NF", nf_e))
                                            docs_ja_subidos.add(nf_e["numero"])
                                    for cte_e in ctes_extra:
                                        if cte_e["numero"] and cte_e["numero"] not in docs_ja_subidos:
                                            docs_para_subir.append(("CT-e", cte_e))
                                            docs_ja_subidos.add(cte_e["numero"])
                                            
                                    if docs_para_subir:
                                        print(f"   📎 Subindo {len(docs_para_subir)} documento(s) faltantes da pasta do {cont_extra}...")
                                        for tipo_doc, doc in docs_para_subir:
                                            try:
                                                page.locator("button[data-ng-click='addInputDocumentType()']:visible").last.click(force=True)
                                                time.sleep(1)
                                                preencher_documento(page, tipo_doc, doc["numero"], doc["caminho"], is_ultimo=True)
                                            except Exception as e:
                                                print(f"   ❌ Erro ao adicionar linha extra: {e}")
                        
                        time.sleep(5) 
                        salvo_com_sucesso = False
                        
                        for tentativa in range(1, 6):
                            try:
                                botao_salvar = page.locator("button[data-ng-click='save()']:visible").first
                                if botao_salvar.is_visible():
                                    botao_salvar.scroll_into_view_if_needed()
                                    botao_salvar.click(force=True)
                                    time.sleep(2) 
                                    try:
                                        botao_sim_final = page.locator("button.swal2-confirm:has-text('Sim'):visible")
                                        if botao_sim_final.is_visible():
                                            botao_sim_final.click()
                                            time.sleep(2)
                                    except: pass
                                    try:
                                        page.locator("button.swal2-confirm:has-text('OK'):visible").click(timeout=2000)
                                    except: pass
                                else:
                                    salvo_com_sucesso = True
                                    break
                            except Exception:
                                salvo_com_sucesso = True
                                break
                                
                        if salvo_com_sucesso or not page.locator("button[data-ng-click='save()']:visible").is_visible():
                            try: page.wait_for_load_state("networkidle", timeout=15000)
                            except: pass 
                            
                            resultados[numero] = "SOLICITADO"
                            if conteineres_extras:
                                for c_ext in conteineres_extras:
                                    resultados[c_ext] = "SOLICITADO" 
                                    print(f"   ✅ Contêiner atrelado {c_ext} também faturado e marcado como concluído!")
                        else:
                            resultados[numero] = "ERRO"
                        time.sleep(2) 
                        
                    except Exception as e:
                        print(Fore.RED + f"   ❌ Erro no faturamento de {numero}: {e}")
                        resultados[numero] = "ERRO"
        except Exception as e:
            print(Fore.RED + f"❌ Erro crítico Fase 2: {e}")
        finally:
            browser.close()
            return resultados

# =========================================================
# FASE 3: LEITURA DE PDF INVISÍVEL COM REGRA ESTRITA DE EXPIRAÇÃO
# =========================================================
def verificar_passes_aprovados(lista_containers):
    resultados_fase3 = {}
    if not lista_containers: return resultados_fase3
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            if login_tecon(page):
                print("\n🧭 Acessando a Lista de Faturamentos para Fase 3...")
                page.goto("https://www.teconsuape.com/portalservicos/#!/atendimento-cliente/billing/lista")
                page.wait_for_selector("input[data-ng-model='filter.unitNbr']", timeout=20000)
                
                for numero in lista_containers:
                    print(f"\n🔍 Fase 3 | Analisando passe de: {numero}")
                    try:
                        campo_filtro = page.locator("input[data-ng-model='filter.unitNbr']")
                        campo_filtro.fill("") 
                        time.sleep(1)
                        campo_filtro.fill(numero)
                        time.sleep(1)
                        
                        page.locator("button[data-ng-click='getPartialFilter(filter)']").click()
                        time.sleep(5)
                        
                        primeira_linha = page.locator("table tbody tr").first
                        if not primeira_linha.is_visible():
                            print("   ⚠️ Nenhum atendimento encontrado para este contêiner.")
                            resultados_fase3[numero] = "NÃO ENCONTRADO"
                            continue
                            
                        texto_linha = primeira_linha.inner_text().upper()
                        linha_display = texto_linha.replace('\n', ' | ').strip()
                        print(f"   👀 Status lido na tela: {linha_display}")
                        
                        if "FINALIZADO" in texto_linha:
                            print("   ✅ Status FINALIZADO! Entrando no atendimento...")
                            
                            with page.expect_popup() as aba_atend_info:
                                primeira_linha.locator("a[data-ui-sref*='visualizar']").click()
                            aba_atend = aba_atend_info.value
                            aba_atend.wait_for_load_state("load")
                            time.sleep(4) 
                            
                            # CÓDIGO MELHORADO: Usa tanto o ícone zmdi-download quanto o fa-file-pdf
                            qtd_botoes = aba_atend.evaluate("""() => {
                                let btns = [];
                                document.querySelectorAll('button').forEach(b => {
                                    let html = b.innerHTML.toLowerCase();
                                    let ngClick = (b.getAttribute('ng-click') || '').toLowerCase();
                                    if (html.includes('fa-file-pdf') || html.includes('zmdi-download') || ngClick.includes('downloadfile')) {
                                        btns.push(b);
                                    }
                                });
                                btns.forEach((b, i) => b.setAttribute('id', `botao-baixar-pdf-${i}`));
                                return btns.length;
                            }""")
                            
                            data_vencimento = None
                            
                            if qtd_botoes == 0:
                                print("   ⚠️ Nenhum botão de PDF encontrado na tela.")
                            else:
                                for i in range(qtd_botoes):
                                    print(f"   📄 Intercetando PDF do documento {i+1}...")
                                    try:
                                        download_obj = []
                                        page_obj = []
                                        
                                        aba_atend.once("download", lambda d: download_obj.append(d))
                                        aba_atend.context.once("page", lambda p: page_obj.append(p))
                                        
                                        aba_atend.locator(f"#botao-baixar-pdf-{i}").click()
                                        
                                        for _ in range(15):
                                            if download_obj or page_obj: break
                                            time.sleep(1)
                                            
                                        caminho_temp = os.path.join(tempfile.gettempdir(), f"tecon_{int(time.time())}.pdf")
                                        texto_extraido = ""
                                        
                                        if download_obj:
                                            download_obj[0].save_as(caminho_temp)
                                            texto_extraido = extrair_texto_pdf(caminho_temp)
                                            
                                        elif page_obj:
                                            nova_aba = page_obj[0]
                                            time.sleep(2)
                                            url = nova_aba.url
                                            
                                            # Captura da imagem via Blob ou Link direto
                                            if url.startswith("blob:"):
                                                pdf_b64 = aba_atend.evaluate(f"""async () => {{
                                                    try {{
                                                        const res = await fetch('{url}');
                                                        const blob = await res.blob();
                                                        return await new Promise(resolve => {{
                                                            const reader = new FileReader();
                                                            reader.onloadend = () => resolve(reader.result);
                                                            reader.readAsDataURL(blob);
                                                        }});
                                                    }} catch(e) {{ return null; }}
                                                }}""")
                                                if pdf_b64:
                                                    with open(caminho_temp, "wb") as f:
                                                        f.write(base64.b64decode(pdf_b64.split(",")[1]))
                                            else:
                                                cookies = context.cookies()
                                                session = requests.Session()
                                                for c in cookies:
                                                    session.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
                                                res = session.get(url)
                                                with open(caminho_temp, "wb") as f:
                                                    f.write(res.content)
                                                    
                                            nova_aba.close()
                                            
                                            if os.path.exists(caminho_temp):
                                                texto_extraido = extrair_texto_pdf(caminho_temp)
                                        
                                        try: os.remove(caminho_temp)
                                        except: pass
                                        
                                        texto_limpo = re.sub(r'\s+', ' ', texto_extraido).strip()
                                        if texto_limpo:
                                            # Reduzindo o print do texto bruto para não poluir demais o terminal
                                            display_text = texto_limpo[:300] + "..." if len(texto_limpo) > 300 else texto_limpo
                                            print(Fore.CYAN + f"   📝 LIDO: {display_text}")
                                            
                                            # =======================================================
                                            # FIX: AGORA SÓ PROCURA EXATAMENTE POR 'EXPIRAÇÃO'
                                            # =======================================================
                                            padroes_data = [
                                                r"EXPIRA[CÇ][AÃ]?O\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
                                                r"DATA\s*(?:DE\s+)?EXPIRA[CÇ][AÃ]?O\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
                                                r"EXPIRA\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})"
                                            ]

                                            for padrao in padroes_data:
                                                match = re.search(padrao, texto_limpo, re.IGNORECASE)
                                                if match:
                                                    data_vencimento = match.group(1).replace('-', '/')
                                                    break 
                                        
                                        if data_vencimento:
                                            break 
                                        
                                    except Exception as e:
                                        print(Fore.RED + f"   ⚠️ Erro ao analisar o documento {i+1}: {e}")
                            
                            if data_vencimento:
                                resultados_fase3[numero] = f"PASSE VENCE {data_vencimento}"
                                print(Fore.GREEN + f"   🎯 BINGO! {resultados_fase3[numero]}")
                            else:
                                print(Fore.YELLOW + "   ⚠️ Nenhum documento retornou a palavra EXPIRAÇÃO.")
                                resultados_fase3[numero] = "FINALIZADO (DATA NÃO LIDA)"
                                
                            aba_atend.close()
                            
                        elif "PENDÊNCIA CLIENTE" in texto_linha:
                            resultados_fase3[numero] = "PENDÊNCIA CLIENTE"
                        else:
                            resultados_fase3[numero] = "EM ANÁLISE"
                            
                    except Exception as e:
                        resultados_fase3[numero] = "ERRO NA VERIFICAÇÃO"
                        
        except Exception as e: pass
        finally:
            browser.close()
            return resultados_fase3