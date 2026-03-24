import os
import time
import shutil
import threading
import queue
import re
import unicodedata
from datetime import datetime
from colorama import init, Fore, Style
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import ROTEAMENTO_PORTOS, PASTA_ERROS, DROPBOX_DIR
from processor import processar_arquivo
# Importa função de busca de contêiner por NF no cache da planilha
from sheets_api import buscar_container_por_nf

try:
    from main_monitor import executar_ciclo_expresso
    INTEGRACAO_ATIVA = True
except ImportError:
    INTEGRACAO_ATIVA = False
    print(Fore.RED + "⚠️ main_monitor.py não encontrado. A integração expressa está desativada.")

init(autoreset=True)
fila_arquivos = queue.Queue()

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def banner():
    print(Fore.CYAN + Style.BRIGHT + "=" * 60)
    print(Fore.CYAN + "          ROBÔ DE LOGÍSTICA - MULTI PORTOS")
    print(Fore.CYAN + "          v13.0 - Fix NF sem Contêiner + Multi-Contêiner")
    print(Fore.CYAN + "=" * 60 + "\n")

def padronizar_nome_cliente(nome):
    if not nome: return "CLIENTE_DESCONHECIDO"
    if "-" in nome:
        nome = nome.split("-")[-1]
    nome = nome.upper().strip()
    nome = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('utf-8')
    nome = nome.replace(".", "").replace(",", "")
    termos_ignorar = [
        r'\bLTDA\b', r'\bS/?A\b', r'\bEIRELI\b', r'\bME\b', r'\bEPP\b',
        r'\bINDUSTRIA\b', r'\bIND\b', r'\bCOMERCIO\b', r'\bCOM\b',
        r'\bMATERIAL\b', r'\bMATERIAIS\b', r'\bCONSTRUCAO\b', r'\bCONSTRUCOES\b',
        r'\bDE\b', r'\bE\b', r'\bDO\b', r'\bDA\b'
    ]
    for termo in termos_ignorar:
        nome = re.sub(termo, ' ', nome)
    nome = re.sub(r'[\\/*?:"<>|]', "", nome)
    palavras = [p for p in nome.split() if p.strip()]
    if len(palavras) >= 2:
        return f"{palavras[0]} {palavras[1]}"
    elif len(palavras) > 0:
        return palavras[0]
    else:
        return "CLIENTE_DESCONHECIDO"

