import os
import sys
from playwright.sync_api import sync_playwright
import time
import unicodedata
import base64
import io
import re
import PyPDF2
import requests
import fitz
import pytesseract
import tempfile
from PIL import Image
from datetime import datetime

# Imports diretos da arquitetura raiz
from config import TECON_CPF, TECON_SENHA, HEADLESS, CNPJ_TRANSPORTADORA
from buscador_pdfs import encontrar_pasta_container, classificar_e_extrair_pdfs

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"

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
                    pasta = encontrar_pasta_container(numero)
                    if not pasta:
                        print(f"   ⚠️ Pasta não encontrada. Aguardando documentos.")
                        resultados[numero] = "SEM_ARQUIVOS"
                        continue
                        
                    nfs, ctes = classificar_e_extrair_pdfs(pasta)
                    
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
                        resultados[numero] = "ERRO"
        except Exception as e: pass
        finally:
            browser.close()
            return resultados

# =========================================================
# FASE 3: LEITURA DE DOWNLOADS INVISÍVEIS (A SOLUÇÃO DEFINITIVA)
# =========================================================
def _extrair_expiracao_gemini(screenshot_bytes: bytes) -> str | None:
    """Usa Gemini Vision para extrair a data de expiração do passe de porta."""
    try:
        from google import genai
        from google.genai import types
        from config import LISTA_CHAVES_GEMINI

        prompt = """Analise este documento (passe de porta do Tecon Suape) e retorne APENAS a data de expiração/validade no formato DD/MM/YYYY.
Procure por campos como: EXPIRAÇÃO, VALIDADE, VÁLIDO ATÉ, VENCIMENTO.
Retorne APENAS a data no formato DD/MM/YYYY, sem mais nada. Se não encontrar, retorne vazio."""

        for chave in LISTA_CHAVES_GEMINI:
            try:
                client  = genai.Client(api_key=chave)
                models  = client.models.list()
                modelo  = next(
                    (m.name.split("/")[-1] for m in models if "flash" in m.name.lower() and "vision" not in m.name.lower()),
                    "gemini-1.5-flash"
                )
                resposta = client.models.generate_content(
                    model=modelo,
                    contents=[prompt, types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg")]
                )
                txt = resposta.text.strip()
                # Valida formato DD/MM/YYYY
                match = re.search(r'(\d{2}[/\-]\d{2}[/\-]\d{4})', txt)
                if match:
                    return match.group(1).replace('-', '/')
            except Exception as e:
                if "429" in str(e):
                    time.sleep(3)
    except Exception:
        pass
    return None


def verificar_passes_aprovados(lista_containers):
    resultados_fase3 = {}
    if not lista_containers: return resultados_fase3
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        
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
                        
                        print(f"   ⏳ Aguardando atualização do Tecon...")
                        time.sleep(5)
                        
                        primeira_linha = page.locator("table tbody tr").first
                        if not primeira_linha.is_visible():
                            print("   ⚠️ Nenhum atendimento encontrado para este contêiner.")
                            resultados_fase3[numero] = "NÃO ENCONTRADO"
                            continue
                            
                        texto_linha = primeira_linha.inner_text().upper()
                        
                        linha_display = texto_linha.replace('\n', ' | ').strip()
                        print(f"   👀 Status lido na tela: {linha_display}")

                        # ── NO SHOW ────────────────────────────────────────
                        if "NOSHOW" in texto_linha.replace(" ", "").replace("-", ""):
                            print("   🚫 Status NO SHOW.")
                            resultados_fase3[numero] = "NO SHOW"

                        elif "FINALIZADO" in texto_linha:
                            print("   ✅ Status FINALIZADO! Entrando no atendimento...")
                            
                            with page.expect_popup() as aba_atend_info:
                                primeira_linha.locator("a[data-ui-sref*='visualizar']").click()
                            aba_atend = aba_atend_info.value
                            aba_atend.wait_for_load_state("load")
                            time.sleep(4)

                            # ── Encontra o botão de download do Passe de Porta ──
                            # Identifica pelo label "Passe de porta" próximo ao botão de download
                            idx_passe = aba_atend.evaluate("""() => {
                                const rows = document.querySelectorAll('.row, div[class*="document"], div[class*="form-group"]');
                                let idx = -1;
                                let btnCount = 0;
                                // Percorre todos os botões de download em ordem
                                const btns = [];
                                document.querySelectorAll('button').forEach(b => {
                                    const html = b.innerHTML.toLowerCase();
                                    const ngClick = (b.getAttribute('ng-click') || '').toLowerCase();
                                    if (html.includes('fa-download') || html.includes('zmdi-download') || ngClick.includes('downloadfile') || b.querySelector('i.fa')) {
                                        btns.push(b);
                                    }
                                });
                                // Tenta achar o botão próximo a "Passe de porta"
                                const spans = document.querySelectorAll('span.chosen-single span, option[value="PASSE_PORTA"], span');
                                for (const span of spans) {
                                    const txt = (span.innerText || span.textContent || '').trim().toLowerCase();
                                    if (txt.includes('passe de porta') || txt.includes('passe porta')) {
                                        // Procura o botão de download mais próximo
                                        let el = span.parentElement;
                                        for (let i = 0; i < 8; i++) {
                                            const btn = el.querySelector('button');
                                            if (btn) {
                                                // Qual índice é esse botão?
                                                for (let j = 0; j < btns.length; j++) {
                                                    if (btns[j] === btn) { return j; }
                                                }
                                            }
                                            el = el.parentElement;
                                            if (!el) break;
                                        }
                                    }
                                }
                                // Fallback: retorna -1 (vai tentar todos)
                                return -1;
                            }""")

                            # Marca todos os botões de download com id
                            qtd_botoes = aba_atend.evaluate("""() => {
                                let btns = [];
                                document.querySelectorAll('button').forEach(b => {
                                    const html = b.innerHTML.toLowerCase();
                                    const ngClick = (b.getAttribute('ng-click') || '').toLowerCase();
                                    if (html.includes('fa-download') || html.includes('zmdi-download') || ngClick.includes('downloadfile') || (b.querySelector && b.querySelector('i.fa'))) {
                                        btns.push(b);
                                    }
                                });
                                btns.forEach((b, i) => b.setAttribute('id', `botao-baixar-pdf-${i}`));
                                return btns.length;
                            }""")

                            print(f"   📎 {qtd_botoes} botão(ões) de download | Passe de porta idx={idx_passe}")

                            if qtd_botoes == 0:
                                print("   ⚠️ Nenhum botão de download encontrado.")
                                resultados_fase3[numero] = "FINALIZADO (DATA NÃO LIDA)"
                                aba_atend.close()
                                continue

                            # Define quais botões testar — prioriza o Passe de Porta
                            if idx_passe >= 0:
                                indices = [idx_passe] + [i for i in range(qtd_botoes) if i != idx_passe]
                            else:
                                indices = list(range(qtd_botoes))

                            data_vencimento = None

                            for i in indices:
                                print(f"   📄 Baixando documento {i+1}/{qtd_botoes}...")
                                try:
                                    with aba_atend.context.expect_page(timeout=15000) as page_info:
                                        aba_atend.locator(f"#botao-baixar-pdf-{i}").click()

                                    nova_aba = page_info.value
                                    nova_aba.wait_for_load_state("load", timeout=15000)
                                    time.sleep(2)

                                    # Usa Gemini Vision para extrair a data (mais preciso que OCR)
                                    screenshot_bytes = nova_aba.screenshot(type="jpeg", quality=95)
                                    nova_aba.close()

                                    data_vencimento = _extrair_expiracao_gemini(screenshot_bytes)
                                    if data_vencimento:
                                        print(f"   ✅ Data encontrada: {data_vencimento}")
                                        break

                                except Exception as e:
                                    print(f"   ❌ Erro doc {i}: {type(e).__name__}: {e}")

                            if data_vencimento:
                                resultados_fase3[numero] = f"PASSE VENCE {data_vencimento}"
                                print(f"   🎯 {resultados_fase3[numero]}")
                            else:
                                print("   ⚠️ Data de expiração não encontrada.")
                                resultados_fase3[numero] = "FINALIZADO (DATA NÃO LIDA)"

                            aba_atend.close()

                        elif "PENDÊNCIA CLIENTE" in texto_linha:
                            resultados_fase3[numero] = "PENDÊNCIA CLIENTE"
                        elif "REJEITADO" in texto_linha:
                            resultados_fase3[numero] = "REJEITADO"
                        else:
                            resultados_fase3[numero] = "EM ANÁLISE"
                            
                    except Exception as e:
                        resultados_fase3[numero] = "ERRO NA VERIFICAÇÃO"
                        
        except Exception as e: pass
        finally:
            browser.close()
            return resultados_fase3