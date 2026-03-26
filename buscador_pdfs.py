import os
import re
from config import PASTA_RAIZ_DOCUMENTOS
from extrator_pdf import extrair_texto_pdf

try:
    import fitz
    FITZ_OK = True
except ImportError:
    FITZ_OK = False


# ──────────────────────────────────────────────────────────────
# PADRÕES DE DETECÇÃO
# ──────────────────────────────────────────────────────────────

_RE_NF = re.compile(
    r'DANFE|DOCUMENTO\s+AUXILIAR\s+DA\s+NOTA\s+FISCAL|NF-?E\b',
    re.IGNORECASE
)
_RE_CTE = re.compile(
    r'DACTE|DOCUMENTO\s+AUXILIAR\s+DO\s+CONHECIMENTO\s+DE\s+TRANSPORTE|CT-?E\b',
    re.IGNORECASE
)
_RE_COMPROVANTE = re.compile(
    r'FICHA\s+DE\s+COMPENSA[CÇ][AÃ]O|C[OÓ]DIGO\s+DE\s+BARRAS|EMITA\s+SEUS\s+BOLETOS|BOLETO\s+BANC[AÁ]RIO',
    re.IGNORECASE
)
_RE_NUM_NF = re.compile(
    r'N[Oº°o]?\.?\s*(\d{1,3}[.\s]?\d{3}[.\s]?\d{3})'
    r'|N[Oº°o]?\.?\s*0*([1-9]\d{0,8})\b',
    re.IGNORECASE
)
_RE_NUM_CTE = re.compile(
    r'(?:CT-?E|C\.T\.-?E\.?)\s*N[Oº°]?\.?\s*(\d{3}[.\s]?\d{3}[.\s]?\d{3})'
    r'|(\d{3}[.\s]\d{3}[.\s]\d{3})',
    re.IGNORECASE
)
# Chave de acesso NF-e no nome do arquivo: 44 dígitos
_RE_CHAVE_ACESSO_NOME = re.compile(r'^\d{44}\.pdf$', re.IGNORECASE)

# Número de CT-e no nome do arquivo: CTe + chave de 44 dígitos
_RE_CHAVE_CTE_NOME = re.compile(r'^cte\d{44}', re.IGNORECASE)

# Número do CT-e dentro do texto do DACTE (campo NÚMERO)
_RE_NUM_CTE_DACTE = re.compile(
    r'N[Oº°]?\s*[\.:]\s*0*([1-9]\d{2,8})\b'   # "Nº. 000.043.433"
    r'|NÚMERO\s*[\n\r]*\s*0*([1-9]\d{2,8})\b'  # campo NÚMERO do DACTE
    r'|^\s*0*([1-9]\d{2,8})\s*$',              # número sozinho numa linha
    re.IGNORECASE | re.MULTILINE
)


def _num_nf(texto):
    m = _RE_NUM_NF.search(texto)
    if m:
        n = (m.group(1) or m.group(2) or '').replace('.', '').replace(' ', '').lstrip('0')
        return n if n else ''
    return ''


def _num_cte(texto):
    m = _RE_NUM_CTE.search(texto)
    if m:
        n = (m.group(1) or m.group(2) or '').replace('.', '').replace(' ', '').lstrip('0')
        return n if n else ''
    return ''


def _ler_paginas(caminho):
    """
    Retorna lista de textos, um por página.
    Usa fitz para separar páginas + extrair_texto_pdf por página para OCR.
    """
    if not FITZ_OK:
        # Sem fitz: lê tudo de uma vez (extrair_texto_pdf já faz OCR internamente)
        return [extrair_texto_pdf(caminho)]

    try:
        doc = fitz.open(caminho)
        n_paginas = len(doc)
        doc.close()
    except Exception as e:
        print(f"   ⚠️ fitz falhou em {os.path.basename(caminho)}: {e}")
        return [extrair_texto_pdf(caminho)]

    if n_paginas == 1:
        # PDF de 1 página: lê direto
        return [extrair_texto_pdf(caminho)]

    # PDF multi-página: extrai cada página em arquivo temporário
    # para aproveitar o OCR do extrair_texto_pdf por página
    import tempfile
    paginas = []
    try:
        doc = fitz.open(caminho)
        for i, pag in enumerate(doc):
            t = pag.get_text("text").strip()
            if len(t) >= 150:
                # Página digital — texto nativo é suficiente
                paginas.append(t)
            else:
                # Página escaneada — exporta como PDF de 1 página e usa OCR
                try:
                    doc_pag = fitz.open()
                    doc_pag.insert_pdf(doc, from_page=i, to_page=i)
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp_path = tmp.name
                    doc_pag.save(tmp_path)
                    doc_pag.close()
                    t = extrair_texto_pdf(tmp_path)
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"   ⚠️ OCR pág.{i+1} de {os.path.basename(caminho)}: {e}")
                paginas.append(t)
        doc.close()
    except Exception as e:
        print(f"   ⚠️ Erro ao paginar {os.path.basename(caminho)}: {e}")
        return [extrair_texto_pdf(caminho)]

    return paginas


