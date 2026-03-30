"""
bsoft_titulos_pagar.py
======================
Robô bsoft TMS — Troca de Código Gerencial em Títulos a Pagar.

Fluxo por título:
  1. Títulos a Pagar → filtro 09.007.005 ou 09.007.006
  2. Abre o título → copia o NÚMERO (ex: 257)
  3. Barra de pesquisa → "contrato de frete" → nova aba
  4. Filtra pelo número → abre o contrato → copia número do CT-e (ex: 3779)
  5. Barra de pesquisa → "CT-e" → nova aba
  6. Filtra pelo número do CT-e → lê o CLIENTE
  7. Volta ao título → troca Código Gerencial pelo nome do cliente
     (pesquisa por "Frete [cliente]" em vez de "Receita [cliente]")
  8. Salva
"""

import os, time, re, json, unicodedata
from datetime import datetime
from colorama import init, Fore, Style
from playwright.sync_api import sync_playwright

try:
    from rapidfuzz import fuzz, process as fuzz_process
    RAPIDFUZZ_OK = True
except ImportError:
    RAPIDFUZZ_OK = False

init(autoreset=True)

# =============================================================
# CONFIGURAÇÕES
# =============================================================
BSOFT_URL      = "https://nortenordeste.bsoft.app"
BSOFT_USUARIO  = "GABRIEL.SANTOS"
BSOFT_SENHA    = "GG@p5005"

CODIGOS_ALVO   = ["09.007.005", "09.007.006"]  # adiantamento e saldo de frete
PASTA_SESSAO   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Bsoft_Session")
ARQUIVO_MEMORIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bsoft_memoria_pagar.json")

# =============================================================
# UTILITÁRIOS
# =============================================================

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).upper().strip()

PALAVRAS_GENERICAS = {
    'MADEIRAS','MADEIRA','COMERCIO','INDUSTRIA','TRANSPORTES','TRANSPORTE',
    'SERVICOS','SERVICO','MATERIAIS','MATERIAL','CONSTRUCAO','CONSTRUCOES',
    'DISTRIBUICAO','DISTRIBUIDORA','BRASIL','NORTE','NORDESTE','SUL',
    'LESTE','OESTE','SOLUCOES','SOLUCAO','SISTEMAS','GRUPO','CENTER','CENTRO'
}

def eh_especifica(p):
    p_up = p.upper()
    if p_up in PALAVRAS_GENERICAS: return False
    if len(p) < 3:
        return bool(re.search(r'\d', p)) or (len(p) == 2 and p.isupper())
    return True

def gerar_termos_busca(nome_completo):
    nome = remover_acentos(nome_completo)
    sufixos = r'\b(LTDA|S/?A|EIRELI|ME|EPP|CIA|DE|E|DO|DA|DOS|DAS|DISTRIBUIDORA|PAINEIS|COMPENSADOS)\b'
    nome_limpo = re.sub(sufixos, '', nome).strip()
    palavras = [p for p in nome_limpo.split() if p.strip() and len(p) >= 2]
    especificas    = [p for p in palavras if eh_especifica(p)]
    genericas      = [p for p in palavras if not eh_especifica(p)]
    especificas_ord = sorted(especificas, key=len, reverse=True)
    genericas_ord   = sorted(genericas,   key=len, reverse=True)
    termos = list(especificas_ord)
    for i in range(len(especificas_ord) - 1):
        termos.append(f"{especificas_ord[i]} {especificas_ord[i+1]}")
    if especificas_ord and genericas_ord:
        termos.append(f"{especificas_ord[0]} {genericas_ord[0]}")
    termos.extend(genericas_ord)
    vistos, resultado = set(), []
    for t in termos:
        t_norm = t.strip().upper()
        if t_norm and t_norm not in vistos:
            vistos.add(t_norm); resultado.append(t)
    return resultado[:10]

# =============================================================
# MEMÓRIA
# =============================================================

