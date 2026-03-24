"""
ROBÔ BSOFT TMS — TÍTULOS A PAGAR
Troca o Código Gerencial de títulos com códigos 09.007.005 (Adiantamento de Frete)
ou 09.007.006 (Saldo de Frete) pelo código correto do cliente.

Requer: pip install playwright colorama rapidfuzz
         playwright install chromium
"""

import os
import sys
import json
import time
import asyncio
import re
from datetime import datetime
from colorama import init, Fore, Style
from rapidfuzz import fuzz

init(autoreset=True)

# =====================================================================
# CONFIGURAÇÕES
# =====================================================================
BASE_URL = "https://nortenordeste.bsoft.app"
USUARIO = "GABRIEL.SANTOS"
SENHA = "GG@p5005"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_DIR = os.path.join(BASE_DIR, "Bsoft_Session")
MEMORIA_PATH = os.path.join(BASE_DIR, "bsoft_memoria_pagar.json")
LOG_DIR = os.path.join(BASE_DIR, "Logs_Bsoft")

CODIGOS_ALVO = ["09.007.005", "09.007.006"]
KEYWORDS_ALVO = ["ADIANTAMENTO", "SALDO DE FRETE"]

# =====================================================================
# UTILITÁRIOS
# =====================================================================

def log(msg, cor=Fore.WHITE):
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{agora}] {cor}{msg}{Style.RESET_ALL}")

def log_erro(msg):
    log(f"❌ {msg}", Fore.RED)

def log_ok(msg):
    log(f"✅ {msg}", Fore.GREEN)

def log_info(msg):
    log(f"ℹ️  {msg}", Fore.YELLOW)

def log_acao(msg):
    log(f"🔧 {msg}", Fore.MAGENTA)


def carregar_memoria():
    """Carrega memória de escolhas anteriores (fornecedor → código gerencial)."""
    if os.path.exists(MEMORIA_PATH):
        try:
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def salvar_memoria(memoria):
    with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


def salvar_log_execucao(resultados):
    """Salva log de execução em arquivo."""
    os.makedirs(LOG_DIR, exist_ok=True)
    agora = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"execucao_{agora}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    log_info(f"Log salvo em: {path}")


def escolher_codigo_gerencial(opcoes, nome_cliente, fornecedor, memoria):
    """
    Seleciona o código gerencial correto com base em prioridades:
    1. Memória (escolha anterior confirmada)
    2. Código com '2.000040' + 'FRETE' + nome do cliente → prioridade máxima
    3. Única opção com 'FRETE'
    4. Múltiplas com FRETE + match fuzzy com nome
    5. Ambiguidade → pergunta ao usuário
    6. Fuzzy fallback geral
    """
    if not opcoes:
        return None

    # Remove opções que SÃO os códigos errados (os que queremos TROCAR)
    opcoes = [op for op in opcoes if not any(
        cod in (op.get('value', '') + ' ' + op.get('text', '').upper())
        for cod in ['09.007.005', '09.007.006']
    )]
    if not opcoes:
        log_info("Todas as opções são códigos errados (09.007.005/006). Nenhuma alternativa.")
        return None

    # --- 1. Memória ---
    chave_memoria = fornecedor.strip().upper()
    if chave_memoria in memoria:
        val_mem = memoria[chave_memoria]
        for op in opcoes:
            if op['value'] == val_mem:
                log_info(f"Memória encontrada para '{fornecedor}': {op['text']}")
                return op
        # Valor na memória não existe mais nas opções, ignora

    # --- 2. Código com 2.000040 + FRETE + nome cliente ---
    nome_upper = nome_cliente.upper() if nome_cliente else ""
    primeiro_nome = nome_upper.split()[0] if nome_upper else ""

    for op in opcoes:
        txt = op['text'].upper()
        val = op['value'].upper()
        if '2.000040' in val and 'FRETE' in txt:
            if primeiro_nome and primeiro_nome in txt:
                log_ok(f"Match exato (2.000040 + FRETE + nome): {op['text']}")
                memoria[chave_memoria] = op['value']
                salvar_memoria(memoria)
                return op

    # --- 3. Única opção com FRETE — mas valida se o nome bate ---
    opcoes_frete = [op for op in opcoes if 'FRETE' in op['text'].upper()]
    if len(opcoes_frete) == 1:
        op = opcoes_frete[0]
        # Verifica se o nome do cliente aparece na opção (match mínimo)
        nome_ok = False
        if nome_upper:
            # Pega palavras significativas do nome do cliente (>= 4 letras, não genéricas)
            GENERICAS_VALIDACAO = {'LTDA', 'EIRELI', 'DISTRIBUIDORA', 'DISTRIBUICAO',
                                   'INDUSTRIA', 'COMERCIO', 'PAINEIS', 'COMPENSADOS',
                                   'MADEIRAS', 'MADEIRA', 'MATERIAIS', 'MATERIAL',
                                   'TRANSPORTES', 'TRANSPORTE', 'CONSTRUCAO',
                                   'SERVICOS', 'SERVICO', 'BRASIL', 'NORTE', 'NORDESTE'}
            palavras_cliente = [p for p in nome_upper.split() if len(p) >= 4
                                and p not in GENERICAS_VALIDACAO]
            txt_op = op['text'].upper()
            for p in palavras_cliente:
                if p in txt_op:
                    nome_ok = True
                    break
            # Fuzzy check como fallback
            if not nome_ok:
                score = fuzz.token_set_ratio(nome_upper, txt_op)
                nome_ok = score >= 55
        else:
            nome_ok = True  # Sem nome de cliente, aceita a única opção

        if nome_ok:
            log_ok(f"Única opção com FRETE (nome confere): {op['text']}")
            memoria[chave_memoria] = op['value']
            salvar_memoria(memoria)
            return op
        else:
            log_info(f"Única opção com FRETE mas nome não bate: '{op['text']}' vs cliente '{nome_upper}'")
            # Cai para o passo 5 (pergunta ao usuário)

    # --- 4. Múltiplas com FRETE + fuzzy ---
    if len(opcoes_frete) > 1 and nome_upper:
        melhor_score = 0
        melhor_op = None
        for op in opcoes_frete:
            score = fuzz.token_set_ratio(nome_upper, op['text'].upper())
            if score > melhor_score:
                melhor_score = score
                melhor_op = op
        if melhor_score >= 65:
            log_ok(f"Match fuzzy FRETE (score={melhor_score}): {melhor_op['text']}")
            memoria[chave_memoria] = melhor_op['value']
            salvar_memoria(memoria)
            return melhor_op

    # --- 5. Ambiguidade → pergunta ao usuário ---
    pool = opcoes_frete if opcoes_frete else opcoes
    if len(pool) <= 10:
        print(Fore.YELLOW + f"\n{'='*60}")
        print(Fore.YELLOW + f"⚠️  AMBIGUIDADE para: {fornecedor}")
        print(Fore.YELLOW + f"   Cliente CT-e: {nome_cliente or '(não encontrado)'}")
        print(Fore.YELLOW + f"{'='*60}")
        for i, op in enumerate(pool):
            print(Fore.WHITE + f"  [{i+1}] {op['text']}  (valor: {op['value']})")
        print(Fore.WHITE + f"  [0] PULAR este título")

        while True:
            try:
                escolha = input(Fore.CYAN + "Escolha: ").strip()
                idx = int(escolha)
                if idx == 0:
                    return None
                if 1 <= idx <= len(pool):
                    op = pool[idx - 1]
                    memoria[chave_memoria] = op['value']
                    salvar_memoria(memoria)
                    return op
            except (ValueError, IndexError):
                pass
            print(Fore.RED + "Opção inválida, tente novamente.")

    # --- 6. Fuzzy fallback geral ---
    if nome_upper:
        melhor_score = 0
        melhor_op = None
        for op in opcoes:
            score = fuzz.token_set_ratio(nome_upper, op['text'].upper())
            if score > melhor_score:
                melhor_score = score
                melhor_op = op
        if melhor_score >= 50:
            log_info(f"Fuzzy fallback (score={melhor_score}): {melhor_op['text']}")
            memoria[chave_memoria] = melhor_op['value']
            salvar_memoria(memoria)
            return melhor_op

    log_erro(f"Nenhuma opção viável encontrada para '{fornecedor}'.")
    return None


