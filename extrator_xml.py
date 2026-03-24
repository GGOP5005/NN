"""
extrator_xml.py — Extrator Inteligente de NF-e e CT-e (XML Fiscal Brasileiro)
==============================================================================
Fluxo:
  1. Detecta o tipo do documento pela chave de acesso (posição 20-22):
       55 = NF-e (Nota Fiscal Eletrônica)
       57 = CT-e (Conhecimento de Transporte Eletrônico)
  2. Extrai os campos diretamente dos nodes XML sem depender da IA.
  3. Se algum campo crítico ficar vazio, faz um fallback enviando o
     texto limpo para o Gemini completar o que faltou.
  4. Retorna um dict no mesmo formato do extrator_ia.py para que o
     processor.py não precise de nenhuma alteração.
"""

import xml.etree.ElementTree as ET
import re

# Namespace padrão dos documentos fiscais brasileiros
NS_NFE = "http://www.portalfiscal.inf.br/nfe"
NS_CTE = "http://www.portalfiscal.inf.br/cte"

CNPJ_NORTE_NORDESTE = "46099394000188"

# =============================================================
# UTILITÁRIOS
# =============================================================

def _remover_ns(tag):
    """Remove o namespace de uma tag XML. Ex: {http://...}emit → emit"""
    return re.sub(r'\{[^}]+\}', '', tag)

def _texto(root, *caminhos, ns=None):
    """
    Tenta encontrar o texto de um elemento testando múltiplos caminhos.
    Retorna a primeira string não vazia encontrada, ou "".
    """
    for caminho in caminhos:
        try:
            if ns:
                el = root.find(caminho, ns)
            else:
                el = root.find(caminho)
            if el is not None and el.text and el.text.strip():
                return el.text.strip()
        except Exception:
            continue
    return ""

def _parse_valor(val_str):
    """Converte string numérica para float BR (trata ponto como decimal)."""
    if not val_str:
        return 0.0
    limpo = re.sub(r'[^\d.]', '', str(val_str))
    try:
        return float(limpo)
    except Exception:
        return 0.0

def _formatar_valor(val_float):
    """Formata float para R$ 1.234,56"""
    return f"R$ {val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _formatar_peso(peso_float):
    """Formata float para 1.234"""
    return f"{peso_float:,.3f}".replace(",", ".")

def _limpar_nf(nf_str):
    """Remove zeros à esquerda de números de NF."""
    if not nf_str:
        return ""
    return str(nf_str).lstrip("0")

def _so_digitos(texto):
    """Remove tudo que não for dígito."""
    return re.sub(r'\D', '', str(texto))

def _detectar_tipo_pela_chave(root):
    """
    Detecta o tipo do documento (NF-e ou CT-e) pela chave de acesso.
    Posição 20-22 da chave (base 0): 55 = NF-e, 57 = CT-e
    Retorna: "NFE", "CTE" ou None
    """
    # Procura a chave de acesso em qualquer lugar do XML
    texto_xml = ET.tostring(root, encoding='unicode')
    chaves = re.findall(r'\d{44}', texto_xml)
    for chave in chaves:
        modelo = chave[20:22]
        if modelo == "55":
            return "NFE", chave
        elif modelo == "57":
            return "CTE", chave
    return None, None

def _encontrar_root_e_ns(caminho_arquivo):
    """Parse do XML e detecção de namespace."""
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        tag_raiz = _remover_ns(root.tag)

        # Detecta namespace da raiz
        ns_match = re.match(r'\{([^}]+)\}', root.tag)
        ns_uri = ns_match.group(1) if ns_match else None

        return root, tag_raiz, ns_uri
    except Exception as e:
        print(f"   ❌ Erro ao fazer parse do XML: {e}")
        return None, None, None

# =============================================================
# EXTRATOR DE NF-e
# =============================================================