def carregar_memoria():
    try:
        if os.path.exists(ARQUIVO_MEMORIA):
            with open(ARQUIVO_MEMORIA, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {}

def salvar_memoria(memoria):
    try:
        with open(ARQUIVO_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.YELLOW + f"   ⚠️ Não foi possível salvar memória: {e}")

def chave_cliente(nome):
    return remover_acentos(str(nome)).strip().upper()

def confirmar_opcao_com_usuario(nome_cliente, opcoes_frete, valores_opcoes):
    print(Fore.YELLOW + Style.BRIGHT + f"\n      ⚠️  AMBIGUIDADE para '{nome_cliente}'")
    print(Fore.YELLOW + f"      {len(opcoes_frete)} opções com 'FRETE'. Qual é a correta?")
    print(Fore.WHITE  + "      " + "-"*50)
    for i, (idx_orig, texto) in enumerate(opcoes_frete):
        print(Fore.WHITE + f"      [{i+1}] {texto}")
    print(Fore.WHITE + f"      [0] Pular este título")
    print(Fore.WHITE + "      " + "-"*50)
    while True:
        try:
            escolha = input(Fore.CYAN + f"      👉 Digite (1-{len(opcoes_frete)}) ou 0 para pular: ").strip()
            num = int(escolha)
            if num == 0:
                return -1, "", ""
            if 1 <= num <= len(opcoes_frete):
                idx_orig, texto = opcoes_frete[num - 1]
                valor = valores_opcoes[idx_orig]
                print(Fore.GREEN + f"      ✅ '{texto}'")
                return idx_orig, texto, valor
        except (ValueError, KeyboardInterrupt): pass
        print(Fore.RED + f"      ❌ Inválido.")

def selecionar_melhor_opcao_frete(opcoes_texto, valores_opcoes, nome_cliente, memoria):
    """
    Seleciona o código gerencial correto para Títulos a Pagar.
    Prioridade:
      1. Memória — escolha já confirmada
      2. Código começando com 2.000040 + nome do cliente (padrão dos fretes)
      3. Opção única com FRETE
      4. Múltiplas opções com FRETE → pergunta usuário
      5. Fuzzy fallback
    """
    chave = chave_cliente(nome_cliente)

    # 1. Memória
    if chave in memoria:
        cod_mem = memoria[chave]
        for i, (texto, valor) in enumerate(zip(opcoes_texto, valores_opcoes)):
            if valor == cod_mem:
                print(Fore.GREEN + f"      💾 Memória: '{texto}'")
                return i, texto, valor, "MEMÓRIA"

    # 2. Prioridade: código 2.000040 + FRETE + nome do cliente
    termos = gerar_termos_busca(nome_cliente)
    opcoes_2000040_frete = []
    for i, texto in enumerate(opcoes_texto):
        t_upper = remover_acentos(texto)
        if "2.000040" in texto and "FRETE" in t_upper:
            opcoes_2000040_frete.append((i, texto))

    if len(opcoes_2000040_frete) == 1:
        i, t = opcoes_2000040_frete[0]
        return i, t, valores_opcoes[i], "2.000040 FRETE ÚNICO"

    if len(opcoes_2000040_frete) > 1:
        # Tenta achar o que tem o nome do cliente
        for termo in termos:
            for i, t in opcoes_2000040_frete:
                if remover_acentos(termo) in remover_acentos(t):
                    return i, t, valores_opcoes[i], f"2.000040 + '{termo}'"
        # Ambiguidade → pergunta
        idx_orig, texto, valor = confirmar_opcao_com_usuario(
            nome_cliente, opcoes_2000040_frete, valores_opcoes
        )
        if idx_orig == -1:
            return -1, "", "", "PULADO PELO USUÁRIO"
        memoria[chave] = valor
        salvar_memoria(memoria)
        return idx_orig, texto, valor, "CONFIRMADO PELO USUÁRIO"

    # 3. Qualquer opção com FRETE
    opcoes_frete = [(i, t) for i, t in enumerate(opcoes_texto) if "FRETE" in remover_acentos(t)]

    if len(opcoes_frete) == 1:
        i, t = opcoes_frete[0]
        return i, t, valores_opcoes[i], "FRETE ÚNICO"

    if len(opcoes_frete) > 1:
        # Tenta match com nome
        for termo in termos:
            for i, t in opcoes_frete:
                if remover_acentos(termo) in remover_acentos(t):
                    return i, t, valores_opcoes[i], f"FRETE + '{termo}'"
        # Ambiguidade → pergunta
        idx_orig, texto, valor = confirmar_opcao_com_usuario(
            nome_cliente, opcoes_frete, valores_opcoes
        )
        if idx_orig == -1:
            return -1, "", "", "PULADO PELO USUÁRIO"
        memoria[chave] = valor
        salvar_memoria(memoria)
        return idx_orig, texto, valor, "CONFIRMADO PELO USUÁRIO"

    # 4. Fuzzy fallback
    if RAPIDFUZZ_OK and opcoes_texto:
        primeiro = termos[0] if termos else nome_cliente
        res = fuzz_process.extract(primeiro, [remover_acentos(o) for o in opcoes_texto],
                                   scorer=fuzz.partial_ratio, limit=1)
        if res and res[0][1] >= 60:
            idx = res[0][2]
            return idx, opcoes_texto[idx], valores_opcoes[idx], f"Fuzzy {res[0][1]}%"

    if opcoes_texto:
        return 0, opcoes_texto[0], valores_opcoes[0], "PRIMEIRA DISPONÍVEL"

    return -1, "", "", "NÃO ENCONTRADO"

# =============================================================
# LOGIN
# =============================================================

def fazer_login(page):
    print(Fore.WHITE + "🔐 Verificando sessão...")
    try:
        page.goto(BSOFT_URL, timeout=30000)
        time.sleep(3)
        url = page.url.lower()
        print(Fore.CYAN + f"   🌐 {page.url}")
        if "login" not in url and len(url) > len(BSOFT_URL) + 5:
            print(Fore.GREEN + "✅ Sessão já ativa.")
            return True
        print(Fore.WHITE + "🔑 Realizando login...")
        page.wait_for_selector("input[type='text']", timeout=15000)
        page.locator("input[type='text']").first.fill(BSOFT_USUARIO)
        time.sleep(0.4)
        page.locator("input[type='password']").first.fill(BSOFT_SENHA)
        time.sleep(0.4)
        page.locator("button:has-text('Entrar')").first.click()
        try: page.wait_for_url("**index.php**", timeout=20000)
        except: pass
        time.sleep(3)
        print(Fore.CYAN + f"   🌐 {page.url}")
        if "login" not in page.url.lower():
            print(Fore.GREEN + "✅ Login OK!")
            return True
        print(Fore.RED + "❌ Login falhou.")
        return False
    except Exception as e:
        print(Fore.RED + f"❌ {e}")
        return False

# =============================================================
# NAVEGAÇÃO PARA TÍTULOS A PAGAR
# =============================================================

def ir_para_titulos_pagar(page):
    print(Fore.WHITE + "📂 Navegando para Títulos a Pagar...")
    try:
        url = f"{BSOFT_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=finan_faturas_pagar"
        page.goto(url, timeout=30000)
        try: page.wait_for_load_state("networkidle", timeout=15000)
        except: pass
        time.sleep(3)
        print(Fore.CYAN + f"   🌐 {page.url}")
        print(Fore.GREEN + "✅ Títulos a Pagar carregado.")
        return True
    except Exception as e:
        print(Fore.RED + f"❌ {e}")
        return False

def obter_frame_lista(page):
    for frame in page.frames:
        url_f = frame.url.lower()
        if "finan_faturas_pagar" in url_f or "lista" in url_f:
            return frame
    for iframe_el in page.locator("iframe").all():
        try:
            frame = iframe_el.content_frame()
            if frame and "blank" not in frame.url:
                return frame
        except: continue
    return page

def obter_frame_formulario(page):
    for frame in page.frames:
        url_f = frame.url.lower()
        if "formulario" in url_f or "op=o3" in url_f:
            return frame
    for frame in page.frames:
        try:
            if frame.locator("input[name='dados_numero']").count() > 0:
                return frame
        except: continue
    return page

# =============================================================
# FILTRO
# =============================================================

def aplicar_filtro(frame, codigo):
    print(Fore.WHITE + f"🔍 Filtrando por Código Gerencial CONTENDO '{codigo}'...")
    try:
        # Limpa filtros anteriores — usa RG.lBR (função oficial do bsoft)
        frame.evaluate("""() => {
            // RG.lBR é o onclick do botão Limpar nativo do bsoft
            const btnLimpar = document.querySelector("input[value='Limpar']");
            if (btnLimpar) {
                try { RG.lBR(btnLimpar); } catch(e) { btnLimpar.click(); }
            }
            // Remove tags de filtro ativas como fallback
            document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]').forEach(a => {
                try { a.click(); } catch(e) {}
            });
        }""")
        time.sleep(1.5)

        # Abre filtro avançado e aplica
        frame.locator("img[title='Filtro Avançado']").first.click()
        time.sleep(2)
        frame.locator("select[name='campos[1]']").select_option(value="filtroCodigoGerencial")
        time.sleep(0.4)
        frame.locator("select[name='operador[1]']").select_option(value="like")
        time.sleep(0.4)
        frame.locator("input[name='valores[]']").last.fill(codigo)
        time.sleep(0.3)
        frame.locator("input[name='bs'][value='Filtrar']").click()
        time.sleep(3)
        print(Fore.GREEN + "✅ Filtro aplicado.")
        return True
    except Exception as e:
        print(Fore.RED + f"❌ Erro no filtro: {e}")
        return False

# =============================================================
# COLETA DOS TÍTULOS
# =============================================================

def coletar_ids_titulos(frame):
    titulos, ids_vistos = [], set()
    pagina_num = 1
    while True:
        print(Fore.WHITE + f"   📋 Coletando — página {pagina_num}...")
        time.sleep(2)
        try:
            # Debug: mostra swni disponíveis na primeira linha (só na pág 1)
            if pagina_num == 1:
                swnis = frame.evaluate("""() => {
                    const tr = document.querySelector('table tbody tr');
                    if (!tr) return [];
                    return Array.from(tr.querySelectorAll('td[swni]'))
                        .map(td => td.getAttribute('swni') + '=' + td.innerText.trim().substring(0,20));
                }""")
                print(Fore.MAGENTA + f"   🔍 DEBUG swni: {swnis}")
            dados = frame.evaluate("""() => {
                const resultado = [];
                document.querySelectorAll('table tbody tr').forEach(tr => {
                    const cb = tr.querySelector('input[name="id"]');
                    const tdFornec = tr.querySelector('td[swni="fornecedor"]')
                                  || tr.querySelector('td[swni="cliente"]');
                    const tdNumero = tr.querySelector('td[swni="numero"]');
                    const tdData   = tr.querySelector('td[swni="data_de_emissao"]')
                                  || tr.querySelector('td[swni="emissao"]')
                                  || tr.querySelector('td[swni="data"]');
                    if (cb && cb.value) {
                        resultado.push({
                            id: cb.value,
                            fornecedor: tdFornec ? tdFornec.innerText.trim() : '',
                            numero: tdNumero ? tdNumero.innerText.trim() : '',
                            emissao: tdData ? tdData.innerText.trim() : ''
                        });
                    }
                });
                return resultado;
            }""")
            print(Fore.CYAN + f"   📊 Linhas brutas: {len(dados)}")
            if not dados: break
            novos = 0
            for item in dados:
                tid = item['id']
                if tid in ids_vistos:
                    continue
                # Filtra títulos com data de emissão anterior a Jan/2026
                emissao = item.get('emissao', '')
                if emissao:
                    try:
                        # Formato DD/MM/YYYY
                        partes = emissao.split('/')
                        if len(partes) == 3:
                            ano, mes = int(partes[2]), int(partes[1])
                            if ano < 2026 or (ano == 2026 and mes < 1):
                                print(Fore.WHITE + f"      ⏭️ #{tid} — emissão {emissao} (anterior a Jan/2026) — pulado")
                                ids_vistos.add(tid)
                                continue
                    except Exception:
                        pass
                # Ignora linha de cabeçalho (texto literal em vez de dados)
                fornec = item['fornecedor'].strip().lower()
                emissao_chk = emissao.strip().lower()
                if fornec in ('fornecedor', 'cliente', '') or emissao_chk in ('data de emissão', 'data de emissao', ''):
                    ids_vistos.add(tid)
                    continue
                ids_vistos.add(tid)
                titulos.append({"codigo": tid, "fornecedor": item['fornecedor'], "numero": item.get('numero', '')})
                print(Fore.WHITE + f"      #{tid} — {item['fornecedor']} — nº {item.get('numero','?')} — {emissao}")
                novos += 1
            if novos == 0: break
            # Botão próxima página — tenta múltiplos seletores
            btn_prox = frame.locator("a[title='Próxima página']").first
            if btn_prox.count() == 0 or not btn_prox.is_visible():
                # Fallback: ícone fa-caret-right dentro de link
                btn_prox = frame.locator("a:has(i.fa-caret-right), a:has(.fa-caret-right)").last
            if btn_prox.count() > 0 and btn_prox.is_visible():
                btn_prox.click(); pagina_num += 1; time.sleep(2)
            else:
                break
        except Exception as e:
            print(Fore.RED + f"   ❌ {e}"); break
    print(Fore.GREEN + f"   ✅ {len(titulos)} título(s) únicos.")
    return titulos

# =============================================================
# PROCESSAR UM TÍTULO A PAGAR
# =============================================================

def abrir_titulo_pagar(page, titulo_id):
    url = (f"{BSOFT_URL}/versoes/versao5.0/rotinas/formulario.php"
           f"?rotina=finan_faturas_pagar&OP=O3&id={titulo_id}")
    print(Fore.WHITE + f"   🌐 Abrindo título #{titulo_id}")
    try:
        page.goto(url, timeout=30000)
        # Aguarda qualquer elemento do formulário aparecer
        try:
            page.wait_for_selector(
                "input[name='dados_numero'], input[name='botao_finalizacao'], fieldset",
                timeout=8000
            )
        except:
            pass
        time.sleep(1)
        return True
    except Exception as e:
        print(Fore.RED + f"   ❌ {e}"); return False

def ler_numero_titulo(page):
    """
    Lê o número do talão/recibo do título a pagar.
    O número fica em td[swni="numero"] na tela do formulário.
    Ex: <td align="right" swni="numero">258</td>
    """
    try:
        numero = page.evaluate("""() => {
            // Número do talão fica em td[swni="numero"]
            const td = document.querySelector('td[swni="numero"]');
            if (td) return td.innerText.trim();
            // Fallback: input dados_numero
            const inp = document.querySelector("input[name='dados_numero']");
            if (inp) return (inp.value || inp.getAttribute('value') || '').trim();
            return '';
        }""")
        return numero or ""
    except Exception as e:
        print(Fore.YELLOW + f"      ⚠️ Erro ao ler número: {e}")
        return ""

def buscar_cliente_via_contrato(page, context, numero_titulo):
    """
    Dado o número do título (ex: 257):
    1. Abre Contrato de Frete em nova aba
    2. Filtra pelo número via JS direto
    3. Clica em Editar no resultado
    4. Lê o número do CT-e
    5. Abre CT-e em nova aba, filtra, lê o cliente
    """
    if not numero_titulo:
        print(Fore.RED + "   ❌ Número do título vazio.")
        return ""

    print(Fore.WHITE + f"   🔗 Buscando cliente via contrato #{numero_titulo}...")
    aba_contrato = None

    try:
        # ── PASSO A: Abre Contrato de Frete ──────────────────────────
        url_contrato = (f"{BSOFT_URL}/versoes/versao5.0/rotinas/"
                        f"carrega_rotina.php?id=transp_contratoFrete")
        aba_contrato = context.new_page()
        aba_contrato.goto(url_contrato, timeout=30000)
        try: aba_contrato.wait_for_load_state("networkidle", timeout=12000)
        except: pass
        time.sleep(3)
        aba_contrato.keyboard.press("Escape")  # fecha qualquer popup
        time.sleep(0.5)

        print(Fore.CYAN + f"      🌐 Contrato URL: {aba_contrato.url}")

        # ── PASSO B: Preenche e filtra via JS ────────────────────────
        print(Fore.WHITE + f"      📋 Filtrando pelo número {numero_titulo}...")
        aba_contrato.evaluate(f"""() => {{
            // 1. Limpa filtros — usa RG.lBR (função oficial do bsoft)
            const btnLimpar = document.querySelector("input[value='Limpar']");
            if (btnLimpar) {{
                try {{ RG.lBR(btnLimpar); }} catch(e) {{ btnLimpar.click(); }}
            }}

            // 2. Remove tags de filtro ativas
            document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]').forEach(a => {{
                try {{ a.click(); }} catch(e) {{}}
            }});

            // 3. Limpa todos os inputs de busca rápida
            document.querySelectorAll('input[name^="busca_"]').forEach(inp => {{
                inp.value = '';
            }});

            // 4. Força abertura do painel de filtro
            const header = document.querySelector('.rg-busca-rapida__cabecalho');
            if (header) {{
                const chevron = header.querySelector('.fa-chevron-up, .fa-chevron-down');
                if (chevron) chevron.parentElement.click();
            }}

            // 5. Preenche o campo de número do talão
            const campo = document.querySelector(
                "input[name='busca_transp_reciboFrete_nroRecibo']"
            );
            if (campo) {{
                campo.value = '{numero_titulo}';
                campo.dispatchEvent(new Event('input', {{bubbles:true}}));
                campo.dispatchEvent(new Event('change', {{bubbles:true}}));
            }}

            // 6. Clica em Filtrar
            const btn = document.querySelector("input[value='Filtrar']");
            if (btn) btn.click();
        }}""")
        time.sleep(3)

        # Diagnóstico: quantas linhas apareceram?
        n_linhas = aba_contrato.evaluate("""() => {
            return document.querySelectorAll('table tbody tr').length;
        }""")
        print(Fore.CYAN + f"      📊 Linhas na tabela: {n_linhas}")

        # ── PASSO C: Clique direito na linha → Editar ────────────────
        # O bsoft pode abrir o formulário na mesma aba ou numa nova aba
        # Usamos expect_page para capturar nova aba se abrir
        try:
            linha_alvo = aba_contrato.locator(
                f"td[swni='numerotalao']:has-text('{numero_titulo}')"
            ).first
            if linha_alvo.count() == 0:
                linha_alvo = aba_contrato.locator("table tbody tr td").first

            # Pega o ID do contrato pelo checkbox da linha
            id_contrato = aba_contrato.evaluate(f"""() => {{
                const tds = document.querySelectorAll('td[swni="numerotalao"]');
                for (const td of tds) {{
                    if (td.innerText.includes('{numero_titulo}')) {{
                        const tr = td.closest('tr');
                        if (tr) {{
                            const cb = tr.querySelector('input[name="id"]');
                            if (cb) return cb.value;
                        }}
                    }}
                }}
                // fallback: primeiro checkbox
                const cb = document.querySelector('input[name="id"]');
                return cb ? cb.value : '';
            }}""")

            print(Fore.CYAN + f"      🆔 ID do contrato: {id_contrato}")

            # Navega diretamente para o formulário do contrato pela URL
            # Evita problemas com menu de contexto e novas abas
            if id_contrato:
                url_form_contrato = (
                    f"{BSOFT_URL}/versoes/versao5.0/rotinas/formulario.php"
                    f"?rotina=transp_contratoFrete&OP=O3&id={id_contrato}"
                )
                aba_contrato.goto(url_form_contrato, timeout=30000)
                try: aba_contrato.wait_for_load_state("networkidle", timeout=12000)
                except: pass
                time.sleep(3)
            else:
                # Fallback: clique direito + menu contexto
                linha_alvo.click(button="right", force=True)
                time.sleep(1)
                btn_ctx = aba_contrato.locator(
                    "a.item-de-contexto:has(img[title='Editar'])"
                ).first
                if btn_ctx.count() > 0:
                    btn_ctx.click(force=True)
                    time.sleep(3)

        except Exception as e:
            print(Fore.YELLOW + f"      ⚠️ Abrir contrato: {e}")

        try: aba_contrato.wait_for_load_state("networkidle", timeout=10000)
        except: pass
        time.sleep(2)

        print(Fore.CYAN + f"      🌐 URL contrato: {aba_contrato.url}")

        # ── PASSO D: Lê o número do CT-e ─────────────────────────────
        numero_cte = aba_contrato.evaluate(r"""() => {
            const tds = document.querySelectorAll('td');
            for (const td of tds) {
                const txt = td.innerText || '';
                const m = txt.match(/CT:\s*(\d+)\/CT-e/i)
                       || txt.match(/(\d{3,})\/CT-e/i);
                if (m) return m[1];
            }
            return '';
        }""")

        print(Fore.CYAN + f"      📄 CT-e: '{numero_cte}'")

        if not numero_cte:
            print(Fore.RED + "      ❌ CT-e não encontrado.")
            aba_contrato.close()
            aba_contrato = None
            return ""

        # ── PASSO E: Abre CT-e na mesma aba via barra de pesquisa ────
        # Usa a barra de pesquisa do bsoft (drawer-menu__search-input)
        # para navegar para CT-e, igual ao que o usuário faz manualmente
        print(Fore.WHITE + f"      🔍 Abrindo CT-e via barra de pesquisa...")
        try:
            # Clica na barra de pesquisa e digita "CT-e"
            campo_busca = aba_contrato.locator("#drawer-menu__search-input").first
            campo_busca.click(force=True)
            time.sleep(0.5)
            campo_busca.fill("CT-e")
            time.sleep(1.5)

            # Clica no item CT-e no resultado da pesquisa
            item_cte = aba_contrato.locator(
                "a[href*='transp_cte'] span:has-text('CT-e'), "
                "span.drawer-menu__item__left span:has-text('CT-e'), "
                "a[href*='id=transp_cte']"
            ).first

            if item_cte.count() > 0:
                item_cte.click(force=True)
            else:
                # Fallback: navega direto pela URL do menu
                aba_contrato.goto(
                    f"{BSOFT_URL}/versoes/versao5.0/rotinas/c.php?id=transp_cte&menu=s",
                    timeout=30000
                )

            try: aba_contrato.wait_for_load_state("networkidle", timeout=12000)
            except: pass
            time.sleep(3)
            print(Fore.CYAN + f"      🌐 URL CT-e: {aba_contrato.url}")

        except Exception as e:
            print(Fore.YELLOW + f"      ⚠️ Abrindo CT-e: {e}")
            # Fallback direto
            aba_contrato.goto(
                f"{BSOFT_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=transp_conhecimentoTransporteReais",
                timeout=30000
            )
            try: aba_contrato.wait_for_load_state("networkidle", timeout=12000)
            except: pass
            time.sleep(3)

        # ── PASSO F: Filtra pelo número do CT-e ──────────────────────
        print(Fore.WHITE + f"      📋 Filtrando CT-e pelo número {numero_cte}...")

        # Aguarda o campo de número aparecer na página
        try:
            aba_contrato.wait_for_selector(
                "input[name='busca_transp_conhecimentoTransporteReais_nroConhecimento']",
                timeout=10000
            )
        except:
            print(Fore.YELLOW + "      ⚠️ Campo de número do CT-e não encontrado. Aguardando mais...")
            time.sleep(3)

        # Diagnóstico: verifica se o campo existe
        campo_existe = aba_contrato.evaluate("""() => {
            const c = document.querySelector(
                "input[name='busca_transp_conhecimentoTransporteReais_nroConhecimento']"
            );
            return c ? 'sim (style: ' + c.style.display + ')' : 'NAO ENCONTRADO';
        }""")
        print(Fore.CYAN + f"      🔍 Campo nroConhecimento: {campo_existe}")

        # Aplica o filtro
        def aplicar_filtro_cte():
            # Preenche o campo direto e filtra — sem RG.lBR que recarrega a página
            aba_contrato.evaluate(f"""() => {{
                // Remove apenas as tags de filtro ativas (X de cada tag)
                document.querySelectorAll('.remover-filtro, a[onclick*="removerFiltro"]').forEach(a => {{
                    try {{ a.click(); }} catch(e) {{}}
                }});

                // Abre o painel de filtro rápido se estiver fechado
                // fa-chevron-up = painel fechado (clica para abrir)
                const header = document.querySelector('.rg-busca-rapida__cabecalho');
                if (header) {{
                    const chevron = header.querySelector('i.fa-chevron-up');
                    if (chevron) chevron.parentElement.click();
                }}

                // Limpa APENAS o campo de número do CT-e
                document.querySelectorAll('input[name^="busca_"]').forEach(inp => {{
                    inp.value = '';
                }});

                // Preenche o campo com o número do CT-e
                const campo = document.querySelector(
                    "input[name='busca_transp_conhecimentoTransporteReais_nroConhecimento']"
                );
                if (campo) {{
                    // Força visibilidade
                    let el = campo;
                    while (el && el !== document.body) {{
                        if (el.style && el.style.display === 'none') el.style.display = '';
                        el = el.parentElement;
                    }}
                    campo.value = '{numero_cte}';
                    campo.dispatchEvent(new Event('input', {{bubbles:true}}));
                    campo.dispatchEvent(new Event('change', {{bubbles:true}}));
                }}

                // Clica em Filtrar
                const btn = document.querySelector("input[value='Filtrar']");
                if (btn) btn.click();
            }}""")

        aplicar_filtro_cte()
        time.sleep(4)

        n_linhas_cte = aba_contrato.evaluate("""() => {
            return document.querySelectorAll('table tbody tr').length;
        }""")
        print(Fore.CYAN + f"      📊 Linhas CT-e após filtro: {n_linhas_cte}")

        # Se ainda tiver muitas linhas, tenta de novo
        if n_linhas_cte > 5:
            print(Fore.YELLOW + f"      ⚠️ Filtro não reduziu ({n_linhas_cte} linhas). Tentando novamente...")
            time.sleep(2)
            aplicar_filtro_cte()
            time.sleep(4)
            n_linhas_cte = aba_contrato.evaluate("""() => {
                return document.querySelectorAll('table tbody tr').length;
            }""")
            print(Fore.CYAN + f"      📊 Linhas após 2ª tentativa: {n_linhas_cte}")

        # ── PASSO G: Lê o cliente da primeira linha de DADOS ─────────
        # td[swni="cliente__nome"] existe no cabeçalho (thead) e no corpo (tbody)
        # Precisamos pegar apenas do tbody para evitar o texto "Cliente - Nome"
        cliente = aba_contrato.evaluate("""() => {
            // Percorre linhas do tbody — ignora thead
            const linhas = document.querySelectorAll('table tbody tr');
            for (const tr of linhas) {
                const td = tr.querySelector('td[swni="cliente__nome"]')
                        || tr.querySelector('td[swni="cliente"]');
                if (td) {
                    const texto = td.innerText.trim();
                    // Ignora textos de cabeçalho ou vazios
                    if (texto
                        && texto.toLowerCase() !== 'cliente - nome'
                        && texto.toLowerCase() !== 'cliente'
                        && texto.length > 3) {
                        return texto;
                    }
                }
            }
            return '';
        }""")

        aba_contrato.close()
        aba_contrato = None

        print(Fore.GREEN + f"      👤 Cliente: '{cliente}'")
        return cliente, id_contrato

    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao buscar cliente: {e}")
        return "", ""
    finally:
        try:
            if aba_contrato: aba_contrato.close()
        except: pass


# =============================================================
# TROCAR CÓDIGO GERENCIAL (igual ao Títulos a Receber mas busca FRETE)
# =============================================================

def trocar_codigo_gerencial_pagar(frame, nome_cliente, memoria):
    termos = gerar_termos_busca(nome_cliente)
    print(Fore.WHITE + f"      🔎 Cliente: '{nome_cliente}' | Termos: {termos[:4]}")

    try:
        # Descobre qual select tem o código alvo
        info_linha = frame.evaluate(r"""() => {
            const codigos_alvo = ['09.007.005', '09.007.006', 'ADIANTAMENTO', 'SALDO DE FRETE'];
            const sels = document.querySelectorAll(
                "select[name^='dados_grupoApropriador_apropGerencial_codigo']"
            );
            for (let sel of sels) {
                const titulo = sel.getAttribute('title') || '';
                if (codigos_alvo.some(c => titulo.includes(c))) {
                    const match = sel.name.match(/\[(\d+)\]/);
                    const idx = match ? match[1] : '1';
                    const num = sel.id.replace('cswobj','');
                    return {
                        encontrado: true,
                        id_select: sel.id,
                        id_pesquisa: 'pswobj' + num,
                        titulo_atual: titulo
                    };
                }
            }
            if (sels.length > 0) {
                const sel = sels[0];
                const num = sel.id.replace('cswobj','');
                return {
                    encontrado: false,
                    id_select: sel.id,
                    id_pesquisa: 'pswobj' + num,
                    titulo_atual: sel.getAttribute('title') || ''
                };
            }
            return {encontrado: false, erro: 'nenhum select'};
        }""")

        print(Fore.CYAN + f"      🎯 Linha: {info_linha}")
        if info_linha.get('erro'):
            return False, "", "SELECT NÃO ENCONTRADO"

        id_pesquisa = info_linha['id_pesquisa']
        id_select   = info_linha['id_select']

        # Tenta cada termo até achar resultados
        textos_opcoes, valores_opcoes, termo_usado = [], [], ""

        for termo in termos:
            frame.evaluate(f"""() => {{
                const campo = document.getElementById('{id_pesquisa}');
                if (!campo) return;
                let el = campo;
                while (el && el !== document.body) {{
                    if (el.style && el.style.display === 'none') el.style.display = '';
                    if (el.style && el.style.visibility === 'hidden') el.style.visibility = '';
                    el = el.parentElement;
                }}
                campo.value = '{termo}';
                const lupas = document.querySelectorAll(
                    "i[name='botaoPesquisa_dados_grupoApropriador_apropGerencial_codigo']"
                );
                let prox = null, menorDist = Infinity;
                lupas.forEach(l => {{
                    const r1 = campo.getBoundingClientRect(), r2 = l.getBoundingClientRect();
                    const d = Math.abs(r1.top-r2.top)+Math.abs(r1.left-r2.left);
                    if (d < menorDist) {{ menorDist = d; prox = l; }}
                }});
                if (prox) prox.click();
                else campo.dispatchEvent(new KeyboardEvent('keydown', {{key:'Enter',keyCode:13,bubbles:true}}));
            }}""")
            time.sleep(2.5)

            opcoes = frame.evaluate(f"""() => {{
                const sel = document.getElementById('{id_select}');
                if (!sel) return [];
                return Array.from(sel.options)
                    .filter(o => o.value && o.value !== '0' && !o.disabled && o.text.trim())
                    .map(o => ({{value: o.value, text: o.text.trim()}}));
            }}""")

            textos_opcoes  = [o['text']  for o in opcoes]
            valores_opcoes = [o['value'] for o in opcoes]

            if textos_opcoes:
                termo_usado = termo
                print(Fore.CYAN + f"      🔍 '{termo}' → {len(textos_opcoes)} opção(ões)")
                break
            else:
                print(Fore.WHITE + f"      🔍 '{termo}' → sem resultados...")

        if not textos_opcoes:
            print(Fore.RED + f"      ❌ Nenhuma opção encontrada para '{nome_cliente}'.")
            return False, "", "SEM RESULTADOS"

        print(Fore.WHITE + f"      📋 Opções:")
        for t in textos_opcoes:
            print(Fore.WHITE + f"         - {t}")

        # Seleciona a melhor opção (procurando FRETE)
        idx, opcao, valor, metodo = selecionar_melhor_opcao_frete(
            textos_opcoes, valores_opcoes, nome_cliente, memoria
        )
        if idx == -1:
            return False, "", metodo

        print(Fore.CYAN + f"      ✨ Selecionando ({metodo}): '{opcao}'")

        # Aplica a seleção com as funções internas do bsoft
        frame.evaluate(f"""() => {{
            const sel = document.getElementById('{id_select}');
            if (!sel) return;
            sel.value = '{valor}';
            try {{ validaContasSinteticas(sel); }} catch(e) {{}}
            try {{ validaPreenchimento(); }} catch(e) {{}}
            try {{ Sisweb.aplicarTitle(sel.name, 'select-one'); }} catch(e) {{}}
            sel.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}""")
        time.sleep(1)

        return True, opcao, metodo

    except Exception as e:
        print(Fore.RED + f"      ❌ Erro: {e}")
        return False, "", f"ERRO: {e}"

def salvar_titulo(frame):
    try:
        resultado = frame.evaluate("""() => {
            const btn = document.querySelector("input[name='botao_finalizacao'][value='Salvar']")
                     || document.querySelector("input[id='botao_salvar']");
            if (!btn) return {ok: false, erro: 'botao nao encontrado'};
            
            // O Títulos a Pagar usa RG.trocaPasso no onclick
            // O Títulos a Receber usa RG.postaalteracao
            // Tentamos os dois
            try {
                RG.trocaPasso(btn, '1', true, 0);
                return {ok: true, m: 'RG.trocaPasso'};
            } catch(e1) {
                try {
                    RG.postaalteracao(btn, document.forms[0]);
                    return {ok: true, m: 'RG.postaalteracao'};
                } catch(e2) {
                    btn.click();
                    return {ok: true, m: 'click', e1: e1.toString()};
                }
            }
        }""")
        print(Fore.CYAN + f"      💾 Salvar: {resultado}")
        if resultado and resultado.get('ok'):
            time.sleep(4); return True
        print(Fore.YELLOW + f"      ⚠️ {resultado}")
        return False
    except Exception as e:
        print(Fore.RED + f"      ❌ {e}"); return False

# =============================================================
# LOOP PRINCIPAL
# =============================================================

def executar_titulos_pagar():
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + "   ROBÔ BSOFT TMS — TÍTULOS A PAGAR")
    print(Fore.BLUE + Style.BRIGHT + f"   Códigos alvo: {' e '.join(CODIGOS_ALVO)}")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65 + "\n")

    memoria = carregar_memoria()
    print(Fore.CYAN + f"💾 Memória: {len(memoria)} cliente(s) mapeados.")
    relatorio = []
    os.makedirs(PASTA_SESSAO, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PASTA_SESSAO,
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = browser.new_page()

        try:
            if not fazer_login(page):
                print(Fore.RED + "❌ Login falhou."); return

            # Processa cada código alvo separadamente
            todos_titulos = []
            for codigo_alvo in CODIGOS_ALVO:
                if not ir_para_titulos_pagar(page):
                    continue
                frame_lista = obter_frame_lista(page)
                if not aplicar_filtro(frame_lista, codigo_alvo):
                    print(Fore.YELLOW + f"⚠️ Filtro {codigo_alvo} não aplicado.")
                titulos = coletar_ids_titulos(frame_lista)
                for t in titulos:
                    t['codigo_gerencial'] = codigo_alvo
                    # Evita duplicata entre os dois códigos
                    if not any(x['codigo'] == t['codigo'] for x in todos_titulos):
                        todos_titulos.append(t)

            if not todos_titulos:
                print(Fore.WHITE + "\n☕ Nenhum título encontrado.")
                input("\nPressione Enter para fechar..."); return

            print(Fore.YELLOW + f"\n🎯 {len(todos_titulos)} título(s) para processar.\n")
            print(Fore.CYAN + "-" * 65)

            # Cache número_contrato → cliente
            # Preenchido ao processar cada título — sem fase de pré-coleta
            cache_numero_cliente = {}

            for idx, titulo in enumerate(todos_titulos):
                cod     = titulo["codigo"]
                cod_ger = titulo["codigo_gerencial"]

                print(Fore.YELLOW + f"\n[{idx+1}/{len(todos_titulos)}] Título #{cod} ({cod_ger})")

                # 1. Abre o título
                if not abrir_titulo_pagar(page, cod):
                    relatorio.append({"cod": cod, "cliente": "",
                                      "status": "ERRO - NAO ABRIU", "opcao": ""})
                    continue

                # 2. Usa o número já coletado da lista (td[swni="numero"])
                numero = titulo.get("numero", "").strip()
                print(Fore.WHITE + f"   🔢 Número: {numero}")

                if not numero:
                    print(Fore.RED + "   ❌ Número não encontrado. Pulando.")
                    relatorio.append({"cod": cod, "cliente": "",
                                      "status": "ERRO - SEM NUMERO", "opcao": ""})
                    continue

                # 3. Busca cliente — usa cache se número já foi processado
                if numero in cache_numero_cliente:
                    cliente = cache_numero_cliente[numero]
                    print(Fore.GREEN + f"   💾 Cache: #{numero} → '{cliente}'")
                else:
                    cliente, id_contrato = buscar_cliente_via_contrato(page, browser, numero)
                    if cliente and id_contrato:
                        # Guarda tanto pelo número do talão quanto pelo ID do contrato
                        cache_numero_cliente[numero] = cliente
                        cache_numero_cliente[id_contrato] = cliente
                        print(Fore.CYAN + f"   📌 Cache: #{numero} (id:{id_contrato}) → '{cliente}'")

                if not cliente:
                    print(Fore.RED + "   ❌ Cliente não encontrado. Pulando.")
                    relatorio.append({"cod": cod, "cliente": "",
                                      "status": "ERRO - SEM CLIENTE", "opcao": ""})
                    continue

                # 4. Reabre o título (busca_cliente pode ter navegado para outra tela)
                if not abrir_titulo_pagar(page, cod):
                    relatorio.append({"cod": cod, "cliente": cliente,
                                      "status": "ERRO - NAO REABRIU", "opcao": ""})
                    continue

                frame_form = obter_frame_formulario(page)

                # 5. Troca o Código Gerencial
                sucesso, opcao, metodo = trocar_codigo_gerencial_pagar(
                    frame_form, cliente, memoria
                )

                if sucesso:
                    salvou = salvar_titulo(frame_form)
                    if salvou:
                        print(Fore.GREEN + f"   ✅ Salvo! → {opcao}")
                        relatorio.append({"cod": cod, "cliente": cliente,
                                          "status": "OK", "opcao": opcao})
                    else:
                        print(Fore.YELLOW + "   ⚠️ Falha ao salvar.")
                        relatorio.append({"cod": cod, "cliente": cliente,
                                          "status": "ERRO - NAO SALVOU", "opcao": opcao})
                else:
                    status = "PULADO" if "PULADO" in metodo else f"ERRO - {metodo}"
                    print(Fore.YELLOW + f"   ⏭️ {status}")
                    relatorio.append({"cod": cod, "cliente": cliente,
                                      "status": status, "opcao": ""})
                time.sleep(1)

        except KeyboardInterrupt:
            print(Fore.RED + "\n🛑 Interrompido.")
        except Exception as e:
            print(Fore.RED + f"\n❌ Erro crítico: {e}")
        finally:
            print(Fore.BLUE + "\n" + "=" * 65)
            print(Fore.YELLOW + Style.BRIGHT + " 📊 RELATÓRIO FINAL")
            print(Fore.BLUE + "=" * 65)
            ok     = [r for r in relatorio if r["status"] == "OK"]
            erros  = [r for r in relatorio if "ERRO" in r["status"]]
            pulados= [r for r in relatorio if r["status"] == "PULADO"]
            print(Fore.GREEN  + f"  ✅ Alterados : {len(ok)}")
            print(Fore.YELLOW + f"  ⏭️  Pulados   : {len(pulados)}")
            print(Fore.RED    + f"  ❌ Erros      : {len(erros)}")
            if erros:
                print(Fore.RED + "\n  Erros:")
                for r in erros:
                    print(Fore.RED + f"    #{r['cod']} — {r.get('cliente','')} — {r['status']}")
            if ok:
                print(Fore.GREEN + "\n  Alterados:")
                for r in ok:
                    print(Fore.GREEN + f"    #{r['cod']} — {r.get('cliente','')} → {r['opcao']}")
            print(Fore.BLUE + "=" * 65)
            print(Fore.WHITE + f"\n  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            input(Fore.WHITE + "\nPressione Enter para fechar...")
            browser.close()

if __name__ == "__main__":
    try:
        executar_titulos_pagar()
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        input("\nPressione Enter para fechar...")