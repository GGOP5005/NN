import os
import re
import shutil
import time
import unicodedata
from datetime import datetime
from colorama import init, Fore, Style
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Importações atualizadas
from config import BASE_DIR, PASTA_RAIZ_DOCUMENTOS, ROTEAMENTO_PORTOS
try:
    from config import PASTA_BACKUP_RAIZ
except ImportError:
    PASTA_BACKUP_RAIZ = r"G:\Meu Drive\NORTE NORDESTE"

try:
    from extrator_pdf import extrair_texto_pdf
    EXTRATOR_PDF_OK = True
except ImportError:
    EXTRATOR_PDF_OK = False

init(autoreset=True)

# A raiz do Dropbox agora é puxada diretamente da constante
DROPBOX_ROOT = PASTA_RAIZ_DOCUMENTOS
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MAPA_MESES = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
    5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
    9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
}
MESES_INV = {v: k for k, v in MAPA_MESES.items()}
MESES_INV["MARCO"] = 3

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def padronizar_nome_cliente(nome):
    if not nome: return "CLIENTE_DESCONHECIDO"
    if "-" in nome: nome = nome.split("-")[-1]
    nome = nome.upper().strip()
    nome = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('utf-8')
    nome = nome.replace(".", "").replace(",", "")
    termos_ignorar = [r'\bLTDA\b', r'\bS/?A\b', r'\bEIRELI\b', r'\bME\b', r'\bEPP\b',
                      r'\bINDUSTRIA\b', r'\bIND\b', r'\bCOMERCIO\b', r'\bCOM\b',
                      r'\bDE\b', r'\bE\b', r'\bDO\b', r'\bDA\b']
    for termo in termos_ignorar:
        nome = re.sub(termo, ' ', nome)
    nome = re.sub(r'[\\/*?:"<>|]', "", nome)
    palavras = [p for p in nome.split() if p.strip()]
    if len(palavras) >= 3: return f"{palavras[0]} {palavras[1]} {palavras[2]}"
    elif len(palavras) > 0: return " ".join(palavras)
    else: return "CLIENTE_DESCONHECIDO"

def mover_com_mesclagem(origem, destino):
    if not os.path.exists(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.move(origem, destino)
    else:
        for item in os.listdir(origem):
            s_item = os.path.join(origem, item)
            d_item = os.path.join(destino, item)
            if not os.path.exists(d_item):
                shutil.move(s_item, d_item)
            else:
                b, ext = os.path.splitext(item)
                d_item = os.path.join(destino, f"{b}_{int(time.time())}{ext}")
                shutil.move(s_item, d_item)
        try: shutil.rmtree(origem)
        except: pass

def mover_arquivo_seguro(origem, destino_dir, nome_arquivo):
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, nome_arquivo)
    if os.path.exists(destino):
        base, ext = os.path.splitext(nome_arquivo)
        destino = os.path.join(destino_dir, f"{base}_{int(time.time())}{ext}")
    for _ in range(3):
        try:
            shutil.move(origem, destino)
            return True
        except Exception:
            time.sleep(1)
    return False