def _extrair_nfe(root, ns_uri, chave_acesso):
    """
    Extrai campos de uma NF-e diretamente dos nodes XML.
    Suporta NF-e com e sem namespace.
    """
    dados = {
        "CLIENTES": "", "DESTINO": "", "BOOKING": "",
        "NAVIO/VIAGEM ARMADOR": "", "VALOR DA NF": "",
        "PESO DA MERCADORIA KG": "", "NOTAS FISCAIS": "",
        "CT-E ARMADOR": "", "CTE-E": "",
        "CONTAINER": "", "TIPO": "", "LACRE": ""
    }

    ns = {ns_uri: ns_uri} if ns_uri else {}
    pref = f"{{{ns_uri}}}" if ns_uri else ""

    def t(*caminhos):
        """Atalho para _texto com prefixo de namespace automático."""
        caminhos_com_ns = []
        for c in caminhos:
            # Adiciona prefixo a cada segmento do caminho
            partes = c.split("/")
            caminho_ns = "/".join(f"{pref}{p}" if p and not p.startswith("{") else p for p in partes)
            caminhos_com_ns.append(caminho_ns)
        return _texto(root, *caminhos_com_ns)

    # ---- Número da NF ----
    num_nf = t("NFe/infNFe/ide/nNF", "infNFe/ide/nNF", ".//nNF")
    dados["NOTAS FISCAIS"] = _limpar_nf(num_nf)

    # ---- Emitente (Remetente) ----
    emit_nome = t("NFe/infNFe/emit/xNome", "infNFe/emit/xNome", ".//emit/xNome")
    emit_nome = re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|IND|COM|INDUSTRIA|COMERCIO)\b', '', emit_nome, flags=re.IGNORECASE).strip()

    # ---- Destinatário ----
    dest_nome = t("NFe/infNFe/dest/xNome", "infNFe/dest/xNome", ".//dest/xNome")
    dest_nome = re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|IND|COM|INDUSTRIA|COMERCIO)\b', '', dest_nome, flags=re.IGNORECASE).strip()

    if emit_nome and dest_nome:
        dados["CLIENTES"] = f"{emit_nome.upper().strip()} - {dest_nome.upper().strip()}"
    elif dest_nome:
        dados["CLIENTES"] = dest_nome.upper().strip()
    elif emit_nome:
        dados["CLIENTES"] = emit_nome.upper().strip()

    # ---- Destino (Cidade-UF do destinatário) ----
    dest_mun = t("NFe/infNFe/dest/enderDest/xMun", "infNFe/dest/enderDest/xMun", ".//dest/enderDest/xMun")
    dest_uf = t("NFe/infNFe/dest/enderDest/UF", "infNFe/dest/enderDest/UF", ".//dest/enderDest/UF")
    if dest_mun and dest_uf:
        dados["DESTINO"] = f"{dest_mun.upper()}-{dest_uf.upper()}"
    elif dest_mun:
        dados["DESTINO"] = dest_mun.upper()

    # ---- Valor Total da NF ----
    valor_total = t(
        "NFe/infNFe/total/ICMSTot/vNF", "infNFe/total/ICMSTot/vNF",
        ".//total/ICMSTot/vNF", ".//vNF"
    )
    if valor_total:
        val_float = _parse_valor(valor_total)
        dados["VALOR DA NF"] = _formatar_valor(val_float)

    # ---- Peso Bruto ----
    # Soma o peso bruto de todos os volumes
    peso_total = 0.0
    pref_transp = f"{pref}transp" if pref else "transp"
    pref_vol = f"{pref}vol" if pref else "vol"
    pref_pesoB = f"{pref}pesoB" if pref else "pesoB"

    for vol in root.iter(f"{pref}vol"):
        pb = _texto(vol, f"{pref}pesoB", "pesoB")
        if pb:
            peso_total += _parse_valor(pb)

    if peso_total > 0:
        dados["PESO DA MERCADORIA KG"] = _formatar_peso(peso_total)
    else:
        # Fallback: tenta peso líquido ou peso no elemento raiz
        peso_liq = t(".//pesoL")
        if peso_liq:
            dados["PESO DA MERCADORIA KG"] = _formatar_peso(_parse_valor(peso_liq))

    # ---- Contêiner e Lacre (nas Observações / Dados Adicionais) ----
    inf_adic = t(
        "NFe/infNFe/infAdic/infCpl", "infNFe/infAdic/infCpl",
        ".//infAdic/infCpl", ".//infCpl"
    )
    obs_cont = t(".//xCampo", ".//xTexto")

    texto_busca_container = f"{inf_adic} {obs_cont}".upper()

    # Padrão de contêiner: 4 letras + 7 dígitos
    cont_match = re.search(r'\b([A-Z]{4}\s*\d{7})\b', texto_busca_container)
    if cont_match:
        dados["CONTAINER"] = re.sub(r'\s+', '', cont_match.group(1))

    # Lacre
    lacre_match = re.search(r'LACRE[:\s#Nº°]*([A-Z0-9\-]{4,20})', texto_busca_container)
    if lacre_match:
        dados["LACRE"] = lacre_match.group(1).strip()

    # Se não achou no infCpl, vasculha todos os campos de observação
    if not dados["CONTAINER"]:
        texto_xml_full = ET.tostring(root, encoding='unicode').upper()
        cont_match2 = re.search(r'\b([A-Z]{4}\d{7})\b', texto_xml_full)
        if cont_match2:
            dados["CONTAINER"] = cont_match2.group(1)

    # ---- Booking / Navio ----
    # Às vezes vem nas observações também
    if inf_adic:
        bk_match = re.search(r'BOOKING[:\s#Nº°]*([A-Z0-9\-]{5,20})', inf_adic.upper())
        if bk_match:
            dados["BOOKING"] = bk_match.group(1).strip()

        navio_match = re.search(r'NAVIO[:\s]*([A-Z0-9\s/]{5,40}?)(?=\s*VIAGEM|\s*BL|\s*BOOKING|\s*LACRE|$)', inf_adic.upper())
        if navio_match:
            dados["NAVIO/VIAGEM ARMADOR"] = navio_match.group(1).strip()

    print(f"   📦 NF-e extraída diretamente: NF={dados['NOTAS FISCAIS']} | Contêiner={dados['CONTAINER']} | Valor={dados['VALOR DA NF']}")
    return dados