def worker_processamento():
    while True:
        caminho_arquivo, id_planilha, nome_porto = fila_arquivos.get()
        arquivo = os.path.basename(caminho_arquivo)

        try:
            print(Fore.YELLOW + f"\n⏳ Aguardando gravação no disco: {arquivo}...")
            time.sleep(3)

            if not os.path.exists(caminho_arquivo):
                print(Fore.RED + f"❌ Arquivo desapareceu antes do processamento: {arquivo}")
                continue

            print(Fore.CYAN + "\n" + "="*70)
            print(Fore.YELLOW + Style.BRIGHT + f"📄 NOVO DOCUMENTO: {arquivo}")
            print(Fore.WHITE + f"📍 Porto/Rota: {nome_porto}")
            print(Fore.CYAN + "-"*70)
            print(Fore.WHITE + "🤖 Lendo conteúdo com Inteligência Artificial...")

            sucesso, lista_dados_json = processar_arquivo(caminho_arquivo, id_planilha)

            if sucesso and lista_dados_json:
                if len(lista_dados_json) > 1:
                    print(Fore.GREEN + f"✅ Leitura Concluída! {len(lista_dados_json)} contêineres encontrados. Dividindo...")
                else:
                    print(Fore.GREEN + f"✅ Leitura Concluída!")

                for idx, dados_json in enumerate(lista_dados_json):

                    container = dados_json.get("CONTAINER", "").strip() if dados_json else ""
                    container_limpo = re.sub(r'[^A-Z0-9]', '', container)

                    # ================================================================
                    # FIX: NF chegou sem contêiner (ex: NF de CT-e multi-contêiner)
                    # A planilha já tem a linha com NF + contêiner (criada pelo CT-e).
                    # Buscamos o contêiner no cache da planilha pelo número da NF
                    # para criar a pasta no lugar certo em vez de ir para SEM_CONTAINER.
                    # ================================================================
                    if not container_limpo:
                        nf_para_busca = dados_json.get("NOTAS FISCAIS", "").strip() if dados_json else ""
                        if nf_para_busca:
                            container_recuperado = buscar_container_por_nf(id_planilha, nf_para_busca)
                            if container_recuperado:
                                container_limpo = container_recuperado
                                print(Fore.CYAN + f"🔗 Contêiner recuperado da planilha via NF {nf_para_busca}: {container_limpo}")

                    agora = datetime.now()
                    ano_atual = str(agora.year)
                    meses_pt = {
                        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
                        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
                        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
                    }
                    mes_atual = meses_pt.get(agora.month, "GERAL")

                    clientes_str = dados_json.get("CLIENTES", "").strip() if dados_json else ""
                    destinatario_limpo = padronizar_nome_cliente(clientes_str)

                    dropbox_root = os.path.dirname(DROPBOX_DIR)
                    caminho_visual = ""

                    if nome_porto == "SANTOS":
                        booking_str = dados_json.get("BOOKING", "").strip() if dados_json else ""
                        booking_limpo = re.sub(r'[\\/*?:"<>|]', "", booking_str)
                        if not booking_limpo: booking_limpo = "SEM_BOOKING"

                        base_porto = os.path.join(dropbox_root, "NORTE NORDESTE", "DOCUMENTAÇÃO NAVIO", "SANTOS", "RISADINHA")
                        destino_porto_raiz = os.path.join(base_porto, booking_limpo, container_limpo if container_limpo else "SEM_CONTAINER")
                        pasta_orfaos = os.path.join(base_porto, booking_limpo, "SEM_CONTAINER")

                        subpasta = ""
                        if dados_json.get("NOTAS FISCAIS"):
                            subpasta = "NFS"
                        elif dados_json.get("CTE-E"):
                            subpasta = "CTE NN"
                        elif dados_json.get("CT-E ARMADOR"):
                            subpasta = "CTE NORCOAST"

                        destino_porto = os.path.join(destino_porto_raiz, subpasta) if subpasta else destino_porto_raiz
                        caminho_visual = f"SANTOS > RISADINHA > {booking_limpo} > {container_limpo if container_limpo else 'SEM_CONTAINER'} > {subpasta}"

                    elif nome_porto == "SALVADOR":
                        nome_pasta_porto = f"DOCUMENTAÇÃO DE ENTREGA SALVADOR {ano_atual}"
                        base_porto = os.path.join(dropbox_root, "NORTE NORDESTE", nome_pasta_porto)
                        destino_porto_raiz = os.path.join(base_porto, mes_atual, destinatario_limpo, container_limpo if container_limpo else "SEM_CONTAINER")
                        pasta_orfaos = os.path.join(base_porto, mes_atual, destinatario_limpo, "SEM_CONTAINER")
                        destino_porto = destino_porto_raiz
                        caminho_visual = f"SALVADOR {ano_atual} > {mes_atual} > {destinatario_limpo} > {container_limpo if container_limpo else 'SEM_CONTAINER'}"

                    else:
                        nome_pasta_porto = f"DOCUMENTAÇÃO DE ENTREGA {nome_porto} {ano_atual}"
                        base_porto = os.path.join(dropbox_root, "NORTE NORDESTE", nome_pasta_porto)
                        destino_porto_raiz = os.path.join(base_porto, mes_atual, destinatario_limpo, container_limpo if container_limpo else "SEM_CONTAINER")
                        pasta_orfaos = os.path.join(base_porto, mes_atual, destinatario_limpo, "SEM_CONTAINER")
                        destino_porto = destino_porto_raiz
                        caminho_visual = f"{nome_porto} {ano_atual} > {mes_atual} > {destinatario_limpo} > {container_limpo if container_limpo else 'SEM_CONTAINER'}"

                    if not os.path.exists(destino_porto):
                        os.makedirs(destino_porto)

                    destino_final = os.path.join(destino_porto, arquivo)
                    if os.path.exists(destino_final):
                        base, ext = os.path.splitext(arquivo)
                        destino_final = os.path.join(destino_porto, f"{base}_{int(time.time())}_{idx}{ext}")

                    if idx == len(lista_dados_json) - 1:
                        shutil.move(caminho_arquivo, destino_final)
                    else:
                        shutil.copy2(caminho_arquivo, destino_final)

                    print(Fore.WHITE + f"\n📦 CONTÊINER: {Fore.YELLOW}{Style.BRIGHT}{container_limpo if container_limpo else 'SEM CONTÊINER (Aguardando par)'}")
                    if nome_porto == "SANTOS":
                        print(Fore.WHITE + f"🏷️  Booking: {booking_limpo}")
                    else:
                        print(Fore.WHITE + f"👤 Cliente: {destinatario_limpo}")

                    print(Fore.GREEN + f"📁 Guardado em: {caminho_visual}")

                    # Resgate de órfãos: se agora temos o contêiner, move os arquivos de SEM_CONTAINER
                    if container_limpo:
                        if os.path.exists(pasta_orfaos) and pasta_orfaos != destino_porto_raiz:
                            arquivos_resgatados = 0
                            for root_dir, dirs, files in os.walk(pasta_orfaos):
                                for orfao in files:
                                    caminho_orfao = os.path.join(root_dir, orfao)
                                    rel_path = os.path.relpath(root_dir, pasta_orfaos)
                                    if rel_path == ".":
                                        destino_resgate_dir = destino_porto_raiz
                                    else:
                                        destino_resgate_dir = os.path.join(destino_porto_raiz, rel_path)

                                    if not os.path.exists(destino_resgate_dir):
                                        os.makedirs(destino_resgate_dir)

                                    destino_resgate = os.path.join(destino_resgate_dir, orfao)
                                    if os.path.exists(destino_resgate):
                                        b_orf, ext_orf = os.path.splitext(orfao)
                                        destino_resgate = os.path.join(destino_resgate_dir, f"{b_orf}_resgate_{int(time.time())}{ext_orf}")

                                    for _ in range(3):
                                        try:
                                            shutil.move(caminho_orfao, destino_resgate)
                                            arquivos_resgatados += 1
                                            break
                                        except:
                                            time.sleep(1)

                            if arquivos_resgatados > 0:
                                print(Fore.MAGENTA + f"🚁 Resgate Automático: {arquivos_resgatados} documento(s) órfão(s) movido(s) para {container_limpo}!")

                            try:
                                shutil.rmtree(pasta_orfaos)
                            except:
                                pass

                    if INTEGRACAO_ATIVA and dados_json:
                        cte_armador = dados_json.get("CT-E ARMADOR", "").strip()
                        cte_nosso = dados_json.get("CTE-E", "").strip()
                        tem_cte = bool(cte_armador or cte_nosso)

                        if container_limpo and tem_cte and nome_porto == "SUAPE":
                            print(Fore.CYAN + f"⚡ INTEGRAÇÃO TECON: Preparando faturamento de {container_limpo}...")

                            def disparar_quando_fila_vazia(num_container):
                                fila_arquivos.join()
                                time.sleep(3)
                                try:
                                    executar_ciclo_expresso(num_container)
                                except Exception as e:
                                    pass

                            threading.Thread(target=disparar_quando_fila_vazia, args=(container_limpo,), daemon=True).start()

            else:
                print(Fore.RED + Style.BRIGHT + f"\n❌ ATENÇÃO: Falha ao ler ou extrair dados deste documento.")
                destino_erro = os.path.join(PASTA_ERROS, arquivo)
                if not os.path.exists(PASTA_ERROS):
                    os.makedirs(PASTA_ERROS)
                if os.path.exists(destino_erro):
                    base, ext = os.path.splitext(arquivo)
                    destino_erro = os.path.join(PASTA_ERROS, f"{base}_{int(time.time())}{ext}")
                shutil.move(caminho_arquivo, destino_erro)
                print(Fore.RED + f"⚠️ Movido para a pasta de ERROS para verificação manual.")

            print(Fore.CYAN + "="*70)

        except Exception as e:
            print(Fore.RED + f"❌ Erro crítico no worker ao processar {arquivo}: {e}")
        finally:
            fila_arquivos.task_done()
            time.sleep(2)


class MonitorPortosHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        caminho_arquivo = event.src_path
        if caminho_arquivo.lower().endswith(('.pdf', '.xml', '.xlsx', '.xls', '.csv')):
            pasta_pai = os.path.dirname(caminho_arquivo)
            id_planilha = ROTEAMENTO_PORTOS.get(pasta_pai)
            if id_planilha:
                nome_porto = os.path.basename(pasta_pai).replace("entrada_", "").upper()
                print(Fore.MAGENTA + f"📥 NOVO ARQUIVO DETECTADO EM {nome_porto}: {os.path.basename(caminho_arquivo)}")
                fila_arquivos.put((caminho_arquivo, id_planilha, nome_porto))


def varredura_inicial():
    print(Fore.YELLOW + "🔍 Realizando varredura de passivo...")
    arquivos_encontrados = 0
    for pasta_entrada, id_planilha in ROTEAMENTO_PORTOS.items():
        if not os.path.exists(pasta_entrada):
            os.makedirs(pasta_entrada)
            continue
        arquivos = [f for f in os.listdir(pasta_entrada) if f.lower().endswith(('.pdf', '.xml', '.xlsx', '.xls', '.csv'))]
        nome_porto = os.path.basename(pasta_entrada).replace("entrada_", "").upper()
        for arquivo in arquivos:
            caminho_completo = os.path.join(pasta_entrada, arquivo)
            fila_arquivos.put((caminho_completo, id_planilha, nome_porto))
            arquivos_encontrados += 1

    if arquivos_encontrados > 0:
        print(Fore.GREEN + f"✅ {arquivos_encontrados} arquivo(s) encontrado(s) e adicionado(s) à fila.")
    else:
        print(Fore.WHITE + "✅ Nenhum arquivo passivo. Pastas limpas.")


def main():
    limpar_tela()
    banner()

    t = threading.Thread(target=worker_processamento, daemon=True)
    t.start()
    varredura_inicial()

    print(Fore.YELLOW + "\n👀 Monitorando em tempo real as pastas:")
    observer = Observer()
    handler = MonitorPortosHandler()

    for pasta in ROTEAMENTO_PORTOS.keys():
        nome_pasta = os.path.basename(pasta)
        print(Fore.WHITE + f"   📂 {nome_pasta}")
        observer.schedule(handler, path=pasta, recursive=False)

    print(Fore.YELLOW + "\n📂 Destino dos Processados (Raiz): " + Fore.WHITE + os.path.join(os.path.dirname(DROPBOX_DIR), "NORTE NORDESTE"))
    print(Fore.CYAN + "-" * 60)
    print(Fore.GREEN + "🟢 SISTEMA ATIVO 24/7.")
    print(Fore.WHITE + "Pressione Ctrl+C para parar o robô de forma segura.\n")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(Fore.RED + "\n\n🛑 Parando o sistema de monitoramento...")
        observer.stop()
    observer.join()
    print(Fore.RED + "Desligado.")


if __name__ == "__main__":
    main()