# =====================================================================
# CLASSE PRINCIPAL DO ROBÔ
# =====================================================================

class RoboBsoftPagar:
    def __init__(self):
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self.cache_numero_cliente = {}  # número_talão → nome_cliente
        self.memoria = carregar_memoria()
        self.resultados = []

    # -----------------------------------------------------------------
    # BROWSER
    # -----------------------------------------------------------------
    async def iniciar_browser(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        os.makedirs(SESSION_DIR, exist_ok=True)

        # Remove lock files de execuções anteriores travadas
        lock_file = os.path.join(SESSION_DIR, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                log_info("Lock de sessão anterior removido.")
            except:
                pass

        try:
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
        except Exception as e:
            log_erro(f"Falha ao abrir browser com sessão salva: {e}")
            log_info("Tentando limpar sessão e reabrir...")
            import shutil
            try:
                shutil.rmtree(SESSION_DIR, ignore_errors=True)
                os.makedirs(SESSION_DIR, exist_ok=True)
            except:
                pass
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

        self.page = self.browser.pages[0] if self.browser.pages else await self.browser.new_page()
        self.page.set_default_timeout(30000)
        log_ok("Browser iniciado.")

    async def fechar_browser(self):
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

    # -----------------------------------------------------------------
    # LOGIN
    # -----------------------------------------------------------------
    async def fazer_login(self):
        """Faz login no bsoft se necessário. Detecção robusta."""
        log_acao("Verificando login...")

        # Navega direto para a página alvo — se sessão expirou, redireciona para login
        try:
            await self.page.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=finan_faturas_pagar",
                wait_until="domcontentloaded", timeout=30000
            )
        except Exception as e:
            log_erro(f"Não conseguiu acessar bsoft: {e}")
            raise

        await asyncio.sleep(3)
        url_atual = self.page.url
        log_info(f"URL após navegação: {url_atual}")

        # Detecção: checa se existe campo de senha na página (= tela de login)
        precisa_login = await self.page.evaluate("""() => {
            const senhaField = document.querySelector("input[type='password']");
            if (senhaField) return true;
            if (location.href.toLowerCase().includes('login')) return true;
            if (location.pathname === '/' || location.pathname === '' || location.pathname === '/index.php') return true;
            // Se não tem nenhum elemento da lista de títulos, provavelmente não logou
            const temTabela = document.querySelector("table tbody tr")
                           || document.querySelector("img[title='Filtro Avançado']");
            if (!temTabela) return true;
            return false;
        }""")

        if precisa_login:
            log_info("Login necessário. Acessando tela de login...")

            # Se não tem campo de senha aqui, navega para a raiz
            tem_senha = await self.page.evaluate("() => !!document.querySelector(\"input[type='password']\")")
            if not tem_senha:
                await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

            # Espera o campo de senha aparecer
            try:
                await self.page.wait_for_selector("input[type='password']", timeout=15000)
            except:
                log_erro("Campo de senha não apareceu. Tentando navegar para URL de login...")
                # Tenta URL de login explícita
                for url_login in [f"{BASE_URL}/login", f"{BASE_URL}/index.php", BASE_URL]:
                    await self.page.goto(url_login, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    tem = await self.page.evaluate("() => !!document.querySelector(\"input[type='password']\")")
                    if tem:
                        break
                else:
                    log_erro("Impossível encontrar tela de login. Verifique a URL do bsoft.")
                    raise Exception("Tela de login não encontrada")

            # Tenta múltiplos seletores para o campo de usuário
            campo_user = None
            for seletor in ["input[name='usuario']", "input[name='login']", "input[id='usuario']",
                            "input[type='text']"]:
                loc = self.page.locator(seletor).first
                if await loc.count() > 0:
                    campo_user = loc
                    break

            campo_senha = self.page.locator("input[type='password']").first

            if not campo_user:
                log_erro("Campo de usuário não encontrado na tela de login.")
                raise Exception("Campo de usuário não encontrado")

            await campo_user.click()
            await campo_user.fill("")
            await campo_user.fill(USUARIO)
            await asyncio.sleep(0.5)
            await campo_senha.click()
            await campo_senha.fill("")
            await campo_senha.fill(SENHA)
            await asyncio.sleep(0.5)

            # Botão de login
            btn_login = None
            for seletor in ["input[value='Entrar']", "input[value='Login']", "input[value='Acessar']",
                            "button[type='submit']", "input[type='submit']"]:
                loc = self.page.locator(seletor).first
                if await loc.count() > 0:
                    btn_login = loc
                    break

            if btn_login:
                await btn_login.click()
            else:
                await campo_senha.press("Enter")

            await asyncio.sleep(5)

            # Verifica se login funcionou
            ainda_login = await self.page.evaluate("() => !!document.querySelector(\"input[type='password']\")")
            if ainda_login:
                log_erro("Login falhou — ainda na tela de login. Verifique as credenciais.")
                raise Exception("Login falhou")

            log_ok("Login realizado com sucesso.")

            # Navega para Títulos a Pagar
            await self.page.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=finan_faturas_pagar",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(3)
        else:
            log_ok("Sessão ativa, já logado.")

        # Verifica se a tela carregou
        tem_conteudo = await self.page.evaluate("""() => {
            return !!document.querySelector("table tbody tr")
                || !!document.querySelector("img[title='Filtro Avançado']");
        }""")
        if tem_conteudo:
            log_ok("Tela de Títulos a Pagar carregada.")
        else:
            log_info("Página carregou mas sem conteúdo esperado — continuando mesmo assim...")

    # -----------------------------------------------------------------
    # LIMPAR FILTROS (genérico)
    # -----------------------------------------------------------------
    async def limpar_filtros(self, usar_rg_lbr=True):
        """Limpa filtros existentes na lista atual."""
        if usar_rg_lbr:
            await self.page.evaluate("""() => {
                const btnLimpar = document.querySelector("input[value='Limpar']");
                if (btnLimpar) {
                    try { RG.lBR(btnLimpar); } catch(e) { btnLimpar.click(); }
                }
            }""")
            await asyncio.sleep(1.5)

        # Remove tags de filtros ativos
        await self.page.evaluate("""() => {
            document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]')
                .forEach(a => { try { a.click(); } catch(e) {} });
        }""")
        await asyncio.sleep(0.5)

    # -----------------------------------------------------------------
    # FASE 1 — COLETA DE TÍTULOS
    # -----------------------------------------------------------------
    async def coletar_titulos(self):
        """Coleta todos os títulos com códigos 09.007.005 e 09.007.006."""
        todos_titulos = []

        for codigo in CODIGOS_ALVO:
            log_acao(f"Filtrando por código: {codigo}")

            # Navega para Títulos a Pagar
            await self.page.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=finan_faturas_pagar",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(2)

            # Limpa filtros
            await self.limpar_filtros(usar_rg_lbr=True)
            await asyncio.sleep(1)

            # Abre Filtro Avançado
            btn_filtro = self.page.locator("img[title='Filtro Avançado']")
            if await btn_filtro.count() > 0:
                await btn_filtro.click()
                await asyncio.sleep(1.5)
            else:
                log_erro("Botão 'Filtro Avançado' não encontrado!")
                continue

            # Preenche campo de filtro
            try:
                select_campo = self.page.locator("select[name='campos[1]']")
                await select_campo.select_option(value="filtroCodigoGerencial")
                await asyncio.sleep(0.5)

                select_operador = self.page.locator("select[name='operador[1]']")
                await select_operador.select_option(value="like")
                await asyncio.sleep(0.5)

                input_valor = self.page.locator("input[name='valores[]']").first
                await input_valor.fill(codigo)
                await asyncio.sleep(0.3)

                btn_filtrar = self.page.locator("input[name='bs'][value='Filtrar']")
                await btn_filtrar.click()
                await asyncio.sleep(3)
            except Exception as e:
                log_erro(f"Erro ao aplicar filtro avançado: {e}")
                continue

            # Coleta títulos de todas as páginas
            pagina_num = 1
            while True:
                log_info(f"Código {codigo} — Lendo página {pagina_num}...")

                titulos_pagina = await self.page.evaluate("""() => {
                    const resultado = [];
                    const headerTexts = ['fornecedor','cliente','número','numero','id','código'];
                    document.querySelectorAll('table tbody tr').forEach(tr => {
                        // Ignora linhas de cabeçalho (th dentro de tbody)
                        if (tr.querySelector('th')) return;
                        
                        const cb = tr.querySelector('input[name="id"]');
                        if (!cb || !cb.value || !cb.value.match(/^\\d+$/)) return;
                        
                        const tdFornec = tr.querySelector('td[swni="fornecedor"]')
                                       || tr.querySelector('td[swni="cliente"]');
                        const tdNumero = tr.querySelector('td[swni="numero"]');
                        const tdData   = tr.querySelector('td[swni="data_de_emissao"]');
                        
                        const fornecedor = tdFornec ? tdFornec.innerText.trim() : '';
                        const numero = tdNumero ? tdNumero.innerText.trim() : '';
                        const dataEmissao = tdData ? tdData.innerText.trim() : '';
                        
                        // Ignora se o texto é literalmente o nome da coluna
                        if (headerTexts.includes(fornecedor.toLowerCase())) return;
                        if (headerTexts.includes(numero.toLowerCase())) return;
                        
                        resultado.push({ id: cb.value, fornecedor, numero, dataEmissao });
                    });
                    return resultado;
                }""")

                for item in titulos_pagina:
                    # Filtra por data: só processa títulos de Janeiro/2026 em diante
                    data_str = item.get('dataEmissao', '')
                    if data_str:
                        try:
                            # Formato esperado: DD/MM/YYYY
                            partes = data_str.split('/')
                            if len(partes) == 3:
                                ano = int(partes[2])
                                if ano < 2026:
                                    log_info(f"  ⏭️  Título #{item['id']} pulado — emissão {data_str} (anterior a 2026)")
                                    continue
                        except (ValueError, IndexError):
                            pass  # Se não conseguir parsear, processa normalmente

                    todos_titulos.append({
                        "codigo": item['id'],
                        "fornecedor": item['fornecedor'],
                        "numero": item.get('numero', ''),
                        "data_emissao": data_str,
                        "codigo_filtrado": codigo,
                    })

                log_info(f"  → {len(titulos_pagina)} títulos nesta página.")

                # Próxima página
                btn_prox = self.page.locator("a[title='Próxima página']")
                if await btn_prox.count() > 0:
                    await btn_prox.click()
                    await asyncio.sleep(2)
                    pagina_num += 1
                else:
                    break

        # Remove duplicatas por ID
        vistos = set()
        titulos_unicos = []
        for t in todos_titulos:
            if t['codigo'] not in vistos:
                vistos.add(t['codigo'])
                titulos_unicos.append(t)

        total_coletados = len(titulos_unicos)
        log_ok(f"Total de títulos coletados (2026+, únicos): {total_coletados}")
        return titulos_unicos

    # -----------------------------------------------------------------
    # FASE 2 — BUSCAR CLIENTE VIA CONTRATO DE FRETE → CT-e
    # -----------------------------------------------------------------
    async def buscar_cliente_por_numero(self, numero_talao):
        """
        Dado o número do talão, busca o nome do cliente:
        Contrato de Frete → pega CT-e → CT-e lista → lê cliente.
        """
        if not numero_talao:
            log_erro("Número do talão vazio, não é possível buscar cliente.")
            return None

        # Verifica cache
        if numero_talao in self.cache_numero_cliente:
            log_info(f"Cache hit para talão {numero_talao}: {self.cache_numero_cliente[numero_talao]}")
            return self.cache_numero_cliente[numero_talao]

        log_acao(f"Buscando cliente para talão nº {numero_talao}...")

        # --- A. Abre Contrato de Frete ---
        aba = await self.context_new_page()
        try:
            await aba.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=transp_contratoFrete",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(2)

            # --- B. Limpa e filtra pelo número do talão ---
            await aba.evaluate("""() => {
                const btnLimpar = document.querySelector("input[value='Limpar']");
                if (btnLimpar) { try { RG.lBR(btnLimpar); } catch(e) { btnLimpar.click(); } }
            }""")
            await asyncio.sleep(2)  # Espera mais após RG.lBR (causa recarga parcial)

            await aba.evaluate("""() => {
                document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]')
                    .forEach(a => { try { a.click(); } catch(e) {} });
                document.querySelectorAll('input[name^="busca_"]').forEach(inp => { inp.value = ''; });
            }""")
            await asyncio.sleep(1)

            # Abre painel de busca rápida — clica no cabeçalho para garantir que está aberto
            await aba.evaluate("""() => {
                const cabecalho = document.querySelector('.rg-busca-rapida__cabecalho');
                if (!cabecalho) return;
                // Se tem chevron-up = painel fechado, precisa clicar para abrir
                const chevUp = cabecalho.querySelector('i.fa-chevron-up');
                if (chevUp) {
                    cabecalho.click();  // abre o painel
                }
            }""")
            await asyncio.sleep(1)

            # Preenche campo de busca via JS puro (evita problemas de visibilidade)
            await aba.evaluate("""(num) => {
                const campo = document.querySelector("input[name='busca_transp_reciboFrete_nroRecibo']");
                if (!campo) return;
                // Força visibilidade de toda a hierarquia
                let el = campo;
                while (el && el !== document.body) {
                    if (el.style && el.style.display === 'none') el.style.display = '';
                    el = el.parentElement;
                }
                campo.value = num;
                campo.dispatchEvent(new Event('input', {bubbles:true}));
                campo.dispatchEvent(new Event('change', {bubbles:true}));
            }""", numero_talao)
            await asyncio.sleep(0.5)

            # Clica Filtrar via JS — RG.fBR causa navegação
            try:
                async with aba.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
                    filtrou = await aba.evaluate("""() => {
                        const btn = document.querySelector("input[value='Filtrar']");
                        if (!btn) return false;
                        try { return RG.fBR(btn), true; } catch(e) {}
                        try { btn.click(); return true; } catch(e2) { return false; }
                    }""")
            except:
                filtrou = True  # Se não houve navegação, assume AJAX
            if not filtrou:
                log_erro("Botão Filtrar não encontrado no Contrato de Frete")
                await aba.close()
                return None

            # Espera a página estabilizar
            try:
                await aba.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass
            await asyncio.sleep(2)

            # --- C. Pega ID do contrato ---
            id_contrato = await aba.evaluate("""(numTalao) => {
                const tds = document.querySelectorAll('td[swni="numerotalao"]');
                for (const td of tds) {
                    if (td.innerText.trim().includes(numTalao)) {
                        const cb = td.closest('tr')?.querySelector('input[name="id"]');
                        if (cb) return cb.value;
                    }
                }
                return null;
            }""", numero_talao)

            if not id_contrato:
                log_erro(f"Contrato de Frete não encontrado para talão {numero_talao}")
                await aba.close()
                return None

            log_info(f"  Contrato de Frete ID: {id_contrato}")

            # --- D. Abre formulário do contrato ---
            await aba.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/formulario.php?rotina=transp_contratoFrete&OP=O3&id={id_contrato}",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(2)

            # --- E. Lê número do CT-e ---
            numero_cte = await aba.evaluate("""() => {
                const tds = document.querySelectorAll('td');
                for (const td of tds) {
                    const m = td.innerText.match(/CT:\\s*(\\d+)\\/CT-e/i)
                           || td.innerText.match(/(\\d{3,})\\/CT-e/i);
                    if (m) return m[1];
                }
                return null;
            }""")

            if not numero_cte:
                log_erro(f"CT-e não encontrado no contrato {id_contrato}")
                await aba.close()
                return None

            log_info(f"  CT-e encontrado: {numero_cte}")

            # --- F. Navega para CT-e ---
            await aba.goto(
                f"{BASE_URL}/versoes/versao5.0/rotinas/c.php?id=transp_cte&menu=s",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(2)

            # --- G. Filtra CT-e pelo número (SEM usar RG.lBR) ---
            await aba.evaluate("""() => {
                // Remove tags ativas
                document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]')
                    .forEach(a => { try { a.click(); } catch(e) {} });
            }""")
            await asyncio.sleep(0.5)

            # Abre painel SE fechado (clica no cabeçalho)
            await aba.evaluate("""() => {
                const cabecalho = document.querySelector('.rg-busca-rapida__cabecalho');
                if (!cabecalho) return;
                const chevUp = cabecalho.querySelector('i.fa-chevron-up');
                if (chevUp) cabecalho.click();
            }""")
            await asyncio.sleep(1)

            # Limpa campos busca_*
            await aba.evaluate("""() => {
                document.querySelectorAll('input[name^="busca_"]').forEach(inp => { inp.value = ''; });
            }""")
            await asyncio.sleep(0.3)

            # Preenche campo de número do CT-e (forçando visibilidade)
            await aba.evaluate("""(numCte) => {
                const campo = document.querySelector(
                    "input[name='busca_transp_conhecimentoTransporteReais_nroConhecimento']"
                );
                if (!campo) return;
                // Força visibilidade
                let el = campo;
                while (el && el !== document.body) {
                    if (el.style && el.style.display === 'none') el.style.display = '';
                    el = el.parentElement;
                }
                campo.value = numCte;
                campo.dispatchEvent(new Event('input', {bubbles:true}));
                campo.dispatchEvent(new Event('change', {bubbles:true}));
            }""", numero_cte)
            await asyncio.sleep(0.5)

            # Clica Filtrar via JS — RG.fBR causa navegação/recarga da página
            try:
                async with aba.expect_navigation(timeout=15000, wait_until="domcontentloaded"):
                    await aba.evaluate("""() => {
                        const btn = document.querySelector("input[value='Filtrar']");
                        if (btn) {
                            try { RG.fBR(btn); } catch(e) { btn.click(); }
                        }
                    }""")
            except:
                # Se não houve navegação (AJAX), espera normalmente
                pass

            # Espera a página estabilizar após navegação/recarga
            try:
                await aba.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass
            await asyncio.sleep(3)

            # --- H. Lê o cliente do CT-e na lista (com retry) ---
            nome_cliente = None
            for tentativa in range(3):
                try:
                    nome_cliente = await aba.evaluate("""() => {
                        const linhas = document.querySelectorAll('table tbody tr');
                        for (const tr of linhas) {
                            const td = tr.querySelector('td[swni="cliente__nome"]')
                                    || tr.querySelector('td[swni="cliente"]');
                            if (td) {
                                const texto = td.innerText.trim();
                                if (texto && texto.toLowerCase() !== 'cliente - nome' && texto.length > 3)
                                    return texto;
                            }
                        }
                        return null;
                    }""")
                    if nome_cliente:
                        break
                except Exception as e:
                    if tentativa < 2:
                        log_info(f"  Contexto destruído (tentativa {tentativa+1}/3), aguardando recarga...")
                        await asyncio.sleep(3)
                        try:
                            await aba.wait_for_load_state("domcontentloaded", timeout=10000)
                        except:
                            pass
                        await asyncio.sleep(2)
                    else:
                        log_erro(f"  Não conseguiu ler cliente após 3 tentativas: {e}")
                        break

            if nome_cliente:
                log_ok(f"  Cliente encontrado: {nome_cliente}")
                # Salva no cache
                self.cache_numero_cliente[numero_talao] = nome_cliente
                self.cache_numero_cliente[id_contrato] = nome_cliente
            else:
                log_erro(f"  Cliente não encontrado na lista do CT-e {numero_cte}")

            await aba.close()
            # Garante que self.page ainda aponta para uma página válida
            await self._garantir_pagina_principal()
            return nome_cliente

        except Exception as e:
            log_erro(f"Erro ao buscar cliente para talão {numero_talao}: {e}")
            try:
                await aba.close()
            except:
                pass
            await self._garantir_pagina_principal()
            return None

    async def _garantir_pagina_principal(self):
        """Verifica se self.page está viva. Se não, pega outra página do contexto."""
        try:
            await self.page.evaluate("() => true")
        except:
            log_info("Página principal perdida. Recuperando...")
            pages = self.browser.pages
            if pages:
                self.page = pages[0]
                self.page.set_default_timeout(30000)
                log_ok(f"Recuperada — usando página: {self.page.url[:80]}")
            else:
                self.page = await self.browser.new_page()
                self.page.set_default_timeout(30000)
                log_info("Nova página criada.")

    async def context_new_page(self):
        """Abre uma nova aba no contexto persistente."""
        return await self.browser.new_page()

    # -----------------------------------------------------------------
    # FASE 3 — TROCAR CÓDIGO GERENCIAL
    # -----------------------------------------------------------------
    async def trocar_codigo_gerencial(self, titulo_id, nome_cliente, fornecedor):
        """Abre o título e troca o código gerencial."""
        log_acao(f"Abrindo título #{titulo_id} para troca de código...")

        # --- A. Abre formulário do título ---
        await self.page.goto(
            f"{BASE_URL}/versoes/versao5.0/rotinas/formulario.php?rotina=finan_faturas_pagar&OP=O3&id={titulo_id}",
            wait_until="domcontentloaded", timeout=30000
        )
        await asyncio.sleep(2)

        # Espera o formulário carregar completamente
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        await asyncio.sleep(1)

        # --- B. Encontra o select com o código alvo (com retry) ---
        select_info = None
        for tentativa in range(3):
            select_info = await self.page.evaluate("""() => {
                const alvos = ['09.007.005', '09.007.006', 'ADIANTAMENTO', 'SALDO DE FRETE'];
                const sels = document.querySelectorAll(
                    "select[name^='dados_grupoApropriador_apropGerencial_codigo']"
                );
                for (let sel of sels) {
                    const titulo = sel.getAttribute('title') || '';
                    const selVal = sel.value || '';
                    const selText = sel.options[sel.selectedIndex]?.text || '';
                    const combined = (titulo + ' ' + selVal + ' ' + selText).toUpperCase();
                    if (alvos.some(c => combined.includes(c.toUpperCase()))) {
                        const num = sel.id.replace('cswobj', '');
                        return {
                            id_select: sel.id,
                            id_pesquisa: 'pswobj' + num,
                            nome_campo: sel.name,
                            valor_atual: selVal,
                            texto_atual: selText
                        };
                    }
                }
                // Info de debug: quantos selects existem e seus valores
                const debug = Array.from(sels).map(s => ({
                    id: s.id,
                    title: (s.getAttribute('title') || '').substring(0, 60),
                    value: s.value,
                    text: s.options[s.selectedIndex]?.text?.substring(0, 40) || ''
                }));
                return {_debug: true, total_selects: sels.length, selects: debug};
            }""")

            if select_info and not select_info.get('_debug'):
                break
            if select_info and select_info.get('_debug'):
                if tentativa < 2:
                    log_info(f"  Select alvo não encontrado (tentativa {tentativa+1}/3) — "
                             f"{select_info.get('total_selects', 0)} selects existentes, aguardando...")
                    await asyncio.sleep(2)
                    select_info = None
                else:
                    log_info(f"  Debug: {select_info.get('total_selects', 0)} selects encontrados:")
                    for s in select_info.get('selects', []):
                        log_info(f"    → {s['id']}: {s['text']} (title: {s['title']})")
                    select_info = None
            elif not select_info and tentativa < 2:
                log_info(f"  Select alvo não encontrado (tentativa {tentativa+1}/3), aguardando...")
                await asyncio.sleep(2)

        if not select_info:
            log_erro(f"Select com código 09.007.005/006 não encontrado no título #{titulo_id} — "
                     f"possivelmente já foi alterado anteriormente.")
            return False

        log_info(f"  Select encontrado: {select_info['id_select']} — atual: {select_info['texto_atual']}")

        # --- C. Pesquisa opções pelo nome do cliente ---
        id_pesquisa = select_info['id_pesquisa']
        id_select = select_info['id_select']

        # Gera termos de busca inteligentes: palavras específicas primeiro, genéricas por último
        PALAVRAS_GENERICAS = {
            'MADEIRAS', 'MADEIRA', 'COMERCIO', 'INDUSTRIA', 'TRANSPORTES',
            'TRANSPORTE', 'SERVICOS', 'SERVICO', 'MATERIAIS', 'MATERIAL',
            'CONSTRUCAO', 'CONSTRUCOES', 'DISTRIBUICAO', 'DISTRIBUIDORA',
            'BRASIL', 'NORTE', 'NORDESTE', 'SUL', 'LESTE', 'OESTE',
            'PAINEIS', 'COMPENSADOS', 'SOLUCOES', 'GRUPO', 'CENTER',
        }
        SUFIXOS_IGNORAR = {'LTDA', 'EIRELI', 'EPP', 'ME', 'CIA', 'S/A', 'S.A.', 'S.A',
                           'DE', 'DO', 'DA', 'DOS', 'DAS', 'E'}

        def gerar_termos(nome):
            """Gera lista de termos de busca, específicos primeiro."""
            if not nome:
                return []
            palavras = [p for p in nome.upper().split() if p.strip() and len(p) >= 2
                        and p not in SUFIXOS_IGNORAR]
            especificas = [p for p in palavras if p not in PALAVRAS_GENERICAS and len(p) >= 3]
            genericas = [p for p in palavras if p in PALAVRAS_GENERICAS]
            # Ordena por tamanho (maior = mais única)
            especificas.sort(key=len, reverse=True)
            genericas.sort(key=len, reverse=True)
            termos = []
            # Específicas primeiro
            termos.extend(especificas)
            # Combo de 2 específicas
            if len(especificas) >= 2:
                termos.append(f"{especificas[0]} {especificas[1]}")
            # Genéricas por último
            termos.extend(genericas)
            # Remove duplicatas mantendo ordem
            vistos = set()
            resultado = []
            for t in termos:
                if t.upper() not in vistos:
                    vistos.add(t.upper())
                    resultado.append(t)
            return resultado[:8]

        termos_busca = []
        if nome_cliente:
            termos_busca.extend(gerar_termos(nome_cliente))
        if fornecedor:
            termos_fornec = gerar_termos(fornecedor)
            for t in termos_fornec:
                if t.upper() not in [tb.upper() for tb in termos_busca]:
                    termos_busca.append(t)

        if not termos_busca:
            # Fallback: primeiro nome do que tiver
            fb = (nome_cliente or fornecedor or "").split()
            termos_busca = [fb[0]] if fb else []

        if not termos_busca:
            log_erro("Sem termo de busca para pesquisar código gerencial.")
            return False

        log_info(f"  Termos de busca: {termos_busca[:5]} (campo: {id_pesquisa}, select: {id_select})")

        opcoes = []
        termo_usado = ""

        for termo in termos_busca[:5]:
            log_info(f"  Tentando termo: '{termo}'...")

            # Pesquisa usando a mesma abordagem do código de recebimento:
            # 1. Força visibilidade do campo E dos pais (display + visibility)
            # 2. Preenche o campo de pesquisa
            # 3. Encontra a lupa MAIS PRÓXIMA do campo por distância
            # 4. Força visibilidade da lupa também
            # 5. Clica na lupa
            resultado_pesquisa = await self.page.evaluate("""(args) => {
                const campo = document.getElementById(args.idPesq);
                if (!campo) return {ok: false, erro: 'campo pesquisa nao encontrado: ' + args.idPesq};

                // Força visibilidade do campo e toda a hierarquia
                let el = campo;
                while (el && el !== document.body) {
                    if (el.style && el.style.display === 'none') el.style.display = '';
                    if (el.style && el.style.visibility === 'hidden') el.style.visibility = '';
                    el = el.parentElement;
                }

                // Preenche o campo de pesquisa
                campo.value = args.termo;

                // Encontra a lupa mais próxima do campo (por distância visual)
                const lupas = document.querySelectorAll(
                    "i[name='botaoPesquisa_dados_grupoApropriador_apropGerencial_codigo']"
                );
                let lupaMaisProxima = null;
                let menorDistancia = Infinity;

                lupas.forEach(lupa => {
                    // Força visibilidade da lupa também
                    let elLupa = lupa;
                    while (elLupa && elLupa !== document.body) {
                        if (elLupa.style && elLupa.style.display === 'none') elLupa.style.display = '';
                        if (elLupa.style && elLupa.style.visibility === 'hidden') elLupa.style.visibility = '';
                        elLupa = elLupa.parentElement;
                    }

                    const rect1 = campo.getBoundingClientRect();
                    const rect2 = lupa.getBoundingClientRect();
                    const dist = Math.abs(rect1.top - rect2.top) + Math.abs(rect1.left - rect2.left);
                    if (dist < menorDistancia) {
                        menorDistancia = dist;
                        lupaMaisProxima = lupa;
                    }
                });

                if (lupaMaisProxima) {
                    lupaMaisProxima.click();
                    return {ok: true, metodo: 'lupa_proxima', distancia: menorDistancia, totalLupas: lupas.length};
                }

                // Fallback: dispara Enter no campo
                campo.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
                return {ok: true, metodo: 'enter_fallback', totalLupas: lupas.length};
            }""", {"idPesq": id_pesquisa, "termo": termo})

            log_info(f"  Resultado pesquisa: {resultado_pesquisa}")
            await asyncio.sleep(3)

            # Lê opções do select
            opcoes = await self.page.evaluate("""(idSel) => {
                const sel = document.getElementById(idSel);
                if (!sel) return [];
                return Array.from(sel.options)
                    .filter(o => o.value && o.value !== '0' && !o.disabled && o.text.trim())
                    .map(o => ({value: o.value, text: o.text.trim()}));
            }""", id_select)

            # Filtra opções que são os próprios códigos errados
            opcoes_validas = [op for op in opcoes if not any(
                cod in (op.get('value', '') + ' ' + op.get('text', '').upper())
                for cod in ['09.007.005', '09.007.006']
            )]

            if opcoes_validas:
                termo_usado = termo
                log_ok(f"  '{termo}' → {len(opcoes_validas)} opção(ões) válidas encontradas")
                opcoes = opcoes_validas
                break
            else:
                log_info(f"  '{termo}' → sem opções válidas, tentando próximo...")

        if not opcoes:
            log_erro(f"Nenhuma opção válida encontrada para '{nome_cliente}' / '{fornecedor}'")
            return False

        log_info(f"  {len(opcoes)} opções válidas encontradas.")

        # --- D. Seleção com prioridade ---
        op_escolhida = escolher_codigo_gerencial(opcoes, nome_cliente, fornecedor, self.memoria)
        if not op_escolhida:
            log_info(f"  Título #{titulo_id} PULADO — sem código gerencial selecionado.")
            return False

        log_acao(f"  Aplicando código: {op_escolhida['text']} ({op_escolhida['value']})")

        # --- E. Aplica a seleção ---
        await self.page.evaluate("""(args) => {
            const sel = document.getElementById(args.idSel);
            if (!sel) return;
            sel.value = args.valor;
            try { validaContasSinteticas(sel); } catch(e) {}
            try { validaPreenchimento(); } catch(e) {}
            try { Sisweb.aplicarTitle(sel.name, 'select-one'); } catch(e) {}
            sel.dispatchEvent(new Event('change', {bubbles: true}));
        }""", {"idSel": id_select, "valor": op_escolhida['value']})
        await asyncio.sleep(1)

        # --- F. Salva ---
        salvo = await self.page.evaluate("""() => {
            const btn = document.querySelector("input[name='botao_finalizacao'][value='Salvar']");
            if (!btn) return false;
            try { RG.trocaPasso(btn, '1', true, 0); return true; }
            catch(e) {
                try { RG.postaalteracao(btn, document.forms[0]); return true; }
                catch(e2) {
                    try { btn.click(); return true; }
                    catch(e3) { return false; }
                }
            }
        }""")

        if salvo:
            await asyncio.sleep(3)
            log_ok(f"  Título #{titulo_id} SALVO com código: {op_escolhida['text']}")
            return True
        else:
            log_erro(f"  Falha ao salvar título #{titulo_id}")
            return False

    # -----------------------------------------------------------------
    # ORQUESTRADOR PRINCIPAL
    # -----------------------------------------------------------------
    async def executar(self):
        """Executa o fluxo completo do robô."""
        print(Fore.CYAN + Style.BRIGHT + "\n" + "=" * 60)
        print(Fore.CYAN + "  ROBÔ BSOFT TMS — TÍTULOS A PAGAR")
        print(Fore.CYAN + f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(Fore.CYAN + "=" * 60 + "\n")

        try:
            await self.iniciar_browser()
            await self.fazer_login()

            # FASE 1 — Coleta
            titulos = await self.coletar_titulos()
            if not titulos:
                log_info("Nenhum título encontrado para processar. Finalizando.")
                return

            # FASE 2 e 3 — Processamento
            total = len(titulos)
            sucesso = 0
            falhas = 0
            pulados = 0

            for idx, titulo in enumerate(titulos):
                print(Fore.CYAN + f"\n{'─'*50}")
                log_info(f"Processando {idx+1}/{total}: Título #{titulo['codigo']} | "
                         f"Fornecedor: {titulo['fornecedor']} | Talão: {titulo['numero']} | "
                         f"Emissão: {titulo.get('data_emissao', '?')}")

                numero = titulo['numero']
                nome_cliente = None

                if numero:
                    nome_cliente = await self.buscar_cliente_por_numero(numero)
                else:
                    log_info("  Sem número de talão — tentando usar fornecedor como referência.")

                resultado = await self.trocar_codigo_gerencial(
                    titulo['codigo'],
                    nome_cliente or "",
                    titulo['fornecedor']
                )

                reg = {
                    "titulo_id": titulo['codigo'],
                    "fornecedor": titulo['fornecedor'],
                    "numero_talao": numero,
                    "cliente_cte": nome_cliente or "",
                    "status": "OK" if resultado else "FALHA",
                    "timestamp": datetime.now().isoformat()
                }
                self.resultados.append(reg)

                if resultado:
                    sucesso += 1
                elif resultado is False and nome_cliente:
                    falhas += 1
                else:
                    pulados += 1

            # Resumo final
            print(Fore.CYAN + Style.BRIGHT + f"\n{'='*60}")
            print(Fore.CYAN + "  RESUMO DA EXECUÇÃO")
            print(Fore.CYAN + f"{'='*60}")
            print(Fore.GREEN  + f"  ✅ Sucesso:  {sucesso}")
            print(Fore.RED    + f"  ❌ Falhas:   {falhas}")
            print(Fore.YELLOW + f"  ⏭️  Pulados:  {pulados}")
            print(Fore.WHITE  + f"  📊 Total:    {total}")
            print(Fore.CYAN + f"{'='*60}\n")

            salvar_log_execucao(self.resultados)

        except Exception as e:
            log_erro(f"Erro crítico: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.fechar_browser()


# =====================================================================
# MAIN
# =====================================================================
async def main():
    robo = RoboBsoftPagar()
    await robo.executar()

if __name__ == "__main__":
    asyncio.run(main())