# =============================================================
# EXTRATOR DE CT-e
# =============================================================

def _extrair_cte(root, ns_uri, chave_acesso):
    """
    Extrai campos de um CT-e diretamente dos nodes XML.
    Determina automaticamente se é nosso CT-e (CTE-E) ou de terceiros (CT-E ARMADOR).
    """
    dados = {
        "CLIENTES": "", "DESTINO": "", "BOOKING": "",
        "NAVIO/VIAGEM ARMADOR": "", "VALOR DA NF": "",
        "PESO DA MERCADORIA KG": "", "NOTAS FISCAIS": "",
        "CT-E ARMADOR": "", "CTE-E": "",
        "CONTAINER": "", "TIPO": "", "LACRE": ""
    }

    pref = f"{{{ns_uri}}}" if ns_uri else ""

    def t(*caminhos):
        caminhos_com_ns = []
        for c in caminhos:
            partes = c.split("/")
            caminho_ns = "/".join(f"{pref}{p}" if p and not p.startswith("{") else p for p in partes)
            caminhos_com_ns.append(caminho_ns)
        return _texto(root, *caminhos_com_ns)

    # ---- Número do CT-e ----
    num_cte = t("CTeOS/infCte/ide/nCT", "CTe/infCte/ide/nCT", "infCte/ide/nCT", ".//nCT")
    num_cte_limpo = _limpar_nf(num_cte)

    # ---- CNPJ do Emitente ---- (decide se é nosso CT-e ou de terceiros)
    cnpj_emit = _so_digitos(t(
        "CTe/infCte/emit/CNPJ", "CTeOS/infCte/emit/CNPJ",
        "infCte/emit/CNPJ", ".//emit/CNPJ"
    ))

    if cnpj_emit == CNPJ_NORTE_NORDESTE:
        dados["CTE-E"] = num_cte_limpo
        print(f"   📑 CT-e identificado como NOSSO (Norte Nordeste): {num_cte_limpo}")
    else:
        dados["CT-E ARMADOR"] = num_cte_limpo
        print(f"   📑 CT-e identificado como TERCEIRO/ARMADOR: {num_cte_limpo}")

    # ---- Remetente e Destinatário ----
    rem_nome = t(
        "CTe/infCte/rem/xNome", "CTeOS/infCte/rem/xNome",
        "infCte/rem/xNome", ".//rem/xNome"
    )
    dest_nome = t(
        "CTe/infCte/dest/xNome", "CTeOS/infCte/dest/xNome",
        "infCte/dest/xNome", ".//dest/xNome"
    )

    rem_nome = re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|IND|COM)\b', '', rem_nome, flags=re.IGNORECASE).strip().upper()
    dest_nome = re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|IND|COM)\b', '', dest_nome, flags=re.IGNORECASE).strip().upper()

    if rem_nome and dest_nome:
        dados["CLIENTES"] = f"{rem_nome} - {dest_nome}"
    elif dest_nome:
        dados["CLIENTES"] = dest_nome
    elif rem_nome:
        dados["CLIENTES"] = rem_nome

    # ---- Destino ----
    dest_mun = t(
        "CTe/infCte/ide/xMunFim", "CTeOS/infCte/ide/xMunFim",
        "infCte/ide/xMunFim", ".//xMunFim"
    )
    dest_uf = t(
        "CTe/infCte/ide/UFFim", "CTeOS/infCte/ide/UFFim",
        "infCte/ide/UFFim", ".//UFFim"
    )
    if dest_mun and dest_uf:
        dados["DESTINO"] = f"{dest_mun.upper()}-{dest_uf.upper()}"
    elif dest_mun:
        dados["DESTINO"] = dest_mun.upper()

    # ---- Valor Total do CT-e ----
    valor_total = t(
        "CTe/infCte/vPrest/vTPrest", "CTeOS/infCte/vPrest/vTPrest",
        "infCte/vPrest/vTPrest", ".//vTPrest"
    )
    if valor_total:
        val_float = _parse_valor(valor_total)
        dados["VALOR DA NF"] = _formatar_valor(val_float)

    # ---- Peso ----
    peso_bruto = t(
        "CTe/infCte/infCTeNorm/infCarga/vCarga", 
        "infCte/infCTeNorm/infCarga/vCarga",
        ".//vCarga"
    )
    # O campo de peso no CT-e fica em qtCarga com cUnid = "KG"
    for qtcarga in root.iter(f"{pref}qtCarga"):
        c_unid_el = qtcarga.find(f"{pref}cUnid") or qtcarga.find("cUnid")
        v_qtd_el = qtcarga.find(f"{pref}vQtde") or qtcarga.find("vQtde")
        if c_unid_el is not None and v_qtd_el is not None:
            if "KG" in (c_unid_el.text or "").upper():
                peso_kg = _parse_valor(v_qtd_el.text)
                if peso_kg > 0:
                    dados["PESO DA MERCADORIA KG"] = _formatar_peso(peso_kg)
                    break

    # ---- Notas Fiscais referenciadas no CT-e ----
    nfs_ref = []
    # CT-e normal: infDoc/infNFe/chave
    for inf_nfe in root.iter(f"{pref}infNFe"):
        chave_el = inf_nfe.find(f"{pref}chave") or inf_nfe.find("chave")
        if chave_el is not None and chave_el.text:
            chave_nf = chave_el.text.strip()
            if len(chave_nf) == 44 and chave_nf[20:22] == "55":
                num = _limpar_nf(chave_nf[25:34])
                if num and num not in nfs_ref:
                    nfs_ref.append(num)

    # CT-e OS / outros: infDoc/infOutros/nDoc
    for inf_outros in root.iter(f"{pref}infOutros"):
        n_doc_el = inf_outros.find(f"{pref}nDoc") or inf_outros.find("nDoc")
        if n_doc_el is not None and n_doc_el.text:
            num = _limpar_nf(n_doc_el.text.strip())
            if num and num not in nfs_ref:
                nfs_ref.append(num)

    if nfs_ref:
        dados["NOTAS FISCAIS"] = ", ".join(nfs_ref)

    # ---- Contêiner e Lacre ----
    # Nos CT-es de cabotagem geralmente ficam em infModal/aquav/balsa ou infDoc
    texto_xml_full = ET.tostring(root, encoding='unicode').upper()

    cont_match = re.search(r'\b([A-Z]{4}\d{7})\b', texto_xml_full)
    if cont_match:
        dados["CONTAINER"] = cont_match.group(1)

    lacre_match = re.search(r'LACRE[:\s#Nº°<>/A-Z]*?>?([A-Z0-9\-]{4,20})<', texto_xml_full)
    if not lacre_match:
        lacre_match = re.search(r'LACRE[:\s#Nº°]*([A-Z0-9\-]{4,20})', texto_xml_full)
    if lacre_match:
        dados["LACRE"] = lacre_match.group(1).strip()

    # ---- Booking e Navio (CT-e marítimo) ----
    # Aquaviário: infModal/aquav
    booking = t(
        "CTe/infCte/infCTeNorm/infModal/aquav/nBooking",
        "infCte/infCTeNorm/infModal/aquav/nBooking",
        ".//nBooking"
    )
    if booking:
        dados["BOOKING"] = booking.upper()

    navio = t(
        "CTe/infCte/infCTeNorm/infModal/aquav/xNavio",
        "infCte/infCTeNorm/infModal/aquav/xNavio",
        ".//xNavio"
    )
    viagem = t(
        "CTe/infCte/infCTeNorm/infModal/aquav/nViag",
        "infCte/infCTeNorm/infModal/aquav/nViag",
        ".//nViag"
    )
    if navio and viagem:
        dados["NAVIO/VIAGEM ARMADOR"] = f"{navio.upper()}/{viagem.upper()}"
    elif navio:
        dados["NAVIO/VIAGEM ARMADOR"] = navio.upper()

    print(f"   📑 CT-e extraído diretamente: Nº={num_cte_limpo} | Contêiner={dados['CONTAINER']} | NFs={dados['NOTAS FISCAIS']}")
    return dados