# ──────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO POR NOME DE ARQUIVO
# ──────────────────────────────────────────────────────────────

def _dica_pelo_nome(nome_arquivo):
    """
    Retorna 'cte', 'nf' ou None com base no nome do arquivo.
    Cobre:
      - CTe<chave44>.pdf / CTe...  → CT-e
      - <chave44>.pdf              → NF (chave de acesso da NF-e, 44 dígitos)
      - DANFE... / ...-nfe.pdf     → NF
    """
    nome = nome_arquivo.upper()
    # Remove extensão e separadores para testar chave pura
    base = re.sub(r'\.PDF$', '', nome)
    base_limpo = re.sub(r'[\s\-_\(\)]+', '', base)

    # CT-e: nome começa com CTe/CTE/CT- OU começa com CTe + chave de 44 dígitos
    if (re.match(r'^CTE?\d', nome, re.IGNORECASE) or
            re.match(r'^CT[-_\s]', nome, re.IGNORECASE) or
            nome.startswith('CTE') or
            'DACTE' in nome):
        return 'cte'

    # NF: chave de acesso de 44 dígitos no nome (com ou sem separadores)
    if (re.match(r'^\d{44}$', base_limpo) or
            'DANFE' in nome or
            nome.endswith('-NFE.PDF') or
            nome.endswith('_NFE.PDF')):
        return 'nf'

    return None


def _buscar_referencias_planilha(numero_container):
    """
    Consulta o cache da planilha (já carregado pelo sheets_api)
    para obter CT-es e NFs já conhecidos para este container.
    Retorna (set_ctes, set_nfs) — usados para confirmar classificação
    quando nome e conteúdo não são conclusivos.
    """
    ctes_conhecidos = set()
    nfs_conhecidas  = set()
    try:
        from sheets_api import CACHE_PLANILHA
        cont_limpo = re.sub(r'[^A-Z0-9]', '', numero_container.upper())
        for _, conteudo in CACHE_PLANILHA.get('dados', {}).items():
            for item in conteudo.get('linhas', []):
                item_cont = re.sub(r'[^A-Z0-9]', '', item.get('container_limpo', '').upper())
                if cont_limpo and cont_limpo == item_cont:
                    for campo in ('cte_armador', 'cte_nosso'):
                        for cte in item.get(campo, '').split(','):
                            c = re.sub(r'[^0-9]', '', cte).lstrip('0')
                            if c: ctes_conhecidos.add(c)
                    for nf in item.get('nf', '').split(','):
                        n = re.sub(r'[^0-9]', '', nf).lstrip('0')
                        if n: nfs_conhecidas.add(n)
    except Exception:
        pass
    return ctes_conhecidos, nfs_conhecidas


# ──────────────────────────────────────────────────────────────
# FUNÇÕES PRINCIPAIS
# ──────────────────────────────────────────────────────────────

def encontrar_pasta_container(numero_container):
    """Procura recursivamente a pasta do contêiner no Dropbox."""
    print(f"🔎 Procurando pasta do contêiner {numero_container}...")
    numero_upper = numero_container.upper().strip()
    for raiz, diretorios, _ in os.walk(PASTA_RAIZ_DOCUMENTOS):
        for d in diretorios:
            if d.upper() == numero_upper:
                caminho = os.path.join(raiz, d)
                tem_pdf = any(f.lower().endswith('.pdf') for f in os.listdir(caminho))
                if tem_pdf:
                    print(f"   📂 Encontrada (com PDFs): {caminho}")
                    return caminho
                else:
                    print(f"   ⚠️ Pasta encontrada mas vazia: {caminho}")
    return None


