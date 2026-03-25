"""
bsoft_codigo_gerencial.py
=========================
Robô de automação para o bsoft TMS — Troca de Código Gerencial
em Títulos a Receber.

Fluxo:
  1. Faz login no bsoft TMS
  2. Vai em Títulos a Receber via carrega_rotina.php
  3. Aplica filtro avançado: Código Gerencial CONTENDO "08.002"
  4. Para cada título encontrado:
     a. Clica em Editar
     b. Lê o nome do cliente
     c. No campo de pesquisa de Código Gerencial, digita o primeiro nome
     d. Seleciona a opção com "Receita" + nome no dropdown
     e. Salva
  5. Gera relatório final
"""

import os
import time
import re
import json
import unicodedata
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
BSOFT_URL     = "https://nortenordeste.bsoft.app"
BSOFT_USUARIO = "GABRIEL.SANTOS"
BSOFT_SENHA   = "GG@p5005"
CODIGO_ALVO   = "08.002"
PASTA_SESSAO  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Bsoft_Session")

# Arquivo de memória — guarda as escolhas confirmadas pelo usuário
# para não perguntar de novo nas próximas rodadas
ARQUIVO_MEMORIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bsoft_memoria_clientes.json")

# =============================================================
# MEMÓRIA DE CLIENTES
# =============================================================

