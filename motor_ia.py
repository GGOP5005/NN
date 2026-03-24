import os
import chromadb
from datetime import datetime
from colorama import init, Fore
from google import genai
from google.genai import types

try:
    from docx import Document
    from docx2pdf import convert
except ImportError:
    pass

from config import LISTA_CHAVES_GEMINI, BASE_DIR

init(autoreset=True)

# =====================================================================
# 1. CONFIGURAÇÃO DO CÉREBRO E MEMÓRIA
# =====================================================================
PASTA_DB = os.path.join(BASE_DIR, "JARVIS_CEREBRO")
cliente_chroma = chromadb.PersistentClient(path=PASTA_DB)

# O Jarvis agora tem acesso a DUAS gavetas
colecao_whatsapp = cliente_chroma.get_or_create_collection(name="historico_conversas")
colecao_regras = cliente_chroma.get_or_create_collection(name="regras_empresa")

ARQUIVOS_PARA_ENVIAR = []

# Função interna para gravar a memória passivamente
def salvar_memoria_conversa(remetente, pergunta, resposta_ia):
    id_msg = f"chat_{int(datetime.now().timestamp() * 1000)}"
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Salva o bloco da conversa inteira para dar contexto
    bloco_conversa = f"Usuário ({remetente}) perguntou: '{pergunta}'. Jarvis respondeu: '{resposta_ia}'"
    
    colecao_whatsapp.add(
        documents=[bloco_conversa],
        metadatas=[{"autor": remetente, "data": data_hora, "tipo": "whatsapp"}],
        ids=[id_msg]
    )
    print(Fore.MAGENTA + f"   💾 [MEMÓRIA] Conversa com {remetente} salva no córtex permanentemente.")

# =====================================================================
# 2. FERRAMENTAS DO JARVIS (FUNCTIONS)
# =====================================================================

def buscar_regras_e_historico(assunto: str) -> str:
    """
    Usa esta ferramenta SEMPRE que precisares lembrar de alguma regra da empresa, 
    histórico de mensagens de WhatsApp antigas, conversas passadas com motoristas ou políticas da diretoria.
    """
    print(Fore.YELLOW + f"   ⚙️ [JARVIS USANDO FERRAMENTA] Buscando memórias e regras sobre: '{assunto}'...")
    
    # Busca nas duas gavetas
    res_regras = colecao_regras.query(query_texts=[assunto], n_results=2)
    res_whats = colecao_whatsapp.query(query_texts=[assunto], n_results=3)
    
    resposta_formatada = "Resultados encontrados no Cérebro da Empresa:\n"
    encontrou_algo = False
    
    docs_regras = res_regras.get('documents', [[]])[0]
    if docs_regras:
        encontrou_algo = True
        resposta_formatada += "\n--- REGRAS E POLÍTICAS DA EMPRESA ---\n"
        for doc in docs_regras: resposta_formatada += f"- {doc}\n"
            
    docs_whats = res_whats.get('documents', [[]])[0]
    if docs_whats:
        encontrou_algo = True
        resposta_formatada += "\n--- HISTÓRICO DE WHATSAPP ANTIGO ---\n"
        for doc in docs_whats: resposta_formatada += f"- {doc}\n"
        
    if not encontrou_algo:
        return "Nenhuma informação ou regra encontrada na memória sobre isso."
        
    return resposta_formatada

