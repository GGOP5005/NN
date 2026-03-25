import os
import re
from config import PASTA_RAIZ_DOCUMENTOS
from extrator_pdf import extrair_texto_pdf 

def encontrar_pasta_container(numero_container):
    print(f"🔎 Procurando a pasta do contêiner {numero_container} no Dropbox...")
    for raiz, diretorios, arquivos in os.walk(PASTA_RAIZ_DOCUMENTOS):
        diretorios_upper = [d.upper() for d in diretorios]
        if numero_container.upper() in diretorios_upper:
            caminho_encontrado = os.path.join(raiz, numero_container.upper())
            tem_pdf = any(f.lower().endswith('.pdf') for f in os.listdir(caminho_encontrado))
            if tem_pdf:
                print(f"   📂 Pasta encontrada (com PDFs): {caminho_encontrado}")
                return caminho_encontrado
            else:
                print(f"   ⚠️ Pasta encontrada, mas está VAZIA. Ignorando...")
    return None

def classificar_e_extrair_pdfs(pasta_container):
    documentos_nf = []
    documentos_cte = []
    
    if not pasta_container or not os.path.exists(pasta_container):
        return documentos_nf, documentos_cte
        
    arquivos = [f for f in os.listdir(pasta_container) if f.lower().endswith('.pdf')]
    
    for arquivo in arquivos:
        caminho_completo = os.path.join(pasta_container, arquivo)
        texto_pdf = extrair_texto_pdf(caminho_completo)
        
        # Pular comprovantes de pagamento que causam confusão
        if "COMPROVANTE DE PAGAMENTO" in texto_pdf.upper() or "PAGADOR" in texto_pdf.upper():
            continue
            
        paginas = texto_pdf.split('--- NOVA PAGINA ---')
        for texto_pagina in paginas:
            texto_upper = texto_pagina.upper()
            
            eh_nf = "DANFE" in texto_upper or "DOCUMENTO AUXILIAR DA NOTA FISCAL" in texto_upper or "NF-E" in texto_upper
            eh_cte = "DACTE" in texto_upper or "CONHECIMENTO DE TRANSPORTE" in texto_upper or "CT-E" in texto_upper
            
            if not eh_nf and not eh_cte:
                if re.search(r'CHAVE DE ACESSO\s*[\d\s]{44}', texto_upper):
                    eh_nf = True
            
            numero_nf = None
            numero_cte = None
            
            if eh_nf:
                match_nf = re.search(r'N[O0º°o№]?\\.?\\s*([0-9]{1,3}\\.[0-9]{3}\\.[0-9]{3})', texto_pagina)
                if match_nf: numero_nf = match_nf.group(1).replace('.', '').lstrip('0')
                if not numero_nf:
                    match_nf2 = re.search(r'N[O0º°o№]?\\.?\\s*0*([1-9][0-9]{0,8})\\b', texto_pagina)
                    if match_nf2: numero_nf = match_nf2.group(1)
            
            elif eh_cte:
                match_cte = re.search(r'(?:CT-E|CT[- ]E)?\\s*N[O0º°o№]?\\.?\\s*([0-9]{3}[\\.\\s]?[0-9]{3}[\\.\\s]?[0-9]{3})', texto_pagina)
                if not match_cte:
                    match_cte = re.search(r'([0-9]{3}\\.[0-9]{3}\\.[0-9]{3})', texto_pagina)
                if match_cte: 
                    numero_cte = match_cte.group(1).replace('.', '').replace(' ', '').lstrip('0')

            if eh_nf and numero_nf:
                documentos_nf.append({"caminho": caminho_completo, "numero": numero_nf, "arquivo": arquivo})
                print(f"   📄 [NF] Identificada: {arquivo} | Número: {numero_nf}")
            elif eh_cte and numero_cte:
                documentos_cte.append({"caminho": caminho_completo, "numero": numero_cte, "arquivo": arquivo})
                print(f"   📑 [CT-e] Identificado: {arquivo} | Número: {numero_cte}")

    return documentos_nf, documentos_cte