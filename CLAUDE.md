# IA Logística Sheets - Sistema de Automação Portuária

## Visão Geral

Sistema de automação para processamento de documentos fiscais brasileiros (NF-e, CT-e), monitoramento de contêineres em portos, e integração com WhatsApp para comunicação automatizada.

### Fluxo Principal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUXO PRINCIPAL                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   PASTAS     │───▶│   PROCESSOR  │───▶│  EXTRATOR IA │───▶│  SHEETS  │  │
│  │  (Watchdog)  │    │   (core/)    │    │ (documents/) │    │ (sheets/)│  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘  │
│         │                   │                   │                   │        │
│         ▼                   ▼                   ▼                   ▼        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐   │
│  │ PDFs/XMLs    │    │ Validação    │    │ Gemini 2.5   │    │ Google   │   │
│  │ NFS-e/CT-e   │    │ Erros        │    │ Flash        │    │ Sheets   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Pastas (Organização por Domínio)

```
C:\ia_logistica_sheets\
│
├── 📁 config.py                 # Configurações centralizadas
├── 📁 main.py                   # Ponto de entrada principal (Watchdog)
│
├── 📁 portos/                   # Monitoramento de portos
│   ├── __init__.py
│   ├── scraper_tecon.py         # Scraper Tecon Suape
│   ├── scraper_salvador.py      # Scraper Porto Salvador
│   ├── scraper_pecem.py         # Scraper Porto Pecém
│   ├── monitor_navios.py        # Monitor de navios
│   ├── monitor_manaus.py        # Monitor Manaus
│   └── main_monitor.py          # Loop principal de monitoramento
│
├── 📁 documents/                # Extração de documentos
│   ├── __init__.py
│   ├── extrator_pdf.py          # Extração de texto de PDFs
│   ├── extrator_xml.py          # Extração de dados de XML (NF-e/CT-e)
│   ├── extrator_ia.py           # Extração com Gemini AI
│   └── EXTRATOR_EXCEL.py        # Extração de planilhas Excel
│
├── 📁 sheets/                   # Integração Google Sheets
│   ├── __init__.py
│   ├── sheets_api.py             # API principal do Google Sheets
│   └── sheets_suape.py           # Funções específicas Suape
│
├── 📁 core/                     # Núcleo do sistema
│   ├── __init__.py
│   ├── processor.py             # Processador principal de arquivos
│   ├── memoria.py               # Sistema de memória (ChromaDB)
│   ├── logger.py                # Sistema de logs coloridos
│   ├── ensinar_regras.py        # Ensino de regras para IA
│   └── organizador_meses.py     # Organização por meses
│
├── 📁 api/                      # Integrações externas
│   ├── __init__.py
│   ├── buscador_pdfs.py         # Buscador de PDFs no Dropbox
│   ├── bsoft_codigo_gerencial.py # Robô Bsoft TMS (códigos)
│   └── robo_bsoft_pagar.py      # Robô Bsoft TMS (títulos)
│
├── 📁 whatsapp/                 # Automação WhatsApp
│   ├── __init__.py
│   ├── motor_ia.py               # Motor de IA (Gemini + ChromaDB)
│   ├── despachante_whatsapp.py  # Bot despachante
│   ├── login_whatsapp.py        # Login manual WhatsApp
│   └── notificador_frota.py     # Notificador de frota
│
├── 📁 utils/                    # Utilitários
│   └── __init__.py
│
├── 📁 archives/                 # Arquivos antigos/arquivados
├── 📁 JARVIS_CEREBRO/           # Banco vetorial ChromaDB
├── 📁 WA_Session/               # Sessão WhatsApp
├── 📁 sessao_whatsapp/          # Cache de sessão
├── 📁 Bsoft_Session/            # Sessão Bsoft
├── 📁 logs/                     # Logs do sistema
├── 📁 erros/                    # Arquivos com erro
├── 📁 processados/              # Arquivos processados
│
├── 📄 .env                      # Variáveis de ambiente
├── 📄 credentials.json          # Credenciais Google API
├── 📄 requirements.txt          # Dependências Python
└── 📄 CLAUDE.md                 # Este arquivo

```

---

## Módulos Principais

### 1. Configuração (`config.py`)

```python
# Variáveis de ambiente
GEMINI_API_KEY          # Chave da API Gemini
SPREADSHEET_ID          # ID da planilha principal
DROPBOX_DIR             # Pasta do Dropbox

# Roteamento por porto
ROTEAMENTO_PORTOS = {
    "C:/caminho/entrada_suape": "ID_PLANILHA_SUAPE",
    "C:/caminho/entrada_salvador": "ID_PLANILHA_SALVADOR",
    "C:/caminho/entrada_pecem": "ID_PLANILHA_PECEM",
}

# Credenciais
TECON_CPF, TECON_SENHA  # Login Tecon
CNPJ_TRANSPORTADORA     # CNPJ da transportadora
HEADLESS = True         # Modo headless Playwright
```