def gerar_proposta_comercial(cliente: str, origem: str, destino: str, valor: float) -> str:
    """
    Usa esta ferramenta para criar um PDF de Proposta Comercial/Orçamento.
    """
    global ARQUIVOS_PARA_ENVIAR
    print(Fore.CYAN + f"   ⚙️ [JARVIS USANDO FERRAMENTA] Gerando PDF de Proposta para {cliente}...")
    
    caminho_template = os.path.join(BASE_DIR, "TEMPLATE_PROPOSTA.docx")
    nome_arquivo_base = f"PROPOSTA_{cliente.replace(' ', '_')}_{int(datetime.now().timestamp())}"
    caminho_docx = os.path.join(BASE_DIR, f"{nome_arquivo_base}.docx")
    caminho_pdf = os.path.join(BASE_DIR, f"{nome_arquivo_base}.pdf")
    
    try:
        doc = Document(caminho_template)
        for paragrafo in doc.paragraphs:
            if '[CLIENTE_CNPJ]' in paragrafo.text: paragrafo.text = paragrafo.text.replace('[CLIENTE_CNPJ]', cliente)
            if '[ORIGEM]' in paragrafo.text: paragrafo.text = paragrafo.text.replace('[ORIGEM]', origem)
            if '[DESTINO]' in paragrafo.text: paragrafo.text = paragrafo.text.replace('[DESTINO]', destino)
            if '[VALOR]' in paragrafo.text: paragrafo.text = paragrafo.text.replace('[VALOR]', f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            if '[DATA]' in paragrafo.text: paragrafo.text = paragrafo.text.replace('[DATA]', datetime.now().strftime("%d/%m/%Y"))
            
        doc.save(caminho_docx)
        convert(caminho_docx, caminho_pdf)
        
        if os.path.exists(caminho_docx): os.remove(caminho_docx)
        
        ARQUIVOS_PARA_ENVIAR.append(caminho_pdf)
        return f"SUCESSO: O PDF foi gerado e enviado para a fila de upload do WhatsApp. Avise ao usuário que a proposta está a ser enviada."
        
    except Exception as e:
        return f"FALHA: Ocorreu um erro ao gerar o documento no Word: {str(e)}"

# =====================================================================
# 3. GERENCIADOR DA I.A. (SESSÕES E ROTAÇÃO)
# =====================================================================

_cliente_atual = None
_chat_atual = None
_indice_chave = 0

configuracao_jarvis = types.GenerateContentConfig(
    system_instruction=(
        "És o Jarvis, a Inteligência Artificial Executiva da Norte Nordeste Logística. "
        "Tens acesso a ferramentas. Analisa o pedido e usa as ferramentas se for necessário. "
        "Sê direto, profissional e educado. Não uses blocos gigantes de texto."
    ),
    tools=[buscar_regras_e_historico, gerar_proposta_comercial],
    temperature=0.0
)

def _conectar_sessao(idx, historico=None):
    cli = genai.Client(api_key=LISTA_CHAVES_GEMINI[idx])
    if historico:
        c = cli.chats.create(model="gemini-2.5-flash", config=configuracao_jarvis, history=historico)
    else:
        c = cli.chats.create(model="gemini-2.5-flash", config=configuracao_jarvis)
    return cli, c

def inicializar_motor():
    global _cliente_atual, _chat_atual, _indice_chave
    print(Fore.YELLOW + "🔄 Inicializando o Cérebro do Jarvis...")
    _cliente_atual, _chat_atual = _conectar_sessao(_indice_chave)
    print(Fore.GREEN + f"✅ Motor IA online (Chave {_indice_chave + 1}).")

def pensar_e_responder(mensagem_pacote):
    global _cliente_atual, _chat_atual, _indice_chave, ARQUIVOS_PARA_ENVIAR
    
    ARQUIVOS_PARA_ENVIAR = []
    if not _chat_atual:
        inicializar_motor()
        
    sucesso = False
    tentativas = 0
    resposta_texto = "Erro interno no sistema de IA."
    
    while not sucesso and tentativas < len(LISTA_CHAVES_GEMINI):
        try:
            resposta = _chat_atual.send_message(mensagem_pacote)
            resposta_texto = resposta.text
            sucesso = True
            
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                tentativas += 1
                if tentativas < len(LISTA_CHAVES_GEMINI):
                    _indice_chave = (_indice_chave + 1) % len(LISTA_CHAVES_GEMINI)
                    print(Fore.YELLOW + f"   🔄 Limite atingido. Rotacionando para Chave {_indice_chave + 1}...")
                    try: historico = _chat_atual.get_history()
                    except: historico = None
                    _cliente_atual, _chat_atual = _conectar_sessao(_indice_chave, historico)
                else:
                    resposta_texto = "Senhor, minhas chaves de processamento diárias esgotaram. Por favor, aguarde o reset do sistema."
                    break
            else:
                resposta_texto = f"Erro de comunicação: {str(e)}"
                break
                
    arquivos_gerados = ARQUIVOS_PARA_ENVIAR.copy()
    ARQUIVOS_PARA_ENVIAR.clear()
    
    # 🔥 A MÁGICA ACONTECE AQUI: Salva a conversa passivamente no Cérebro!
    try:
        linhas = mensagem_pacote.split('\n')
        remetente = "Usuário"
        pergunta_limpa = mensagem_pacote
        for linha in linhas:
            if "[MENSAGEM DE]:" in linha: remetente = linha.replace("[MENSAGEM DE]:", "").strip()
            if "[PEDIDO]:" in linha: pergunta_limpa = linha.replace("[PEDIDO]:", "").strip()
        
        salvar_memoria_conversa(remetente, pergunta_limpa, resposta_texto)
    except: pass
    
    return resposta_texto, arquivos_gerados