def classificar_e_extrair_pdfs(pasta_container):
    """
    Classifica PDFs em NFs e CT-es pelo CONTEÚDO de cada página.
    O nome do arquivo é ignorado completamente.
    
    Camadas:
      1. Palavras-chave no conteúdo (DACTE, DANFE, etc.) página a página
      2. Validação cruzada com cache da planilha (último recurso)
    """
    documentos_nf  = []
    documentos_cte = []

    if not pasta_container or not os.path.exists(pasta_container):
        return documentos_nf, documentos_cte

    numero_container = os.path.basename(pasta_container)
    ctes_planilha, nfs_planilha = _buscar_referencias_planilha(numero_container)
    if ctes_planilha or nfs_planilha:
        print(f"   📋 Planilha: CT-es={ctes_planilha or '∅'} | NFs={nfs_planilha or '∅'}")

    arquivos = sorted(f for f in os.listdir(pasta_container) if f.lower().endswith('.pdf'))

    for arquivo in arquivos:
        caminho = os.path.join(pasta_container, arquivo)

        try:
            paginas = _ler_paginas(caminho)
        except Exception as e:
            print(f"   ⚠️ Erro ao ler {arquivo}: {e}")
            continue

        if not paginas or not any(p.strip() for p in paginas):
            print(f"   ⚠️ PDF sem texto: {arquivo}")
            continue

        encontrou_nf     = False
        encontrou_cte    = False
        numero_nf_final  = ''
        numero_cte_final = ''

        for idx_pag, texto_pag in enumerate(paginas):
            if not texto_pag.strip():
                continue

            # LOG: mostra primeiros 300 chars do texto extraído por página
            preview = ' '.join(texto_pag.split())[:300]
            print(f"   📝 {arquivo} pág.{idx_pag+1}: {preview}{'...' if len(preview)==300 else ''}")

            # Pula páginas de boleto/comprovante (mas continua analisando o resto do arquivo)
            if _RE_COMPROVANTE.search(texto_pag):
                print(f"   ⏭️ {arquivo} pág.{idx_pag+1}: boleto ignorado")
                continue

            # ── Camada 1: decide pelo conteúdo da página ─────────
            eh_cte = bool(_RE_CTE.search(texto_pag))
            eh_nf  = bool(_RE_NF.search(texto_pag))

            # CT-e tem prioridade: todo CT-e cita NFs no corpo do documento
            if eh_cte and eh_nf:
                eh_nf = False

            if eh_cte and not encontrou_cte:
                num = _num_cte(texto_pag)
                if num:
                    encontrou_cte    = True
                    numero_cte_final = num

            if eh_nf and not encontrou_nf:
                num = _num_nf(texto_pag)
                if num:
                    encontrou_nf    = True
                    numero_nf_final = num

        # ── Camada 2: validação cruzada com planilha ─────────────
        if not encontrou_cte and not encontrou_nf:
            texto_total  = ' '.join(paginas)
            num_qualquer = _num_cte(texto_total) or _num_nf(texto_total)
            if num_qualquer:
                if num_qualquer in ctes_planilha:
                    encontrou_cte    = True
                    numero_cte_final = num_qualquer
                    print(f"   🔗 {arquivo}: CT-e confirmado pela planilha (Nº {num_qualquer})")
                elif num_qualquer in nfs_planilha:
                    encontrou_nf    = True
                    numero_nf_final = num_qualquer
                    print(f"   🔗 {arquivo}: NF confirmada pela planilha (Nº {num_qualquer})")

        # ── Camada 3: Gemini IA como último recurso ───────────────
        if not encontrou_cte and not encontrou_nf:
            try:
                from extrator_ia import extrair_com_ia
                texto_total = ' '.join(p for p in paginas if p.strip())
                print(f"   🤖 {arquivo}: tentando extração via Gemini...")
                resultado = extrair_com_ia(texto_total)
                if resultado:
                    itens = resultado if isinstance(resultado, list) else [resultado]
                    for item in itens:
                        cte_arm = str(item.get('CT-E ARMADOR', '') or '').strip().lstrip('0')
                        nf_num  = str(item.get('NOTAS FISCAIS', '') or '').strip().lstrip('0')
                        if cte_arm and not encontrou_cte:
                            encontrou_cte    = True
                            numero_cte_final = cte_arm
                            print(f"   🤖 Gemini identificou CT-e Nº {cte_arm}")
                        if nf_num and not encontrou_nf:
                            encontrou_nf    = True
                            numero_nf_final = nf_num.split(',')[0].strip()
                            print(f"   🤖 Gemini identificou NF Nº {numero_nf_final}")
            except Exception as e:
                print(f"   ⚠️ Gemini falhou em {arquivo}: {e}")



        # ── Registra resultados do arquivo ────────────────────
        if encontrou_cte and numero_cte_final:
            if not any(d["numero"] == numero_cte_final for d in documentos_cte):
                documentos_cte.append({"caminho": caminho, "numero": numero_cte_final, "arquivo": arquivo})
                print(f"   📑 [CT-e] {arquivo} | Nº {numero_cte_final}")

        if encontrou_nf and numero_nf_final:
            if not any(d["numero"] == numero_nf_final for d in documentos_nf):
                documentos_nf.append({"caminho": caminho, "numero": numero_nf_final, "arquivo": arquivo})
                print(f"   📄 [NF] {arquivo} | Nº {numero_nf_final}")

        if not encontrou_nf and not encontrou_cte:
            print(f"   ⚠️ {arquivo}: não classificado como NF nem CT-e")

    if not documentos_nf and not documentos_cte:
        print(f"   ⚠️ Nenhum NF ou CT-e identificado em {pasta_container}")

    return documentos_nf, documentos_cte