def extrair_nfs_do_arquivo(caminho_arquivo):
    """Lê PDFs e XMLs profundamente em busca de NFs e CT-es"""
    nfs = []
    ext = caminho_arquivo.lower().split('.')[-1]
    
    # BATIMENTO CARDÍACO: Avisa que está a ler o interior do ficheiro
    print(Fore.BLACK + Style.BRIGHT + f"      📖 Raio-X profundo: Lendo interior do {ext.upper()} {os.path.basename(caminho_arquivo)[:15]}...")
    
    try:
        if ext == 'pdf' and EXTRATOR_PDF_OK:
            texto = extrair_texto_pdf(caminho_arquivo)
            if texto:
                chaves = re.findall(r'\d{44}', texto)
                for chave in chaves:
                    if chave[20:22] in ["55", "57"]:
                        num = str(int(chave[25:34]))
                        if num and num not in nfs: nfs.append(num)
                if not nfs:
                    matches = re.findall(r'N[ºO°]?\s*\.?\s*0*([1-9]\d{4,8})', texto)
                    for m in matches:
                        if m not in nfs: nfs.append(m)
                            
        elif ext == 'xml':
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                texto = f.read()
                chaves = re.findall(r'\d{44}', texto)
                for chave in chaves:
                    if chave[20:22] in ["55", "57"]:
                        num = str(int(chave[25:34]))
                        if num and num not in nfs: nfs.append(num)
                if not nfs:
                    matches = re.findall(r'<nNF>(\d+)</nNF>', texto) + re.findall(r'<nCT>(\d+)</nCT>', texto)
                    for m in matches:
                        num = m.lstrip("0")
                        if num and num not in nfs: nfs.append(num)
                            
    except Exception as e: 
        print(Fore.RED + f"      ⚠️ Erro ao ler PDF/XML {os.path.basename(caminho_arquivo)}: {e}")
    return nfs

def obter_dados_planilha(spreadsheet_id, porto_nome):
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    mes_atual_num = datetime.now().month
    mes_atual_nome = MAPA_MESES.get(mes_atual_num, "MARÇO")

    ativos_por_container = {}
    container_por_nf = {}

    try:
        print(Fore.WHITE + "   ⏳ Fazendo download da base de dados do Google Sheets...")
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        abas = [s["properties"]["title"].upper() for s in meta.get("sheets", [])]

        aba_alvo = mes_atual_nome if mes_atual_nome in abas else ("MARCO" if "MARCO" in abas else abas[0])
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{aba_alvo}!A:AZ"
        ).execute()
        linhas = res.get("values", [])

        if not linhas: return ativos_por_container, container_por_nf, aba_alvo

        idx_cont = -1
        idx_cliente = -1
        indices_docs = []
        linha_cabecalho = 0

        for num_linha, linha in enumerate(linhas[:10]):
            cabecalho = [str(c).upper().strip() for c in linha]
            for i, col in enumerate(cabecalho):
                if col in ["CLIENTES", "CLIENTE", "DESTINATARIO", "DESTINATÁRIO", "EMPRESA"]: idx_cliente = i
                elif col in ["CONTAINER", "CNTR", "UNIDADE"]: idx_cont = i
                elif col in ["NOTAS FISCAIS", "NF", "NOTA FISCAL", "CT-E ARMADOR", "CTE-E", "CTE", "CT-E"]: indices_docs.append(i)

            if idx_cont != -1 and idx_cliente != -1:
                linha_cabecalho = num_linha
                break

        if idx_cliente == -1 and idx_cont != -1: idx_cliente = 0
        if idx_cont == -1: return ativos_por_container, container_por_nf, aba_alvo

        print(Fore.GREEN + f"   👁️ Planilha Lida! Cliente:[{idx_cliente+1}] Contêiner:[{idx_cont+1}] Docs:[{len(indices_docs)} colunas]")

        for i in range(linha_cabecalho + 1, len(linhas)):
            linha = linhas[i]
            if len(linha) <= idx_cont: continue

            cont = re.sub(r'[^A-Z0-9]', '', str(linha[idx_cont]).upper())
            if not cont or len(cont) < 10: continue

            cliente_bruto = str(linha[idx_cliente]) if len(linha) > idx_cliente else ""
            cliente_limpo = padronizar_nome_cliente(cliente_bruto)

            if cont not in ativos_por_container or ativos_por_container[cont] == "CLIENTE_DESCONHECIDO":
                ativos_por_container[cont] = cliente_limpo

            for idx_doc in indices_docs:
                if len(linha) > idx_doc:
                    doc_str = str(linha[idx_doc]).strip()
                    for doc in re.split(r'[,;/\s|-]', doc_str):
                        doc = doc.strip().lstrip("0")
                        if doc and len(doc) >= 4:
                            if doc not in container_por_nf: container_por_nf[doc] = cont

        return ativos_por_container, container_por_nf, aba_alvo

    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao ler planilha de {porto_nome}: {e}")
        return ativos_por_container, container_por_nf, mes_atual_nome


