import os
import chromadb
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

# 1. DEFINE ONDE O CÉREBRO VAI FICAR SALVO NO SEU COMPUTADOR
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DB = os.path.join(BASE_DIR, "JARVIS_CEREBRO")

# 2. INICIA O BANCO DE DADOS (Se a pasta não existir, ele cria sozinho)
# Usamos PersistentClient para que ele NUNCA esqueça as coisas ao desligar o PC
cliente_chroma = chromadb.PersistentClient(path=PASTA_DB)

# 3. CRIA UMA "GAVETA" (COLEÇÃO) SÓ PARA AS MENSAGENS DO WHATSAPP
colecao_whatsapp = cliente_chroma.get_or_create_collection(name="historico_conversas")

def salvar_memoria(texto_mensagem, nome_autor, cargo_autor):
    """
    Função que o robô usará no futuro para guardar cada mensagem do WhatsApp.
    """
    # Cria uma identidade única para cada mensagem baseada na hora exata
    id_mensagem = f"msg_{int(datetime.now().timestamp() * 1000)}"
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    
    # Guarda no banco de dados
    colecao_whatsapp.add(
        documents=[texto_mensagem], # A memória em si (o texto)
        metadatas=[{"autor": nome_autor, "cargo": cargo_autor, "data": data_hoje}], # As "Etiquetas" (Metadados)
        ids=[id_mensagem] # O RG da mensagem
    )
    print(Fore.GREEN + f"✅ Memória salva: '{texto_mensagem}'")

def buscar_na_memoria(pergunta, limite_resultados=2):
    """
    Função que o Jarvis usará para pesquisar no cérebro antes de te responder.
    """
    print(Fore.YELLOW + f"\n🔍 Pesquisando no Cérebro por: '{pergunta}'...")
    
    # O banco vetorial faz a mágica matemática aqui
    resultados = colecao_whatsapp.query(
        query_texts=[pergunta],
        n_results=limite_resultados
    )
    
    return resultados

# =====================================================================
# 🧪 ÁREA DE TESTE (Para você ver a mágica acontecendo)
# =====================================================================
if __name__ == "__main__":
    print(Fore.CYAN + Style.BRIGHT + "=========================================")
    print(Fore.CYAN + Style.BRIGHT + "   INICIANDO TESTE DO CÉREBRO VETORIAL")
    print(Fore.CYAN + Style.BRIGHT + "=========================================\n")
    
    # Passo A: Simulando que o robô leu mensagens no WhatsApp e está guardando no cérebro
    print(Fore.WHITE + "1. Ensinando informações para o Jarvis...")
    salvar_memoria("O pneu da carreta do Bruno estourou na BR-101 e o borracheiro cobrou R$ 150,00.", "Bruno", "Motorista")
    salvar_memoria("A empresa VEXA mudou a regra. Agora eles querem receber os boletos apenas nas sextas-feiras.", "Douglas", "Diretoria")
    salvar_memoria("Deixei a chave do cadeado do contêiner vazio da MSC dentro da gaveta da recepção.", "Nivaldo", "Diretoria")
    
    # Passo B: Simulando o Douglas fazendo uma pergunta solta no WhatsApp
    pergunta_do_diretor = "Onde eu acho a chave pra abrir aquele equipamento vazio?"
    
    # Passo C: O Cérebro procura a resposta por significado
    resposta = buscar_na_memoria(pergunta_do_diretor)
    
    # Passo D: Mostrando o que ele encontrou
    print(Fore.MAGENTA + "\n🧠 O QUE O BANCO DE DADOS ENCONTROU (Pela lógica semântica):")
    
    documentos_encontrados = resposta['documents'][0]
    etiquetas_encontradas = resposta['metadatas'][0]
    
    for i in range(len(documentos_encontrados)):
        texto = documentos_encontrados[i]
        autor = etiquetas_encontradas[i]['autor']
        cargo = etiquetas_encontradas[i]['cargo']
        data = etiquetas_encontradas[i]['data']
        
        print(Fore.WHITE + f"\n   📦 Lembrança {i+1}: {texto}")
        print(Fore.CYAN + f"   🏷️ Etiquetas: Dita por {autor} ({cargo}) no dia {data}")