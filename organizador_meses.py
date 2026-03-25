import os
import re
import shutil
import time
import unicodedata
from datetime import datetime
from colorama import init, Fore, Style
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import BASE_DIR, DROPBOX_DIR, ROTEAMENTO_PORTOS
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

DROPBOX_ROOT = os.path.dirname(DROPBOX_DIR)
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
        try:
            shutil.rmtree(origem)
        except:
            pass

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
        except Exception as e:
            time.sleep(1)
    return False

def extrair_nfs_do_arquivo(caminho_arquivo):
    nfs = []
    try:
        if caminho_arquivo.lower().endswith('.pdf') and EXTRATOR_PDF_OK:
            texto = extrair_texto_pdf(caminho_arquivo)
            if texto:
                chaves = re.findall(r'\d{44}', texto)
                for chave in chaves:
                    if chave[20:22] in ["55", "57"]:
                        num = str(int(chave[25:34]))
                        if num and num not in nfs:
                            nfs.append(num)

                if not nfs:
                    matches = re.findall(r'N[ºO°]?\s*\.?\s*0*([1-9]\d{4,8})', texto)
                    for m in matches:
                        if m not in nfs:
                            nfs.append(m)
    except Exception as e:
        print(Fore.YELLOW + f"      ⚠️ Não foi possível ler NF do arquivo {os.path.basename(caminho_arquivo)}: {e}")
    return nfs

def obter_dados_planilha(spreadsheet_id, porto_nome):
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    mes_atual_num = datetime.now().month
    mes_atual_nome = MAPA_MESES.get(mes_atual_num, "MARÇO")

    ativos_por_container = {}
    container_por_nf = {}

    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        abas = [s["properties"]["title"].upper() for s in meta.get("sheets", [])]

        aba_alvo = mes_atual_nome if mes_atual_nome in abas else ("MARCO" if "MARCO" in abas else abas[0])
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{aba_alvo}!A:AZ"
        ).execute()
        linhas = res.get("values", [])

        if not linhas:
            return ativos_por_container, container_por_nf, aba_alvo

        idx_cont = -1
        idx_cliente = -1
        idx_nf = -1
        linha_cabecalho = 0

        for num_linha, linha in enumerate(linhas[:10]):
            cabecalho = [str(c).upper().strip() for c in linha]

            for i, col in enumerate(cabecalho):
                if col in ["CLIENTES", "CLIENTE", "DESTINATARIO", "DESTINATÁRIO", "EMPRESA"]:
                    idx_cliente = i
                if col in ["CONTAINER", "CNTR", "UNIDADE"]:
                    idx_cont = i
                if col in ["NOTAS FISCAIS", "NF", "NOTA FISCAL"]:
                    idx_nf = i

            if idx_cont != -1 and idx_cliente != -1:
                linha_cabecalho = num_linha
                break

        if idx_cliente == -1 and idx_cont != -1:
            idx_cliente = 0

        if idx_cont == -1:
            print(Fore.RED + f"   ❌ Coluna 'CONTAINER' não encontrada na planilha de {porto_nome}!")
            return ativos_por_container, container_por_nf, aba_alvo

        print(Fore.GREEN + f"   👁️ Colunas mapeadas → Cliente:[{idx_cliente+1}] Contêiner:[{idx_cont+1}] NF:[{idx_nf+1 if idx_nf != -1 else 'N/A'}]")

        for i in range(linha_cabecalho + 1, len(linhas)):
            linha = linhas[i]
            if len(linha) <= idx_cont:
                continue

            cont = re.sub(r'[^A-Z0-9]', '', str(linha[idx_cont]).upper())
            if not cont or len(cont) < 10:
                continue

            cliente_bruto = str(linha[idx_cliente]) if len(linha) > idx_cliente else ""
            cliente_limpo = padronizar_nome_cliente(cliente_bruto)

            if cont not in ativos_por_container or ativos_por_container[cont] == "CLIENTE_DESCONHECIDO":
                ativos_por_container[cont] = cliente_limpo

            if idx_nf != -1 and len(linha) > idx_nf:
                nfs_str = str(linha[idx_nf]).strip()
                for nf in re.split(r'[,;]', nfs_str):
                    nf = nf.strip().lstrip("0")
                    if nf and len(nf) >= 4:
                        if nf not in container_por_nf:
                            container_por_nf[nf] = cont

        if ativos_por_container:
            amostra = list(ativos_por_container.items())[:3]
            print(Fore.CYAN + f"   🧪 Raio-X (3 exemplos contêiner→cliente): {amostra}")
        if container_por_nf:
            amostra_nf = list(container_por_nf.items())[:3]
            print(Fore.CYAN + f"   🧪 Raio-X (3 exemplos NF→contêiner): {amostra_nf}")

        return ativos_por_container, container_por_nf, aba_alvo

    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao ler planilha de {porto_nome}: {e}")
        return ativos_por_container, container_por_nf, mes_atual_nome

