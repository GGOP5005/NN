import xml.etree.ElementTree as ET
import re

NS_NFE = "http://www.portalfiscal.inf.br/nfe"
NS_CTE = "http://www.portalfiscal.inf.br/cte"
CNPJ_NORTE_NORDESTE = "46099394000188"

def _remover_ns(tag):
    return re.sub(r'\{[^}]+\}', '', tag)

def _texto(root, *tags):
    for tag in tags:
        element = root.find(f".//{{*}}{tag}")
        if element is not None and element.text:
            return element.text.strip()
    return ""

def _detectar_tipo_pela_chave(root):
    chave = _texto(root, "chNFe", "chCTe", "chMDFe")
    if chave and len(chave) >= 22:
        return chave[20:22], chave
    return None, None

def extrair_texto_xml(path):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        
        tipo_doc, chave = _detectar_tipo_pela_chave(root)
        if not tipo_doc:
            return ""

        dados = {}
        if tipo_doc == "55":
            dados["TIPO"] = "NF-E"
            dados["NOTA FISCAL"] = _texto(root, "nNF")
            dados["VALOR DA NF"] = _texto(root, "vNF", "vProd")
            dados["PESO DA MERCADORIA KG"] = _texto(root, "pesoB", "pesoL", "qVol")
            
            dest = root.find(".//{*}dest")
            if dest is not None:
                nome_dest = _texto(dest, "xNome")
                if nome_dest: dados["CLIENTES"] = nome_dest
                mun_dest = _texto(dest, "xMun")
                uf_dest = _texto(dest, "UF")
                if mun_dest and uf_dest: dados["DESTINO"] = f"{mun_dest}/{uf_dest}"

        elif tipo_doc == "57":
            dados["TIPO"] = "CT-E"
            dados["NOTA FISCAL"] = _texto(root, "nCT")
            dados["VALOR DA NF"] = _texto(root, "vTPrest", "vRec")
            
            rem = root.find(".//{*}rem")
            if rem is not None:
                nome_rem = _texto(rem, "xNome")
                if nome_rem: dados["CLIENTES"] = nome_rem

            dest = root.find(".//{*}dest")
            if dest is not None:
                mun_dest = _texto(dest, "xMun")
                uf_dest = _texto(dest, "UF")
                if mun_dest and uf_dest: dados["DESTINO"] = f"{mun_dest}/{uf_dest}"

            infCarga = root.find(".//{*}infCarga")
            if infCarga is not None:
                for infQ in infCarga.findall(".//{*}infQ"):
                    tpMed = _texto(infQ, "tpMed")
                    if tpMed == "PESO BRUTO" or tpMed == "PESO BASE":
                        dados["PESO DA MERCADORIA KG"] = _texto(infQ, "qCarga")
                        break

            for cont in root.findall(".//{*}cont"):
                nCont = _texto(cont, "nCont")
                if nCont: dados["CONTAINER"] = nCont
                nLacre = _texto(cont, "nLacre")
                if nLacre: dados["LACRE"] = nLacre

        linhas = []
        if dados.get("CLIENTES"):           linhas.append(f"CLIENTES: {dados['CLIENTES']}")
        if dados.get("DESTINO"):            linhas.append(f"DESTINO: {dados['DESTINO']}")
        if dados.get("VALOR DA NF"):        linhas.append(f"VALOR DA NF: {dados['VALOR DA NF']}")
        if dados.get("PESO DA MERCADORIA KG"): linhas.append(f"PESO DA MERCADORIA KG: {dados['PESO DA MERCADORIA KG']}")
        if dados.get("CONTAINER"):          linhas.append(f"CONTAINER: {dados['CONTAINER']}")
        if dados.get("LACRE"):              linhas.append(f"LACRE: {dados['LACRE']}")
        if dados.get("TIPO"):               linhas.append(f"TIPO: {dados['TIPO']}")

        texto_otimizado = "\n".join(linhas)
        return texto_otimizado

    except Exception as e:
        print(f"   ❌ Erro crítico no extrator_xml: {e}")
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except: return ""