def organizar_porto(porto_nome, spreadsheet_id):
    print(Fore.CYAN + f"\n==================================================")
    print(Fore.YELLOW + Style.BRIGHT + f" 🚢 SINCRONIZANDO PORTO: {porto_nome}")
    print(Fore.CYAN + f"==================================================")

    ativos, container_por_nf, aba_atual_nome = obter_dados_planilha(spreadsheet_id, porto_nome)

    if not ativos and not container_por_nf:
        print(Fore.WHITE + "   ☕ Nenhum dado encontrado na planilha. Pulando...")
        return

    print(Fore.GREEN + f"   ✅ {len(ativos)} contêiner(es) ativo(s) mapeado(s).")

    ano_atual = datetime.now().year
    mes_atual_num = datetime.now().month
    calculo_atual = (ano_atual * 12) + mes_atual_num

    movidos_resgate = 0
    movidos_backup = 0
    pastas_criadas = 0

    pasta_norte_nordeste = DROPBOX_ROOT 
    
    if not os.path.exists(pasta_norte_nordeste):
        print(Fore.RED + f"   ❌ Pasta NORTE NORDESTE não encontrada: {pasta_norte_nordeste}")
        return

    # Descobre qual é a pasta do porto atual no Dropbox (Ex: DOCUMENTAÇÃO DE ENTREGA SUAPE 2026)
    pasta_porto_atual = None
    for p_drop in os.listdir(pasta_norte_nordeste):
        nome_limpo = unicodedata.normalize('NFKD', p_drop.upper()).encode('ASCII', 'ignore').decode('utf-8')
        if porto_nome in nome_limpo and "ENTREGA" in nome_limpo and str(ano_atual) in nome_limpo:
            pasta_porto_atual = os.path.join(pasta_norte_nordeste, p_drop)
            break

    if not pasta_porto_atual:
        pasta_porto_atual = os.path.join(pasta_norte_nordeste, f"DOCUMENTAÇÃO DE ENTREGA {porto_nome} {ano_atual}")
        os.makedirs(pasta_porto_atual, exist_ok=True)

    print(Fore.WHITE + f"   📂 Trabalhando no diretório base: {os.path.basename(pasta_porto_atual)}")

    # ======================================================================
    # FASE 1: CRIAR PASTAS FALTANTES PARA TODOS OS CONTÊINERES ATIVOS
    # ======================================================================
    for cont, cliente in ativos.items():
        if porto_nome == "SALVADOR":
            pasta_correta = os.path.join(pasta_porto_atual, aba_atual_nome, cont)
        else:
            pasta_correta = os.path.join(pasta_porto_atual, aba_atual_nome, cliente, cont)

        if not os.path.exists(pasta_correta):
            os.makedirs(pasta_correta, exist_ok=True)
            pastas_criadas += 1
            print(Fore.CYAN + f"   📁 Recriada pasta base para contêiner apagado: {cont}")

    # ======================================================================
    # FASE 2: VARREDURA GLOBAL DE ARQUIVOS (RESGATE DE ÓRFÃOS EM QUALQUER LUGAR)
    # ======================================================================
    print(Fore.YELLOW + f"   🔍 Iniciando Varredura Global por Arquivos Perdidos...")
    for root_dir, dirs, files in os.walk(pasta_porto_atual):
        # Ignora a pasta de erros ou backups
        if "00_ERROS_DE_LEITURA" in root_dir or "BACKUP" in root_dir.upper():
            continue

        nome_pasta_atual = os.path.basename(root_dir).upper()
        # Se a pasta já tem o nome de um contêiner válido, assumimos que está organizada
        is_pasta_container = bool(re.match(r'^[A-Z]{4}\d{7}$', nome_pasta_atual))

        # BATIMENTO CARDÍACO: Mostra em que pasta o robô está a passar
        if files:
            print(Fore.BLACK + Style.BRIGHT + f"   ... Varrendo pasta: {nome_pasta_atual[:30]} ({len(files)} arquivos encontrados)")

        for nome_arquivo in files:
            caminho_arquivo = os.path.join(root_dir, nome_arquivo)
            container_destino = ""
            cliente_destino = ""
            origem_resolucao = ""

            # 1. Verifica se o nome do arquivo tem o contêiner escrito
            cont_no_nome = re.search(r'[A-Z]{4}\d{7}', nome_arquivo.upper())
            if cont_no_nome:
                cont_candidato = cont_no_nome.group(0)
                if cont_candidato in ativos:
                    container_destino = cont_candidato
                    cliente_destino = ativos[cont_candidato]
                    origem_resolucao = "nome do arquivo"

            # 2. Verifica se há um número solto no nome (NF ou CT-e)
            if not container_destino:
                numeros_no_nome = re.findall(r'\d+', nome_arquivo)
                for num in numeros_no_nome:
                    num_limpo = num.lstrip("0")
                    if num_limpo and num_limpo in container_por_nf:
                        cont_candidato = container_por_nf[num_limpo]
                        if cont_candidato in ativos:
                            container_destino = cont_candidato
                            cliente_destino = ativos[cont_candidato]
                            origem_resolucao = f"NF/Doc {num_limpo} no título"
                            break

            # 3. Extração Profunda (Leitura de PDF/XML) -> APENAS se o arquivo estiver solto/perdido
            if not container_destino and not is_pasta_container and caminho_arquivo.lower().endswith(('.pdf', '.xml')):
                docs_arquivo = extrair_nfs_do_arquivo(caminho_arquivo)
                for doc in docs_arquivo:
                    doc = str(doc).strip().lstrip("0")
                    if doc in container_por_nf:
                        cont_candidato = container_por_nf[doc]
                        if cont_candidato in ativos:
                            container_destino = cont_candidato
                            cliente_destino = ativos[cont_candidato]
                            origem_resolucao = f"leitura profunda (Doc {doc})"
                            break

            # Se descobrimos o dono do ficheiro, verificamos se ele já está lá. Se não estiver, MUDAMOS!
            if container_destino and cliente_destino:
                if porto_nome == "SALVADOR":
                    pasta_destino = os.path.join(pasta_porto_atual, aba_atual_nome, container_destino)
                else:
                    pasta_destino = os.path.join(pasta_porto_atual, aba_atual_nome, cliente_destino, container_destino)

                if os.path.normpath(root_dir) != os.path.normpath(pasta_destino):
                    sucesso = mover_arquivo_seguro(caminho_arquivo, pasta_destino, nome_arquivo)
                    if sucesso:
                        print(Fore.MAGENTA + f"   🚁 Resgate Global ({origem_resolucao}): {nome_arquivo} → {cliente_destino}/{container_destino}")
                        movidos_resgate += 1

    # ======================================================================
    # FASE 3: BACKUP DE INATIVOS (Meses Passados)
    # ======================================================================
    print(Fore.YELLOW + f"   🧹 Analisando Contêineres Inativos para Backup...")
    for pasta_mes in os.listdir(pasta_porto_atual):
        caminho_mes = os.path.join(pasta_porto_atual, pasta_mes)
        if not os.path.isdir(caminho_mes): continue

        mes_pasta_num = MESES_INV.get(pasta_mes.upper().replace("Ç", "C").replace("Ã", "A"))
        if not mes_pasta_num: continue
        
        calculo_pasta = (ano_atual * 12) + mes_pasta_num

        for item_lvl1 in os.listdir(caminho_mes):
            caminho_lvl1 = os.path.join(caminho_mes, item_lvl1)
            if not os.path.isdir(caminho_lvl1): continue

            if porto_nome == "SALVADOR":
                conteineres_para_ver = [(item_lvl1, caminho_lvl1, None)]
            else:
                conteineres_para_ver = []
                for c in os.listdir(caminho_lvl1):
                    p = os.path.join(caminho_lvl1, c)
                    if os.path.isdir(p):
                        conteineres_para_ver.append((c, p, item_lvl1))

            for cont_nome, caminho_cont, cliente_nome in conteineres_para_ver:
                cont_limpo = re.sub(r'[^A-Z0-9]', '', cont_nome.upper())
                if not bool(re.match(r'^[A-Z]{4}\d{7}$', cont_limpo)):
                    continue

                if cont_limpo not in ativos and calculo_pasta < calculo_atual:
                    drive_backup = os.path.splitdrive(PASTA_BACKUP_RAIZ)[0] + "\\"
                    if not os.path.exists(drive_backup) or not os.path.exists(PASTA_BACKUP_RAIZ):
                        continue

                    caminho_backup_raiz = PASTA_BACKUP_RAIZ
                    for sub_b in os.listdir(PASTA_BACKUP_RAIZ):
                        sub_limpo = unicodedata.normalize('NFKD', sub_b.upper()).encode('ASCII', 'ignore').decode('utf-8')
                        if porto_nome in sub_limpo and "ENTREGA" in sub_limpo:
                            caminho_backup_raiz = os.path.join(PASTA_BACKUP_RAIZ, sub_b)
                            break

                    if porto_nome == "SALVADOR":
                        caminho_backup = os.path.join(caminho_backup_raiz, str(ano_atual), pasta_mes.upper(), cont_limpo)
                    else:
                        caminho_backup = os.path.join(caminho_backup_raiz, str(ano_atual), pasta_mes.upper(), cliente_nome or "DESCONHECIDO", cont_limpo)

                    print(Fore.MAGENTA + f"   📦 BACKUP: Arquivando {cont_limpo} inativo → Drive G:")
                    mover_com_mesclagem(caminho_cont, caminho_backup)
                    movidos_backup += 1

    # ======================================================================
    # FASE 4: DESTRUIR PASTAS VAZIAS ("BOTTOM-UP")
    # ======================================================================
    for dirpath, dirnames, filenames in os.walk(pasta_porto_atual, topdown=False):
        if not os.listdir(dirpath):
            try: os.rmdir(dirpath)
            except: pass

    # ======================================================================
    # RESULTADO FINAL DO PORTO
    # ======================================================================
    if pastas_criadas > 0 or movidos_resgate > 0 or movidos_backup > 0:
        if pastas_criadas > 0:
            print(Fore.GREEN + f"   🏁 {pastas_criadas} pasta(s) de contêiner recriada(s).")
        if movidos_resgate > 0:
            print(Fore.GREEN + f"   🏁 {movidos_resgate} arquivo(s) resgatado(s) na Varredura Global e agrupados corretamente.")
        if movidos_backup > 0:
            print(Fore.GREEN + f"   🏁 {movidos_backup} contêiner(es) inativo(s) arquivado(s) no Drive G:.")
    else:
        print(Fore.WHITE + "   ☕ Tudo limpo, auditado e milimetricamente sincronizado.")

def iniciar_organizacao():
    print(Fore.BLUE + "\n" + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + f" 🗄️ INICIANDO GESTOR MASTER DE PASTAS E BACKUP ({datetime.now().strftime('%H:%M:%S')})")
    print(Fore.BLUE + "="*70)

    portos_alvo = ["SUAPE", "PECEM", "MANAUS", "SANTOS", "SALVADOR"]

    for pasta_entrada, s_id in ROTEAMENTO_PORTOS.items():
        nome_porto = os.path.basename(pasta_entrada).replace("entrada_", "").upper()
        if nome_porto in portos_alvo:
            organizar_porto(nome_porto, s_id)

    print(Fore.BLUE + "\n" + "="*70)
    print(Fore.GREEN + Style.BRIGHT + " 🧹 VARREDURA GLOBAL DE BACKUP E ORGANIZAÇÃO CONCLUÍDA!")
    print(Fore.BLUE + "="*70 + "\n")

if __name__ == "__main__":
    limpar_tela()
    iniciar_organizacao()