def resgatar_sem_container(pasta_sem_container, destino_base_porto, aba_atual_nome,
                            ativos_por_container, container_por_nf, porto_nome):
    if not os.path.exists(pasta_sem_container):
        return 0

    arquivos = [f for f in os.listdir(pasta_sem_container) if os.path.isfile(os.path.join(pasta_sem_container, f))]
    if not arquivos:
        return 0

    print(Fore.YELLOW + f"   📂 Resgatando {len(arquivos)} arquivo(s) de SEM_CONTAINER...")
    resgatados = 0

    for nome_arquivo in arquivos:
        caminho_arquivo = os.path.join(pasta_sem_container, nome_arquivo)
        container_destino = ""
        cliente_destino = ""
        origem_resolucao = ""

        cont_no_nome = re.search(r'[A-Z]{4}\d{7}', nome_arquivo.upper())
        if cont_no_nome:
            cont_candidato = cont_no_nome.group(0)
            if cont_candidato in ativos_por_container:
                container_destino = cont_candidato
                cliente_destino = ativos_por_container[cont_candidato]
                origem_resolucao = "nome do arquivo"

        if not container_destino and caminho_arquivo.lower().endswith('.pdf'):
            nfs_arquivo = extrair_nfs_do_arquivo(caminho_arquivo)
            for nf in nfs_arquivo:
                if nf in container_por_nf:
                    cont_candidato = container_por_nf[nf]
                    if cont_candidato in ativos_por_container:
                        container_destino = cont_candidato
                        cliente_destino = ativos_por_container[cont_candidato]
                        origem_resolucao = f"NF {nf} → planilha"
                        break

        if container_destino and cliente_destino:
            if porto_nome == "SALVADOR":
                pasta_destino = os.path.join(destino_base_porto, aba_atual_nome, container_destino)
            else:
                pasta_destino = os.path.join(destino_base_porto, aba_atual_nome, cliente_destino, container_destino)

            sucesso = mover_arquivo_seguro(caminho_arquivo, pasta_destino, nome_arquivo)
            if sucesso:
                print(Fore.MAGENTA + f"   🚁 Resgatado ({origem_resolucao}): {nome_arquivo} → {cliente_destino}/{container_destino}")
                resgatados += 1
        else:
            print(Fore.WHITE + f"   ⏭️ Não resolvido (sem referência na planilha): {nome_arquivo}")

    try:
        if os.path.exists(pasta_sem_container) and not os.listdir(pasta_sem_container):
            shutil.rmtree(pasta_sem_container)
            print(Fore.GREEN + f"   🗑️ Pasta SEM_CONTAINER removida (vazia).")
    except:
        pass

    return resgatados