---

### 2. Core - Processor (`core/processor.py`)

```python
def processar_arquivo(caminho_arquivo, spreadsheet_id):
    """
    Função principal de processamento.

    Fluxo:
    1. Detecta extensão (PDF/XML/Excel)
    2. Extrai texto bruto
    3. Envia para IA extrair dados estruturados
    4. Valida campos obrigatórios
    5. Envia para Google Sheets

    Returns:
        (sucesso: bool, dados: list[dict])
    """
```

---

### 3. Documents - Extratores

#### `documents/extrator_pdf.py`
```python
def extrair_texto_pdf(path):
    """Extrai texto de PDFs usando PyMuPDF (fitz)"""
    # Usa pytesseract como fallback para PDFs scaneados
```

#### `documents/extrator_xml.py`
```python
def extrair_texto_xml(path):
    """
    Extrai dados de XML fiscal brasileiro.
    Detecta automaticamente: NF-e (55) ou CT-e (57)
    pela chave de acesso (posição 20-22).

    Namespaces:
    - http://www.portalfiscal.inf.br/nfe
    - http://www.portalfiscal.inf.br/cte
    """
```

#### `documents/extrator_ia.py`
```python
def extrair_com_ia(texto):
    """
    Usa Gemini 2.5 Flash para extrair dados estruturados.

    Campos extraídos:
    - conteiner, nf, data, valor_total, peso
    - cliente, cidade_origem, cidade_destino
    - motorista, placa, telefone
    """
```

---

### 4. Sheets - Google Sheets API (`sheets/sheets_api.py`)

```python
def adicionar_ou_mesclar_linha(spreadsheet_id, aba_nome, dados):
    """
    Adiciona ou mescla linha na planilha.

    Lógica:
    1. Busca linha existente pelo número do contêiner
    2. Se existe: mescla dados (atualiza)
    3. Se não existe: adiciona nova linha
    """

def buscar_container_por_nf(nf_numero):
    """Busca contêiner pelo número da NF no cache local"""

def executar_com_resiliencia_infinita(funcao, *args, **kwargs):
    """
    Executa função com retry infinito.
    Útil para operações que podem falhar por rate limit.
    """
```

---

### 5. Portos - Scrapers

#### `portos/scraper_tecon.py` (Tecon Suape)
```python
def processar_lote_tecon():
    """
    Processa contêineres no sistema Tecon.

    Fluxo:
    1. Login com CPF/Senha
    2. Acessa lista de contêineres
    3. Para cada contêiner:
       - Busca PDFs no Dropbox
       - Extrai dados do PDF
       - Preenche formulário
    4. Solicita passes
    """

def solicitar_passes_tecon():
    """Solicita passes para contêineres pendentes"""

def verificar_passes_aprovados():
    """Verifica status dos passes solicitados"""
```

#### `portos/scraper_salvador.py` (Porto Salvador)
```python
def processar_lote_salvador():
    """
    Processa contêineres no sistema do Porto Salvador.
    Similar ao Tecon, mas com login diferente.
    """
```

#### `portos/scraper_pecem.py` (Porto Pecém)
```python
def processar_lote_pecem():
    """Processa contêineres no sistema do Porto Pecém"""
```

---

### 6. WhatsApp - Motor IA (`whatsapp/motor_ia.py`)

```python
class MotorIA:
    def __init__(self):
        self.cliente_chroma = chromadb.PersistentClient(path="JARVIS_CEREBRO")
        self.modelo = genai.GenerativeModel('gemini-2.5-flash')

    def pensar_e_responder(self, mensagem):
        """
        Processa mensagem do WhatsApp com IA.

        Fluxo:
        1. Busca contexto no ChromaDB
        2. Constrói prompt com histórico
        3. Envia para Gemini
        4. Salva resposta no histórico
        5. Retorna resposta formatada
        """
```

---

### 7. API - Buscador PDFs (`api/buscador_pdfs.py`)

```python
def encontrar_pasta_container(numero_container):
    """
    Busca pasta do contêiner no Dropbox.

    Padrões de busca:
    - {CONTAINER}
    - {CONTAINER}_*
    - *_{CONTAINER}
    """

def classificar_e_extrair_pdfs(pasta):
    """
    Classifica PDFs encontrados por tipo:
    - NF-e
    - CT-e
    - Romaneio
    - Recibo
    """
```

---

## Dependências (`requirements.txt`)

