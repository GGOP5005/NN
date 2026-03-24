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
        
    for arquivo in os.listdir(pasta_container):
        if arquivo.lower().endswith('.pdf'):
            caminho_completo = os.path.join(pasta_container, arquivo)
            
            try:
                texto_pagina = extrair_texto_pdf(caminho_completo)
                if not texto_pagina: continue
                texto_pagina = texto_pagina.upper()
                
                eh_cte = False
                eh_nf = False
                numero_nf = ""
                numero_cte = ""
                
                # 1. TENTA PELA CHAVE DE ACESSO NO NOME DO FICHEIRO
                chaves_no_nome = re.findall(r'\d{44}', arquivo)
                if chaves_no_nome:
                    chave = chaves_no_nome[0]
                    if chave[20:22] == '57': 
                        eh_cte = True
                        numero_cte = str(int(chave[25:34])) 
                    elif chave[20:22] == '55': 
                        eh_nf = True
                        numero_nf = str(int(chave[25:34]))

                # 2. SE NÃO ACHOU NO NOME, OLHA PARA DENTRO DO PDF (BLINDADO)
                if not eh_cte and not eh_nf:
                    # 2.1 Identifica a natureza do doc pelo Título PRIMEIRO!
                    texto_limpo = texto_pagina.replace(' ', '')
                    if "DACTE" in texto_limpo or "CONHECIMENTODETRANSPORTE" in texto_limpo:
                        eh_cte = True
                    elif "DANFE" in texto_limpo or "DOCUMENTOAUXILIAR" in texto_limpo or "NOTAFISCAL" in texto_limpo:
                        eh_nf = True

                    # 2.2 Extração infalível da Chave de Acesso (Pega exatos 44 digitos, ignorando espaços/pontos)
                    chaves_brutas = re.findall(r'(?<!\d)(?:(?:\d)[\s\.\-]*){44}(?!\d)', texto_pagina)
                    chaves_acesso = [re.sub(r'\D', '', c) for c in chaves_brutas]
                    
                    # 2.3 Atribui o número de acordo com o TIPO IDENTIFICADO (Evita roubo de chaves trocadas)
                    if eh_cte:
                        for chave in chaves_acesso:
                            if chave[20:22] == '57':
                                numero_cte = str(int(chave[25:34]))
                                break
                    elif eh_nf:
                        for chave in chaves_acesso:
                            if chave[20:22] == '55':
                                numero_nf = str(int(chave[25:34]))
                                break
                    else:
                        for chave in chaves_acesso:
                            if chave[20:22] == '57':
                                eh_cte = True
                                numero_cte = str(int(chave[25:34])) 
                                break
                            elif chave[20:22] == '55':
                                eh_nf = True
                                numero_nf = str(int(chave[25:34])) 
                                break

                # 3. FALLBACK DE TEXTO SE A CHAVE DE ACESSO NÃO ESTIVER NÍTIDA
                if eh_nf and not numero_nf:
                    match_nf = re.search(r'(?:N[oOº°№]\s*\.?\s*|N[UÚ]MERO\s*:?\s*|N\.\s*DOCUMENTO\s*|DOCUMENTO\s*)([0-9\.]+)', texto_pagina)
                    if match_nf: numero_nf = match_nf.group(1).replace('.', '').lstrip('0')
                        
                elif eh_cte and not numero_cte:
                    match_cte = re.search(r'(?:CT-E|CT[- ]E)?\s*N[O0º°o№]?\.?\s*([0-9]{3}[\.\s]?[0-9]{3}[\.\s]?[0-9]{3})', texto_pagina)
                    if not match_cte:
                        match_cte = re.search(r'([0-9]{3}\.[0-9]{3}\.[0-9]{3})', texto_pagina)
                    if match_cte: 
                        numero_cte = match_cte.group(1).replace('.', '').replace(' ', '').lstrip('0')

                # --- RESULTADOS ---
                if eh_nf and numero_nf:
                    documentos_nf.append({"caminho": caminho_completo, "numero": numero_nf, "arquivo": arquivo})
                    print(f"   📄 [NF] Identificada: {arquivo} | Número: {numero_nf}")
                elif eh_cte and numero_cte:
                    documentos_cte.append({"caminho": caminho_completo, "numero": numero_cte, "arquivo": arquivo})
                    print(f"   📑 [CT-e] Identificado: {arquivo} | Número: {numero_cte}")
                elif eh_nf:
                    print(f"   ⚠️ [NF] Encontrada: {arquivo}, mas falhou a leitura do número.")
                elif eh_cte:
                    print(f"   ⚠️ [CT-e] Encontrado: {arquivo}, mas falhou a leitura do número.")
                else:
                    pass
                        
            except Exception as e:
                print(f"   ⚠️ Erro ao tentar ler o arquivo {arquivo}: {e}")
                
    return documentos_nf, documentos_cte