# =============================================================
# FALLBACK: complementa campos vazios usando a IA
# =============================================================

def _complementar_com_ia(dados, texto_xml):
    """
    Se campos críticos ficaram vazios após a extração direta,
    envia o XML (convertido em texto limpo) para o Gemini completar.
    Só é chamado se realmente necessário — evita gastos desnecessários.
    """
    campos_criticos_vazios = not dados.get("CLIENTES") or not dados.get("CONTAINER")

    if not campos_criticos_vazios:
        return dados  # Extração direta foi suficiente, não precisa da IA

    print("   🤖 Campos críticos vazios. Acionando IA para complementar...")
    try:
        from extrator_ia import extrair_com_ia
        # Limpa o XML para o texto ficar legível para a IA
        texto_limpo = re.sub(r'<[^>]+>', ' ', texto_xml)
        texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
        dados_ia = extrair_com_ia(texto_limpo)

        if dados_ia:
            # Preenche apenas os campos que a extração direta deixou vazios
            for campo, valor in dados_ia.items():
                if not dados.get(campo) and valor:
                    dados[campo] = valor
                    print(f"      ✅ Campo complementado pela IA: {campo} = {valor}")
    except Exception as e:
        print(f"   ⚠️ Fallback IA falhou: {e}")

    return dados