```txt
# Web Scraping
playwright>=1.40.0
selenium>=4.15.0

# Google APIs
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=1.1.0
google-generativeai>=0.3.0

# AI & ML
chromadb>=0.4.0
pytesseract>=0.3.10

# PDF Processing
PyMuPDF>=1.23.0
pdfplumber>=0.10.0

# Utilities
colorama>=0.4.6
rich>=13.7.0
python-dotenv>=1.0.0
watchdog>=3.0.0

# Windows Automation
pywin32>=306

# Document Processing
python-docx>=0.8.11
docx2pdf>=0.1.8
openpyxl>=3.1.2
pandas>=2.1.0

# Audio Processing
SpeechRecognition>=3.10.0
pydub>=0.25.1
```

---

## Configuração de Ambiente

### 1. Variáveis de Ambiente (`.env`)

```env
GEMINI_API_KEY=sua_chave_gemini
SPREADSHEET_ID=id_da_planilha_principal
DROPBOX_DIR=C:/caminho/dropbox
HEADLESS=True
```

### 2. Credenciais Google (`credentials.json`)

Arquivo JSON com credenciais de serviço do Google Cloud:
- Projeto: nortenordeste-sheets
- Scopes: spreadsheets, drive

---

## Padrões e Convenções

### Nomenclatura

- **Arquivos**: `snake_case.py` (ex: `scraper_tecon.py`)
- **Funções**: `snake_case` (ex: `processar_arquivo`)
- **Classes**: `PascalCase` (ex: `MotorIA`)
- **Constantes**: `UPPER_SNAKE_CASE` (ex: `ROTEAMENTO_PORTOS`)

### Logs Coloridos

```python
from colorama import Fore, Style

print(Fore.GREEN + "✅ Sucesso: Operação concluída")
print(Fore.RED + "❌ Erro: Falha na operação")
print(Fore.YELLOW + "⚠️ Aviso: Verificar situação")
print(Fore.CYAN + "ℹ️ Info: Informação adicional")
```

### Emojis nos Logs

- ✅ Sucesso
- ❌ Erro
- ⚠️ Aviso
- 🔍 Busca
- 📤 Upload
- 📥 Download
- 🚀 Início
- 🎯 Objetivo
- ⏳ Aguardando
- ✨ Processamento IA

---

## Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUXO DE PROCESSAMENTO                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. MONITORAMENTO (main.py)                                                 │
│     └── Watchdog monitora pastas de entrada                                 │
│                                                                             │
│  2. DETECÇÃO                                                                 │
│     └── Novo arquivo detectado → Dispara processar_arquivo()               │
│                                                                             │
│  3. EXTRAÇÃO                                                                │
│     └── PDF → extrator_pdf.py → Texto bruto                                 │
│     └── XML → extrator_xml.py → Dados estruturados                          │
│     └── Excel → EXTRATOR_EXCEL.py → Dados tabulares                         │
│                                                                             │
│  4. IA PROCESSAMENTO                                                        │
│     └── Texto → extrator_ia.py → Gemini 2.5 Flash                           │
│     └── Prompt: "Extraia dados do documento fiscal..."                      │
│     └── Retorno: JSON com campos estruturados                               │
│                                                                             │
│  5. VALIDAÇÃO                                                               │
│     └── Verifica campos obrigatórios                                        │
│     └── Se erro → move para pasta de erros                                  │
│                                                                             │
│  6. INTEGRAÇÃO                                                              │
│     └── sheets_api.py → Google Sheets API                                   │
│     └── Adiciona ou mescla linha na planilha                                │
│                                                                             │
│  7. MONITORAMENTO PORTOS                                                    │
│     └── main_monitor.py → Loop periódico                                    │
│     └── Verifica contêineres pendentes                                      │
│     └── Solicita passes, atualiza status                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Comandos Úteis

### Instalação

```bash
# Instalar dependências
pip install -r requirements.txt

# Instalar navegadores Playwright
playwright install chromium

# Instalar Tesseract (Windows)
# Baixar de: https://github.com/UB-Mannheim/tesseract/wiki
```

### Execução

```bash
# Iniciar monitoramento principal
python main.py

# Iniciar monitoramento de portos
python -m portos.main_monitor

# Login manual WhatsApp
python -m whatsapp.login_whatsapp

# Executar robô Bsoft
python -m api.bsoft_codigo_gerencial
python -m api.robo_bsoft_pagar

# Organizador de meses
python -m core.organizador_meses
```

---

## Troubleshooting

### Erro: "Módulo não encontrado"

```bash
# Verificar se está no diretório correto
cd C:\ia_logistica_sheets

# Verificar PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Erro: "Credenciais Google"

1. Verificar se `credentials.json` existe
2. Verificar se o projeto Google Cloud está ativo
3. Verificar se as APIs estão habilitadas

### Erro: "Tesseract não encontrado"

```python
# Verificar caminho em extrator_pdf.py
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"
```

---

## Contatos e Referências

- **Projeto**: IA Logística Sheets
- **Empresa**: Norte Nordeste Transportes
- **CNPJ**: 46.099.394/0001-88
- **Planilha Principal**: Google Sheets ID em `config.py`

---

*Última atualização: 2026-03-24*