def carregar_memoria():
    """Carrega o mapa cliente → código gerencial do disco."""
    try:
        if os.path.exists(ARQUIVO_MEMORIA):
            with open(ARQUIVO_MEMORIA, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def salvar_memoria(memoria):
    """Salva o mapa cliente → código gerencial no disco."""
    try:
        with open(ARQUIVO_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.YELLOW + f"   ⚠️ Não foi possível salvar memória: {e}")

def chave_cliente(nome_cliente):
    """Normaliza o nome do cliente para usar como chave no JSON."""
    return remover_acentos(str(nome_cliente)).strip().upper()

def confirmar_opcao_com_usuario(nome_cliente, opcoes_receita, textos_opcoes, valores_opcoes):
    """
    Quando há ambiguidade (múltiplas opções com RECEITA), pausa e pergunta
    ao usuário qual é a opção correta. Retorna (idx, texto, value).
    """
    print(Fore.YELLOW + Style.BRIGHT + f"\n      ⚠️  AMBIGUIDADE DETECTADA para '{nome_cliente}'")
    print(Fore.YELLOW + f"      Encontrei {len(opcoes_receita)} opções com 'RECEITA'. Qual é a correta?")
    print(Fore.WHITE  + "      " + "-"*50)

    for i, (idx_orig, texto) in enumerate(opcoes_receita):
        print(Fore.WHITE + f"      [{i+1}] {texto}")

    print(Fore.WHITE + f"      [0] Pular este título (não alterar)")
    print(Fore.WHITE + "      " + "-"*50)

    while True:
        try:
            escolha = input(Fore.CYAN + f"      👉 Digite o número (1-{len(opcoes_receita)}) ou 0 para pular: ").strip()
            num = int(escolha)
            if num == 0:
                return -1, "", ""
            if 1 <= num <= len(opcoes_receita):
                idx_orig, texto_escolhido = opcoes_receita[num - 1]
                valor_escolhido = valores_opcoes[idx_orig]
                print(Fore.GREEN + f"      ✅ Escolhido: '{texto_escolhido}'")
                return idx_orig, texto_escolhido, valor_escolhido
        except (ValueError, KeyboardInterrupt):
            pass
        print(Fore.RED + f"      ❌ Número inválido. Digite entre 0 e {len(opcoes_receita)}.")

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

def primeiro_nome_cliente(nome_completo):
    """
    Extrai o melhor termo de busca do nome do cliente.
    Prioriza a palavra mais longa (mais específica) em vez de sempre pegar a primeira.
    Ex: "C P DE ARRUDA OLIVEIRA MADEIRAS" → "ARRUDA" (mais longa e específica)
        "GUARARAPES PAINEIS S.A."         → "GUARARAPES"
        "MADEIRAS REFLORESTADAS"           → "REFLORESTADAS"
    """
    if not nome_completo:
        return ""
    nome = remover_acentos(nome_completo)
    # Remove sufixos irrelevantes
    sufixos = r'\b(LTDA|S/?A|EIRELI|ME|EPP|CIA|COMERCIO|INDUSTRIA|IND|COM|DE|E|DO|DA|DOS|DAS|PAINEIS|COMPENSADOS|DISTRIBUIDORA|DISTRIBUCAO)\b'
    nome = re.sub(sufixos, '', nome).strip()
    palavras = [p for p in nome.split() if p.strip()]
    if not palavras:
        return nome_completo.split()[0].upper()
    # Pega a palavra mais longa com pelo menos 3 letras
    palavras_uteis = [p for p in palavras if len(p) >= 3]
    if palavras_uteis:
        return max(palavras_uteis, key=len)
    # Fallback: primeira palavra, mesmo que curta
    return palavras[0]

def gerar_termos_busca(nome_completo):
    """
    Gera lista de termos de busca em ordem inteligente.
    Palavras genéricas (MADEIRAS, COMERCIO, etc.) ficam por último
    porque retornam muitos resultados ambíguos.
    Ex: "C P DE ARRUDA OLIVEIRA MADEIRAS" →
        ["ARRUDA", "OLIVEIRA", "ARRUDA OLIVEIRA", "MADEIRAS"]
    """
    # Palavras muito genéricas que causam ambiguidade — vão para o fim
    PALAVRAS_GENERICAS = {
        'MADEIRAS', 'MADEIRA', 'COMERCIO', 'INDUSTRIA', 'TRANSPORTES',
        'TRANSPORTE', 'SERVICOS', 'SERVICO', 'MATERIAIS', 'MATERIAL',
        'CONSTRUCAO', 'CONSTRUCOES', 'DISTRIBUICAO', 'DISTRIBUIDORA',
        'BRASIL', 'NORTE', 'NORDESTE', 'SUL', 'LESTE', 'OESTE',
        'SOLUCOES', 'SOLUCAO', 'SISTEMAS', 'GRUPO', 'CENTER', 'CENTRO'
    }

    nome = remover_acentos(nome_completo)
    sufixos = r'\b(LTDA|S/?A|EIRELI|ME|EPP|CIA|DE|E|DO|DA|DOS|DAS|DISTRIBUIDORA|PAINEIS|COMPENSADOS)\b'
    nome_limpo = re.sub(sufixos, '', nome).strip()
    palavras = [p for p in nome_limpo.split() if p.strip() and len(p) >= 2]

    # Separa em específicas e genéricas
    # Inclui palavras curtas alfanuméricas como G5, RF, CDP (têm número ou são siglas)
    def eh_especifica(p):
        p_up = p.upper()
        if p_up in PALAVRAS_GENERICAS:
            return False
        if len(p) < 3:
            # Mantém se tiver dígito (G5, RF2) ou parecer sigla com maiúscula
            return bool(re.search(r'\d', p)) or (len(p) == 2 and p.isupper())
        return True

    especificas = [p for p in palavras if eh_especifica(p)]
    genericas   = [p for p in palavras if not eh_especifica(p)]

    # Ordena específicas por tamanho (maior = mais única)
    especificas_ord = sorted(especificas, key=len, reverse=True)
    genericas_ord   = sorted(genericas,   key=len, reverse=True)

    termos = []

    # 1. Específicas primeiro
    termos.extend(especificas_ord)

    # 2. Combos de 2 palavras específicas
    for i in range(len(especificas_ord) - 1):
        combo = f"{especificas_ord[i]} {especificas_ord[i+1]}"
        termos.append(combo)

    # 3. Combo específica + genérica
    if especificas_ord and genericas_ord:
        termos.append(f"{especificas_ord[0]} {genericas_ord[0]}")

    # 4. Genéricas por último (só se necessário)
    termos.extend(genericas_ord)

    # Remove duplicatas mantendo ordem
    vistos = set()
    resultado = []
    for t in termos:
        t_norm = t.strip().upper()
        if t_norm and t_norm not in vistos:
            vistos.add(t_norm)
            resultado.append(t)

    return resultado[:10]

def selecionar_melhor_opcao(opcoes_texto, valores_opcoes, nome_cliente, memoria):
    """
    Escolhe a melhor opção do dropdown na seguinte ordem:
      1. Memória — se o cliente já foi confirmado antes, usa direto
      2. Opção única com RECEITA — seleciona automaticamente
      3. Múltiplas opções com RECEITA — pausa e pergunta ao usuário
      4. Fuzzy matching como último recurso
    
    Retorna (idx, texto, valor, metodo)
    """
    nome_upper = remover_acentos(nome_cliente)
    chave = chave_cliente(nome_cliente)

    # Prioridade 1: Memória — escolha já confirmada anteriormente
    if chave in memoria:
        codigo_memorizado = memoria[chave]
        for i, (texto, valor) in enumerate(zip(opcoes_texto, valores_opcoes)):
            if valor == codigo_memorizado or remover_acentos(texto) == remover_acentos(codigo_memorizado):
                print(Fore.GREEN + f"      💾 Memória: usando '{texto}' (confirmado anteriormente)")
                return i, texto, valor, "MEMÓRIA"

    # Coleta todas as opções que contêm RECEITA
    opcoes_receita = []
    for i, texto in enumerate(opcoes_texto):
        if "RECEITA" in remover_acentos(texto):
            opcoes_receita.append((i, texto))

    # Prioridade 2: Só uma opção com RECEITA → automático
    if len(opcoes_receita) == 1:
        i, texto = opcoes_receita[0]
        return i, texto, valores_opcoes[i], "RECEITA ÚNICA"

    # Prioridade 3: Múltiplas opções com RECEITA → pergunta usuário
    if len(opcoes_receita) > 1:
        idx_orig, texto_escolhido, valor_escolhido = confirmar_opcao_com_usuario(
            nome_cliente, opcoes_receita, opcoes_texto, valores_opcoes
        )
        if idx_orig == -1:
            return -1, "", "", "PULADO PELO USUÁRIO"
        # Salva na memória para não perguntar de novo
        memoria[chave] = valor_escolhido
        salvar_memoria(memoria)
        print(Fore.GREEN + f"      💾 Memória salva: '{nome_cliente}' → '{texto_escolhido}'")
        return idx_orig, texto_escolhido, valor_escolhido, "CONFIRMADO PELO USUÁRIO"

    # Prioridade 4: Nenhuma opção com RECEITA → fuzzy como último recurso
    if RAPIDFUZZ_OK and opcoes_texto:
        primeiro = primeiro_nome_cliente(nome_cliente)
        resultados = fuzz_process.extract(
            primeiro,
            [remover_acentos(o) for o in opcoes_texto],
            scorer=fuzz.partial_ratio,
            limit=3
        )
        if resultados:
            melhor_texto, melhor_score, melhor_idx = resultados[0]
            if melhor_score >= 60:
                return melhor_idx, opcoes_texto[melhor_idx], valores_opcoes[melhor_idx], f"Fuzzy {melhor_score}%"

    # Última opção: primeira disponível
    if opcoes_texto:
        return 0, opcoes_texto[0], valores_opcoes[0], "PRIMEIRA DISPONÍVEL"

    return -1, "", "", "NÃO ENCONTRADO"

# =============================================================
# LOGIN
# =============================================================

def fazer_login(page):
    print(Fore.WHITE + "🔐 Verificando sessão no bsoft TMS...")
    try:
        page.goto(BSOFT_URL, timeout=30000)
        time.sleep(3)

        url_atual = page.url.lower()
        print(Fore.CYAN + f"   🌐 URL atual: {page.url}")

        ja_logado = (
            "login" not in url_atual and
            ("index.php" in url_atual or "area_trabalho" in url_atual or
             "rotina" in url_atual or "message_collection" in url_atual)
        )
        if ja_logado:
            print(Fore.GREEN + "✅ Sessão já ativa.")
            return True

        print(Fore.WHITE + "🔑 Realizando login...")
        page.wait_for_selector("input[type='text']", timeout=15000)

        page.locator("input[type='text']").first.fill(BSOFT_USUARIO)
        time.sleep(0.4)
        page.locator("input[type='password']").first.fill(BSOFT_SENHA)
        time.sleep(0.4)
        page.locator("button:has-text('Entrar')").first.click()

        print(Fore.WHITE + "   ⏳ Aguardando redirecionamento...")
        try:
            page.wait_for_url("**index.php**", timeout=20000)
        except:
            pass

        time.sleep(3)
        url_pos = page.url.lower()
        print(Fore.CYAN + f"   🌐 URL pós-login: {page.url}")

        if "login" not in url_pos and len(url_pos) > len(BSOFT_URL.lower()) + 5:
            print(Fore.GREEN + "✅ Login realizado com sucesso!")
            return True

        print(Fore.RED + f"❌ Login falhou.")
        return False

    except Exception as e:
        print(Fore.RED + f"❌ Falha no login: {e}")
        return False

# =============================================================
# NAVEGAÇÃO PARA TÍTULOS A RECEBER
# =============================================================

def ir_para_titulos_receber(page):
    print(Fore.WHITE + "📂 Navegando para Títulos a Receber...")
    try:
        url = f"{BSOFT_URL}/versoes/versao5.0/rotinas/carrega_rotina.php?id=finan_faturas_receber"
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        time.sleep(3)
        print(Fore.CYAN + f"   🌐 URL: {page.url}")
        print(Fore.CYAN + f"   🖼️ Frames: {len(page.frames)}")
        for i, f in enumerate(page.frames):
            print(Fore.CYAN + f"      Frame {i}: {f.url}")
        print(Fore.GREEN + "✅ Títulos a Receber carregado.")
        return True
    except Exception as e:
        print(Fore.RED + f"❌ Erro ao navegar: {e}")
        return False

def obter_frame_lista(page):
    """Retorna o frame onde está a tabela de títulos."""
    for frame in page.frames:
        url_f = frame.url.lower()
        if "finan_faturas_receber" in url_f or "lista" in url_f:
            return frame
    # Tenta qualquer iframe com conteúdo
    for iframe_el in page.locator("iframe").all():
        try:
            frame = iframe_el.content_frame()
            if frame and frame.url and frame.url != "about:blank":
                return frame
        except:
            continue
    return page

# =============================================================
# FILTRO AVANÇADO
# =============================================================

def aplicar_filtro_codigo_gerencial(frame, codigo=CODIGO_ALVO):
    print(Fore.WHITE + f"🔍 Aplicando filtro: Código Gerencial CONTENDO '{codigo}'...")
    try:
        # Limpa filtros anteriores — usa RG.lBR (função oficial do bsoft)
        frame.evaluate("""() => {
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

        # Clica na imagem do Filtro Avançado
        btn_filtro = frame.locator("img[title='Filtro Avançado']").first
        if btn_filtro.count() == 0:
            btn_filtro = frame.locator("img[title*='iltro']").first
        btn_filtro.click()
        time.sleep(2)

        frame.locator("select[name='campos[1]']").select_option(value="filtroCodigoGerencial")
        time.sleep(0.5)
        frame.locator("select[name='operador[1]']").select_option(value="like")
        time.sleep(0.5)
        frame.locator("input[name='valores[]']").last.fill(codigo)
        time.sleep(0.3)
        frame.locator("input[name='bs'][value='Filtrar']").click()
        time.sleep(3)

        print(Fore.GREEN + "✅ Filtro aplicado com sucesso.")
        return True

    except Exception as e:
        print(Fore.RED + f"❌ Erro ao aplicar filtro: {e}")
        return False

# =============================================================
# COLETA DOS TÍTULOS DA LISTA
# =============================================================

def coletar_ids_titulos(frame):
    """
    Coleta os IDs e clientes de todos os títulos listados.
    Usa JavaScript para pegar checkbox input[name='id'] e td[swni='cliente'].
    Deduplica por ID para não processar o mesmo título mais de uma vez.
    """
    titulos = []
    ids_vistos = set()
    pagina_num = 1

    while True:
        print(Fore.WHITE + f"   📋 Coletando — página {pagina_num}...")
        time.sleep(2)

        try:
            dados = frame.evaluate("""() => {
                const resultado = [];
                const linhas = document.querySelectorAll('table tbody tr');
                linhas.forEach(tr => {
                    const cb = tr.querySelector('input[name="id"]');
                    const tdCliente = tr.querySelector('td[swni="cliente"]');
                    if (cb && cb.value) {
                        resultado.push({
                            id: cb.value,
                            cliente: tdCliente ? tdCliente.innerText.trim() : ''
                        });
                    }
                });
                return resultado;
            }""")

            print(Fore.CYAN + f"   📊 Linhas brutas: {len(dados)}")

            if not dados:
                break

            novos = 0
            for item in dados:
                tid = item['id']
                if tid not in ids_vistos:
                    ids_vistos.add(tid)
                    titulos.append({"codigo": tid, "cliente": item['cliente']})
                    print(Fore.WHITE + f"      #{tid} — {item['cliente']}")
                    novos += 1

            if novos == 0:
                print(Fore.WHITE + "   ℹ️ Todos os IDs desta página já foram coletados.")
                break

            # Próxima página
            btn_prox = frame.locator("a[title='Próxima página']").first
            if btn_prox.count() > 0 and btn_prox.is_visible():
                btn_prox.click()
                pagina_num += 1
                time.sleep(2)
            else:
                break

        except Exception as e:
            print(Fore.RED + f"   ❌ Erro página {pagina_num}: {e}")
            break

    print(Fore.GREEN + f"   ✅ {len(titulos)} título(s) únicos coletados.")
    return titulos

# =============================================================
# ABRIR EDIÇÃO
# =============================================================

def abrir_edicao_titulo(page, titulo_id):
    """
    Abre o formulário de edição navegando diretamente pela URL.
    Evita o problema do modal/box interno do bsoft que torna
    os elementos invisíveis para o Playwright.
    """
    try:
        url_form = (
            f"{BSOFT_URL}/versoes/versao5.0/rotinas/formulario.php"
            f"?rotina=finan_faturas_receber&OP=O3&id={titulo_id}"
        )
        print(Fore.WHITE + f"   🌐 Abrindo formulário: ...id={titulo_id}")
        page.goto(url_form, timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        time.sleep(2)

        # Diagnóstico: lista frames disponíveis
        frames = page.frames
        print(Fore.CYAN + f"   🖼️ Frames após abrir formulário: {len(frames)}")
        for i, f in enumerate(frames):
            print(Fore.CYAN + f"      Frame {i}: {f.url[:80]}")

        return True

    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao abrir formulário #{titulo_id}: {e}")
        return False


def obter_frame_formulario(page):
    """
    Retorna o frame onde está o formulário de edição.
    O bsoft pode carregar o formulário em iframe ou na própria página.
    """
    # Procura frame com 'formulario' ou 'finan_faturas_receber' na URL
    for frame in page.frames:
        url_f = frame.url.lower()
        if "formulario" in url_f or ("finan_faturas_receber" in url_f and "op=o3" in url_f):
            print(Fore.CYAN + f"   🖼️ Frame formulário: {frame.url[:80]}")
            return frame

    # Procura frame com o campo do cliente (confirma que é o formulário)
    for frame in page.frames:
        try:
            if frame.locator("input[name='dados_cod_clienteAlteracao']").count() > 0:
                print(Fore.CYAN + f"   🖼️ Frame com campo cliente: {frame.url[:80]}")
                return frame
        except:
            continue

    # Tenta qualquer iframe com conteúdo relevante
    for iframe_el in page.locator("iframe").all():
        try:
            frame = iframe_el.content_frame()
            if frame and frame.url and "blank" not in frame.url:
                try:
                    if frame.locator("input[name='dados_cod_clienteAlteracao']").count() > 0:
                        return frame
                except:
                    pass
        except:
            continue

    print(Fore.WHITE + "   ℹ️ Usando page diretamente como frame do formulário.")
    return page

# =============================================================
# LER CLIENTE NO FORMULÁRIO
# =============================================================

def ler_cliente_formulario(frame):
    """Lê o nome do cliente do campo readonly no formulário de edição."""
    try:
        campo = frame.locator("input[name='dados_cod_clienteAlteracao']").first
        if campo.count() > 0:
            return campo.get_attribute("value") or ""
    except:
        pass
    return ""

# =============================================================
# TROCAR CÓDIGO GERENCIAL
# =============================================================

def trocar_codigo_gerencial(frame, nome_cliente, memoria):
    """
    Troca o Código Gerencial SUBSTITUINDO a linha existente com 08.002.
    """
    primeiro = primeiro_nome_cliente(nome_cliente)
    print(Fore.WHITE + f"      🔎 Buscando código para '{nome_cliente}' (termo: '{primeiro}')")

    try:
        # Passo 1: Descobre qual índice do select tem o 08.002
        info_linha = frame.evaluate(f"""() => {{
            const sels = document.querySelectorAll(
                "select[name^='dados_grupoApropriador_apropGerencial_codigo']"
            );
            
            for (let i = 0; i < sels.length; i++) {{
                const sel = sels[i];
                const titulo = sel.getAttribute('title') || '';
                
                if (titulo.includes('08.002') || titulo.includes('RECEITAS COM FRETES')) {{
                    const match = sel.name.match(/\\[(\\d+)\\]/);
                    const idx = match ? match[1] : '1';
                    const idCampo = sel.id; 
                    const numCampo = idCampo.replace('cswobj', '');
                    
                    return {{
                        encontrado: true,
                        idx_name: idx,
                        id_select: idCampo,
                        id_pesquisa: 'pswobj' + numCampo,
                        name_pesquisa: 'pesquisa_dados_grupoApropriador_apropGerencial_codigo',
                        titulo_atual: titulo,
                        num_campo: numCampo
                    }};
                }}
            }}
            
            if (sels.length > 0) {{
                const sel = sels[0];
                const match = sel.name.match(/\\[(\\d+)\\]/);
                const idx = match ? match[1] : '1';
                const idCampo = sel.id;
                const numCampo = idCampo.replace('cswobj', '');
                return {{
                    encontrado: false,
                    idx_name: idx,
                    id_select: idCampo,
                    id_pesquisa: 'pswobj' + numCampo,
                    name_pesquisa: 'pesquisa_dados_grupoApropriador_apropGerencial_codigo',
                    titulo_atual: sel.getAttribute('title') || '',
                    num_campo: numCampo
                }};
            }}
            
            return {{encontrado: false, erro: 'nenhum select encontrado'}};
        }}""")

        print(Fore.CYAN + f"      🎯 Linha alvo: {info_linha}")

        if info_linha.get('erro'):
            return False, "", "SELECT NÃO ENCONTRADO"

        id_pesquisa = info_linha['id_pesquisa']
        id_select   = info_linha['id_select']

        # Passo 2: Força visibilidade e preenche o campo de pesquisa da linha correta
        termos_busca = gerar_termos_busca(nome_cliente)
        print(Fore.WHITE + f"      🔎 Termos de busca: {termos_busca[:5]}")

        textos_opcoes  = []
        valores_opcoes = []
        termo_usado    = ""

        for termo in termos_busca:
            resultado_pesquisa = frame.evaluate(f"""() => {{
                const campo = document.getElementById('{id_pesquisa}');
                if (!campo) return {{ok: false, erro: 'campo nao encontrado'}};

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
                let lupaMaisProxima = null;
                let menorDistancia = Infinity;
                lupas.forEach(lupa => {{
                    const rect1 = campo.getBoundingClientRect();
                    const rect2 = lupa.getBoundingClientRect();
                    const dist = Math.abs(rect1.top - rect2.top) + Math.abs(rect1.left - rect2.left);
                    if (dist < menorDistancia) {{
                        menorDistancia = dist;
                        lupaMaisProxima = lupa;
                    }}
                }});

                if (lupaMaisProxima) {{
                    lupaMaisProxima.click();
                    return {{ok: true, metodo: 'lupa', termo: '{termo}'}};
                }}
                campo.dispatchEvent(new KeyboardEvent('keydown', {{key:'Enter', keyCode:13, bubbles:true}}));
                return {{ok: true, metodo: 'enter', termo: '{termo}'}};
            }}""")

            time.sleep(2.5)

            opcoes_dados = frame.evaluate(f"""() => {{
                const sel = document.getElementById('{id_select}');
                if (!sel) return [];
                return Array.from(sel.options)
                    .filter(o => o.value && o.value !== '0' && !o.disabled && o.text.trim())
                    .map(o => ({{value: o.value, text: o.text.trim()}}));
            }}""")

            textos_opcoes  = [o['text']  for o in opcoes_dados]
            valores_opcoes = [o['value'] for o in opcoes_dados]

            if textos_opcoes:
                termo_usado = termo
                print(Fore.CYAN + f"      🔍 '{termo}' → {len(textos_opcoes)} opção(ões) encontradas")
                break
            else:
                print(Fore.WHITE + f"      🔍 '{termo}' → sem resultados, tentando próximo...")

        if not textos_opcoes:
            print(Fore.RED + f"      ❌ Nenhuma opção para '{nome_cliente}'.")
            return False, "", "SEM RESULTADOS"

        # Passo 4: Escolhe melhor opção (com memória e confirmação interativa)
        idx, opcao_escolhida, valor_escolhido, metodo = selecionar_melhor_opcao(
            textos_opcoes, valores_opcoes, nome_cliente, memoria
        )

        if idx == -1:
            print(Fore.YELLOW + f"      ⏭️ Pulado: {metodo}")
            return False, "", metodo

        print(Fore.CYAN + f"      ✨ Selecionando ({metodo}): '{opcao_escolhida}'")

        # Passo 5: Seleciona no select CORRETO e executa validações do bsoft
        resultado_selecao = frame.evaluate(f"""() => {{
            const sel = document.getElementById('{id_select}');
            if (!sel) return {{ok: false, erro: 'select nao encontrado'}};

            sel.value = '{valor_escolhido}';

            try {{ validaContasSinteticas(sel); }} catch(e) {{}}
            try {{ validaPreenchimento(); }} catch(e) {{}}
            try {{ Sisweb.aplicarTitle(sel.name, 'select-one'); }} catch(e) {{}}
            sel.dispatchEvent(new Event('change', {{bubbles: true}}));

            const idx = sel.selectedIndex;
            return {{
                ok: true,
                valor_set: sel.value,
                texto_set: idx >= 0 ? sel.options[idx].text : '',
                id_usado: sel.id
            }};
        }}""")

        print(Fore.CYAN + f"      💾 Seleção: {resultado_selecao}")
        time.sleep(1)

        return True, opcao_escolhida, metodo

    except Exception as e:
        print(Fore.RED + f"      ❌ Erro: {e}")
        return False, "", f"ERRO: {e}"

# =============================================================
# SALVAR
# =============================================================

def salvar_titulo(frame):
    """
    Salva o formulário.
    Tenta RG.postaalteracao primeiro, depois submit direto do form.
    """
    try:
        resultado = frame.evaluate("""() => {
            const btn = document.querySelector("input[name='botao_finalizacao'][value='Salvar']")
                     || document.querySelector("input[id='botao_salvar']");
            if (!btn) return {ok: false, erro: 'botao nao encontrado'};
            
            // Tenta RG.postaalteracao (método oficial do bsoft)
            try {
                RG.postaalteracao(btn, document.forms[0]);
                return {ok: true, metodo: 'RG.postaalteracao'};
            } catch(e1) {
                // Fallback 1: submit direto do form
                try {
                    const form = document.forms[0];
                    if (form) {
                        form.submit();
                        return {ok: true, metodo: 'form.submit'};
                    }
                } catch(e2) {}
                // Fallback 2: click no botão
                btn.click();
                return {ok: true, metodo: 'btn.click', erro_rg: e1.toString()};
            }
        }""")

        print(Fore.CYAN + f"      💾 Salvar: {resultado}")

        if resultado and resultado.get('ok'):
            time.sleep(4)
            return True
        print(Fore.YELLOW + f"      ⚠️ {resultado}")
        return False

    except Exception as e:
        print(Fore.RED + f"      ❌ Erro ao salvar: {e}")
        return False

# =============================================================
# LOOP PRINCIPAL
# =============================================================

def executar_troca_codigos():
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + "   ROBÔ BSOFT TMS — TROCA DE CÓDIGO GERENCIAL")
    print(Fore.BLUE + Style.BRIGHT + f"   Substituindo: '{CODIGO_ALVO}' → Receita [Cliente]")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65 + "\n")

    relatorio = []
    os.makedirs(PASTA_SESSAO, exist_ok=True)

    # Carrega memória de escolhas anteriores
    memoria = carregar_memoria()
    print(Fore.CYAN + f"💾 Memória carregada: {len(memoria)} cliente(s) já mapeados.")
    if memoria:
        for k, v in list(memoria.items())[:5]:
            print(Fore.CYAN + f"   {k} → {v}")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PASTA_SESSAO,
            headless=False,
            viewport={"width": 1400, "height": 850},
        )
        page = browser.new_page()

        try:
            # 1. Login
            if not fazer_login(page):
                print(Fore.RED + "❌ Login falhou. Encerrando.")
                return

            # 2. Navega para Títulos a Receber
            if not ir_para_titulos_receber(page):
                print(Fore.RED + "❌ Navegação falhou. Encerrando.")
                return

            # 3. Obtém o frame da lista
            frame_lista = obter_frame_lista(page)

            # 4. Aplica filtro
            if not aplicar_filtro_codigo_gerencial(frame_lista, CODIGO_ALVO):
                print(Fore.YELLOW + "⚠️ Filtro não aplicado. Continuando com a lista atual...")

            # 5. Coleta IDs dos títulos
            titulos = coletar_ids_titulos(frame_lista)

            if not titulos:
                print(Fore.WHITE + "\n☕ Nenhum título encontrado com código gerencial '08.002'.")
                input("\nPressione Enter para fechar...")
                return

            print(Fore.YELLOW + f"\n🎯 {len(titulos)} título(s) para processar.\n")
            print(Fore.CYAN + "-" * 65)

            # 6. Processa cada título
            for idx, titulo in enumerate(titulos):
                cod = titulo["codigo"]
                cliente_lista = titulo["cliente"]

                print(Fore.YELLOW + f"\n[{idx+1}/{len(titulos)}] Título #{cod} — {cliente_lista}")

                # Abre o formulário navegando diretamente pela URL
                aberto = abrir_edicao_titulo(page, cod)
                if not aberto:
                    relatorio.append({"cod": cod, "cliente": cliente_lista,
                                      "status": "ERRO - NAO ABRIU", "opcao": ""})
                    continue

                # Obtém o frame correto do formulário
                frame_form = obter_frame_formulario(page)

                # Lê o nome do cliente no formulário
                cliente_form = ler_cliente_formulario(frame_form)
                nome_final = cliente_form if cliente_form else cliente_lista
                print(Fore.WHITE + f"   👤 Cliente: {nome_final}")

                # Troca o código gerencial (passa a memória para consulta/atualização)
                sucesso, opcao, metodo = trocar_codigo_gerencial(frame_form, nome_final, memoria)

                if sucesso:
                    salvou = salvar_titulo(frame_form)
                    if salvou:
                        print(Fore.GREEN + f"   ✅ Salvo! → {opcao}")
                        relatorio.append({"cod": cod, "cliente": nome_final,
                                          "status": "OK", "opcao": opcao})
                    else:
                        print(Fore.YELLOW + f"   ⚠️ Troca feita mas falha ao salvar.")
                        relatorio.append({"cod": cod, "cliente": nome_final,
                                          "status": "ERRO - NAO SALVOU", "opcao": opcao})
                else:
                    status = "PULADO" if "PULADO" in metodo else f"ERRO - {metodo}"
                    print(Fore.YELLOW + f"   ⏭️ {status}")
                    relatorio.append({"cod": cod, "cliente": nome_final,
                                      "status": status, "opcao": ""})

                time.sleep(1)

        except KeyboardInterrupt:
            print(Fore.RED + "\n🛑 Interrompido pelo usuário.")
        except Exception as e:
            print(Fore.RED + f"\n❌ Erro crítico: {e}")
        finally:
            print(Fore.BLUE + "\n" + "=" * 65)
            print(Fore.YELLOW + Style.BRIGHT + " 📊 RELATÓRIO FINAL")
            print(Fore.BLUE + "=" * 65)

            ok      = [r for r in relatorio if r["status"] == "OK"]
            erros   = [r for r in relatorio if "ERRO" in r["status"]]
            pulados = [r for r in relatorio if r["status"] == "JA ALTERADO"]

            print(Fore.GREEN  + f"  ✅ Alterados com sucesso : {len(ok)}")
            print(Fore.YELLOW + f"  ⏭️  Já alterados / pulados: {len(pulados)}")
            print(Fore.RED    + f"  ❌ Erros                 : {len(erros)}")

            if erros:
                print(Fore.RED + "\n  Títulos com erro:")
                for r in erros:
                    print(Fore.RED + f"    #{r['cod']} — {r['cliente']} — {r['status']}")

            if ok:
                print(Fore.GREEN + "\n  Títulos alterados:")
                for r in ok:
                    print(Fore.GREEN + f"    #{r['cod']} — {r['cliente']} → {r['opcao']}")

            print(Fore.BLUE + "=" * 65)
            print(Fore.WHITE + f"\n  Processados em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            input(Fore.WHITE + "\nPressione Enter para fechar o browser...")
            browser.close()

if __name__ == "__main__":
    executar_troca_codigos()