# =============================================================
# FUNÇÃO PRINCIPAL (chamada pelo processor.py)
# =============================================================

def extrair_texto_xml(caminho_arquivo):
    """
    Extrai o texto estruturado de um XML fiscal (NF-e ou CT-e).
    Retorna uma string de texto limpo para ser enviada à IA pelo processor.py,
    OU processa diretamente e retorna um dict já pronto.

    ATENÇÃO: Como o processor.py espera uma STRING (texto_extraido),
    esta função retorna uma representação textual otimizada do XML
    que a IA consegue ler com muito mais precisão do que o XML bruto.
    """
    try:
        root, tag_raiz, ns_uri = _encontrar_root_e_ns(caminho_arquivo)
        if root is None:
            return ""

        tipo_doc, chave_acesso = _detectar_tipo_pela_chave(root)
        print(f"   🔍 XML detectado como: {tipo_doc or 'DESCONHECIDO'} | Chave: {chave_acesso[:10] if chave_acesso else 'N/A'}...")

        if tipo_doc == "NFE":
            dados = _extrair_nfe(root, ns_uri, chave_acesso)
        elif tipo_doc == "CTE":
            dados = _extrair_cte(root, ns_uri, chave_acesso)
        else:
            # Tipo desconhecido: converte para texto e deixa a IA decidir
            print("   ⚠️ Tipo de XML desconhecido. Convertendo para texto...")
            texto_xml = ET.tostring(root, encoding='unicode')
            texto_limpo = re.sub(r'<[^>]+>', ' ', texto_xml)
            return re.sub(r'\s+', ' ', texto_limpo).strip()

        # Lê o XML como texto para o fallback da IA se necessário
        texto_xml_str = ET.tostring(root, encoding='unicode')
        dados = _complementar_com_ia(dados, texto_xml_str)

        # Converte o dict extraído de volta para um texto formatado
        # que o processor.py vai passar para extrair_com_ia()
        # Mas como já temos os dados limpos, montamos um texto estruturado
        # que garante que a IA vai interpretar corretamente
        linhas = []
        linhas.append(f"TIPO DOCUMENTO: {'NOTA FISCAL ELETRONICA' if tipo_doc == 'NFE' else 'CONHECIMENTO DE TRANSPORTE ELETRONICO'}")
        if dados.get("NOTAS FISCAIS"):      linhas.append(f"NOTAS FISCAIS: {dados['NOTAS FISCAIS']}")
        if dados.get("CT-E ARMADOR"):       linhas.append(f"CT-E ARMADOR: {dados['CT-E ARMADOR']}")
        if dados.get("CTE-E"):              linhas.append(f"CTE-E: {dados['CTE-E']}")
        if dados.get("CLIENTES"):           linhas.append(f"CLIENTES: {dados['CLIENTES']}")
        if dados.get("DESTINO"):            linhas.append(f"DESTINO: {dados['DESTINO']}")
        if dados.get("VALOR DA NF"):        linhas.append(f"VALOR DA NF: {dados['VALOR DA NF']}")
        if dados.get("PESO DA MERCADORIA KG"): linhas.append(f"PESO DA MERCADORIA KG: {dados['PESO DA MERCADORIA KG']}")
        if dados.get("CONTAINER"):          linhas.append(f"CONTAINER: {dados['CONTAINER']}")
        if dados.get("LACRE"):              linhas.append(f"LACRE: {dados['LACRE']}")
        if dados.get("BOOKING"):            linhas.append(f"BOOKING: {dados['BOOKING']}")
        if dados.get("NAVIO/VIAGEM ARMADOR"): linhas.append(f"NAVIO/VIAGEM ARMADOR: {dados['NAVIO/VIAGEM ARMADOR']}")
        if dados.get("TIPO"):               linhas.append(f"TIPO: {dados['TIPO']}")

        texto_otimizado = "\n".join(linhas)
        print(f"   ✅ XML processado com sucesso. Texto otimizado gerado ({len(linhas)} campos).")
        return texto_otimizado

    except Exception as e:
        print(f"   ❌ Erro crítico no extrator_xml: {e}")
        # Fallback absoluto: retorna o XML como texto puro
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()
            texto_limpo = re.sub(r'<[^>]+>', ' ', conteudo)
            return re.sub(r'\s+', ' ', texto_limpo).strip()
        except Exception:
            return ""