def organizar_porto(porto_nome, spreadsheet_id):
    print(Fore.CYAN + f"\n==================================================")
    print(Fore.YELLOW + Style.BRIGHT + f" 🚢 SINCRONIZANDO PORTO: {porto_nome}")
    print(Fore.CYAN + f"==================================================")

    ativos, container_por_nf, aba_atual_nome = obter_dados_planilha(spreadsheet_id, porto_nome)

    if not ativos and not container_por_nf:
        print(Fore.WHITE + "   ☕ Nenhum dado encontrado na planilha. Pulando...")
        return

    print(Fore.GREEN + f"   ✅ {len(ativos)} contêiner(es) ativo(s) | {len(container_por_nf)} NF(s) mapeadas na aba {aba_atual_nome}.")

    ano_atual = datetime.now().year
    mes_atual_num = datetime.now().month
    calculo_atual = (ano_atual * 12) + mes_atual_num

    movidos_resgate = 0
    movidos_backup = 0
    resgatados_sem_container = 0

    pasta_norte_nordeste = os.path.join(DROPBOX_ROOT, "NORTE NORDESTE")
    if not os.path.exists(pasta_norte_nordeste):
        print(Fore.RED + f"   ❌ Pasta NORTE NORDESTE não encontrada: {pasta_norte_nordeste}")
        return

    for pasta_ano_dropbox in os.listdir(pasta_norte_nordeste):
        caminho_base_dropbox = os.path.join(pasta_norte_nordeste, pasta_ano_dropbox)
        if not os.path.isdir(caminho_base_dropbox):
            continue

        nome_limpo = unicodedata.normalize('NFKD', pasta_ano_dropbox.upper()).encode('ASCII', 'ignore').decode('utf-8')

        if porto_nome not in nome_limpo or "ENTREGA" not in nome_limpo:
            continue

        print(Fore.WHITE + f"   📂 Vasculhando o Dropbox em: {pasta_ano_dropbox}...")
        ano_match = re.search(r'\d{4}', pasta_ano_dropbox)
        ano_pasta_int = int(ano_match.group()) if ano_match else ano_atual

        for pasta_mes in os.listdir(caminho_base_dropbox):
            caminho_mes = os.path.join(caminho_base_dropbox, pasta_mes)
            if not os.path.isdir(caminho_mes):
                continue

            mes_pasta_num = MESES_INV.get(pasta_mes.upper().replace("Ç", "C").replace("Ã", "A"))
            if not mes_pasta_num:
                continue

            calculo_pasta = (ano_pasta_int * 12) + mes_pasta_num

            for item_lvl1 in os.listdir(caminho_mes):
                caminho_lvl1 = os.path.join(caminho_mes, item_lvl1)
                if not os.path.isdir(caminho_lvl1):
                    continue

                if porto_nome == "SALVADOR":
                    conteineres_para_ver = [(item_lvl1, caminho_lvl1, None)]
                else:
                    conteineres_para_ver = []
                    for c in os.listdir(caminho_lvl1):
                        p = os.path.join(caminho_lvl1, c)
                        if os.path.isdir(p):
                            conteineres_para_ver.append((c, p, item_lvl1))

                    pasta_sem_cont = os.path.join(caminho_lvl1, "SEM_CONTAINER")
                    if os.path.exists(pasta_sem_cont):
                        destino_base = caminho_base_dropbox
                        n = resgatar_sem_container(
                            pasta_sem_cont,
                            destino_base,
                            pasta_mes.upper(),
                            ativos,
                            container_por_nf,
                            porto_nome
                        )
                        resgatados_sem_container += n

                for cont_nome, caminho_cont, cliente_nome in conteineres_para_ver:
                    cont_limpo = re.sub(r'[^A-Z0-9]', '', cont_nome.upper())
                    if len(cont_limpo) < 10:
                        continue

                    if cont_limpo in ativos:
                        cliente_correto = ativos[cont_limpo]
                        if porto_nome == "SALVADOR":
                            caminho_correto = os.path.join(pasta_norte_nordeste, pasta_ano_dropbox, aba_atual_nome, cont_limpo)
                        else:
                            caminho_correto = os.path.join(pasta_norte_nordeste, pasta_ano_dropbox, aba_atual_nome, cliente_correto, cont_limpo)

                        if caminho_cont != caminho_correto:
                            print(Fore.YELLOW + f"   🚁 CORRIGINDO: {cont_limpo} → {aba_atual_nome}/{cliente_correto}")
                            mover_com_mesclagem(caminho_cont, caminho_correto)
                            movidos_resgate += 1

                    else:
                        if calculo_pasta < calculo_atual:
                            drive_backup = os.path.splitdrive(PASTA_BACKUP_RAIZ)[0] + "\\"
                            if not os.path.exists(drive_backup):
                                print(Fore.YELLOW + f"   ⚠️ Drive de backup '{drive_backup}' não está conectado. Pulando backup de {cont_limpo}.")
                                continue

                            if not os.path.exists(PASTA_BACKUP_RAIZ):
                                print(Fore.YELLOW + f"   ⚠️ Pasta de backup não encontrada: {PASTA_BACKUP_RAIZ}. Pulando backup de {cont_limpo}.")
                                continue

                            caminho_backup_raiz = PASTA_BACKUP_RAIZ
                            for sub_b in os.listdir(PASTA_BACKUP_RAIZ):
                                sub_limpo = unicodedata.normalize('NFKD', sub_b.upper()).encode('ASCII', 'ignore').decode('utf-8')
                                if porto_nome in sub_limpo and "ENTREGA" in sub_limpo:
                                    caminho_backup_raiz = os.path.join(PASTA_BACKUP_RAIZ, sub_b)
                                    break

                            if porto_nome == "SALVADOR":
                                caminho_backup = os.path.join(caminho_backup_raiz, str(ano_pasta_int), pasta_mes.upper(), cont_limpo)
                            else:
                                caminho_backup = os.path.join(caminho_backup_raiz, str(ano_pasta_int), pasta_mes.upper(), cliente_nome or "DESCONHECIDO", cont_limpo)

                            print(Fore.MAGENTA + f"   📦 BACKUP: Arquivando {cont_limpo} → Drive G: ({ano_pasta_int}/{pasta_mes.upper()})")
                            mover_com_mesclagem(caminho_cont, caminho_backup)
                            movidos_backup += 1

                if porto_nome != "SALVADOR":
                    try:
                        if os.path.exists(caminho_lvl1) and not os.listdir(caminho_lvl1):
                            shutil.rmtree(caminho_lvl1)
                    except:
                        pass

    drive_backup = os.path.splitdrive(PASTA_BACKUP_RAIZ)[0] + "\\"
    if not os.path.exists(drive_backup):
        print(Fore.YELLOW + f"   ⚠️ Drive de backup '{drive_backup}' não está conectado. Pulando varredura do backup.")
    elif not os.path.exists(PASTA_BACKUP_RAIZ):
        print(Fore.YELLOW + f"   ⚠️ Pasta de backup não encontrada: {PASTA_BACKUP_RAIZ}. Pulando.")
    else:
        pasta_backup_porto = None
        for sub_b in os.listdir(PASTA_BACKUP_RAIZ):
            sub_limpo = unicodedata.normalize('NFKD', sub_b.upper()).encode('ASCII', 'ignore').decode('utf-8')
            if porto_nome in sub_limpo and "ENTREGA" in sub_limpo:
                pasta_backup_porto = os.path.join(PASTA_BACKUP_RAIZ, sub_b)
                break

        if pasta_backup_porto and os.path.exists(pasta_backup_porto):
            print(Fore.WHITE + f"   📂 Vasculhando o Drive de Backup: {pasta_backup_porto}...")
            for pasta_ano in os.listdir(pasta_backup_porto):
                caminho_ano = os.path.join(pasta_backup_porto, pasta_ano)
                if not os.path.isdir(caminho_ano):
                    continue

                for pasta_mes in os.listdir(caminho_ano):
                    caminho_mes = os.path.join(caminho_ano, pasta_mes)
                    if not os.path.isdir(caminho_mes):
                        continue

                    for item_lvl1 in os.listdir(caminho_mes):
                        caminho_lvl1 = os.path.join(caminho_mes, item_lvl1)
                        if not os.path.isdir(caminho_lvl1):
                            continue

                        if porto_nome == "SALVADOR":
                            conteineres_para_ver = [(item_lvl1, caminho_lvl1)]
                        else:
                            conteineres_para_ver = []
                            for c in os.listdir(caminho_lvl1):
                                p = os.path.join(caminho_lvl1, c)
                                if os.path.isdir(p):
                                    conteineres_para_ver.append((c, p))

                        for cont_nome, caminho_cont in conteineres_para_ver:
                            cont_limpo = re.sub(r'[^A-Z0-9]', '', cont_nome.upper())
                            if len(cont_limpo) < 10:
                                continue

                            if cont_limpo in ativos:
                                cliente_correto = ativos[cont_limpo]
                                pasta_dropbox_correta = f"DOCUMENTAÇÃO DE ENTREGA {porto_nome} {ano_atual}"
                                for p_drop in os.listdir(pasta_norte_nordeste):
                                    if porto_nome in p_drop.upper() and "ENTREGA" in p_drop.upper():
                                        pasta_dropbox_correta = p_drop
                                        break

                                if porto_nome == "SALVADOR":
                                    caminho_correto = os.path.join(pasta_norte_nordeste, pasta_dropbox_correta, aba_atual_nome, cont_limpo)
                                else:
                                    caminho_correto = os.path.join(pasta_norte_nordeste, pasta_dropbox_correta, aba_atual_nome, cliente_correto, cont_limpo)

                                print(Fore.RED + Style.BRIGHT + f"   🚨 URGENTE: Resgatando {cont_limpo} do Drive G: → {cliente_correto}!")
                                mover_com_mesclagem(caminho_cont, caminho_correto)
                                movidos_resgate += 1

                        if porto_nome != "SALVADOR":
                            try:
                                if os.path.exists(caminho_lvl1) and not os.listdir(caminho_lvl1):
                                    shutil.rmtree(caminho_lvl1)
                            except:
                                pass

    if movidos_resgate > 0 or movidos_backup > 0 or resgatados_sem_container > 0:
        if movidos_resgate > 0:
            print(Fore.GREEN + f"   🏁 {movidos_resgate} contêiner(es) organizado(s)/resgatado(s) para o mês atual.")
        if movidos_backup > 0:
            print(Fore.GREEN + f"   🏁 {movidos_backup} contêiner(es) arquivado(s) no Drive G:.")
        if resgatados_sem_container > 0:
            print(Fore.GREEN + f"   🏁 {resgatados_sem_container} arquivo(s) resgatado(s) de SEM_CONTAINER para a pasta correta.")
    else:
        print(Fore.WHITE + "   ☕ Tudo limpo e milimetricamente sincronizado.")

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