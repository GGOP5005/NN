"""
bsoft_codigo_gerencial_api.py
==============================
Robô de Troca de Código Gerencial em Títulos a Receber.
Migrado de Playwright → API REST Bsoft TMS.

Fluxo:
  1. GET /financeiro/v1/titulosReceber   → busca todos os títulos
  2. Filtra localmente os que têm cod_gerencial com "08.002"
  3. Para cada título:
     a. Verifica memória local (bsoft_memoria_clientes.json)
     b. Fuzzy matching no plano de contas gerencial (cache local)
     c. PUT /financeiro/v1/titulosReceber → atualiza gerencias
"""

import os
import re
import json
import unicodedata
from colorama import init, Fore, Style

try:
    from rapidfuzz import fuzz, process as fuzz_process
    RAPIDFUZZ_OK = True
except ImportError:
    RAPIDFUZZ_OK = False

from api_bsoft import BsoftAPI

init(autoreset=True)

# =============================================================
# CONFIGURAÇÕES
# =============================================================
CODIGO_ALVO     = "08.002"
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "bsoft_memoria_clientes.json")

# =============================================================
# MEMÓRIA
# =============================================================

def carregar_memoria() -> dict:
    try:
        if os.path.exists(ARQUIVO_MEMORIA):
            with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def salvar_memoria(memoria: dict):
    try:
        with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(memoria, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.YELLOW + f"   ⚠️ Erro ao salvar memória: {e}")

def chave_cliente(nome: str) -> str:
    return remover_acentos(str(nome)).strip().upper()

# =============================================================
# UTILITÁRIOS
# =============================================================

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    ).upper().strip()

def gerar_termos_busca(nome_completo: str) -> list:
    GENERICAS = {
        "MADEIRAS","MADEIRA","COMERCIO","INDUSTRIA","TRANSPORTES","TRANSPORTE",
        "SERVICOS","SERVICO","MATERIAIS","MATERIAL","CONSTRUCAO","CONSTRUCOES",
        "DISTRIBUICAO","DISTRIBUIDORA","BRASIL","NORTE","NORDESTE","SUL",
        "LESTE","OESTE","SOLUCOES","SOLUCAO","SISTEMAS","GRUPO","CENTER","CENTRO",
    }
    nome = remover_acentos(nome_completo)
    nome_limpo = re.sub(
        r"\b(LTDA|S/?A|EIRELI|ME|EPP|CIA|DE|E|DO|DA|DOS|DAS|DISTRIBUIDORA|PAINEIS|COMPENSADOS)\b",
        "", nome
    ).strip()
    palavras = [p for p in nome_limpo.split() if len(p) >= 2]

    def eh_especifica(p):
        if p.upper() in GENERICAS:
            return False
        if len(p) < 3:
            return bool(re.search(r"\d", p)) or (len(p) == 2 and p.isupper())
        return True

    esp = sorted([p for p in palavras if eh_especifica(p)], key=len, reverse=True)
    gen = sorted([p for p in palavras if not eh_especifica(p)], key=len, reverse=True)

    termos = list(esp)
    for i in range(len(esp) - 1):
        termos.append(f"{esp[i]} {esp[i+1]}")
    if esp and gen:
        termos.append(f"{esp[0]} {gen[0]}")
    termos.extend(gen)

    vistos, resultado = set(), []
    for t in termos:
        n = t.strip().upper()
        if n and n not in vistos:
            vistos.add(n)
            resultado.append(t)
    return resultado[:10]

# =============================================================
# FILTRAR TÍTULOS COM CÓDIGO ALVO
# =============================================================

def filtrar_titulos_alvo(titulos: list) -> list:
    """Filtra client-side os títulos que possuem 08.002 na descrição das gerencias."""
    resultado = []
    for t in titulos:
        for g in t.get("gerencias", []):
            if CODIGO_ALVO in g.get("descricao", ""):
                resultado.append(t)
                break
    return resultado

# =============================================================
# BUSCAR NO PLANO DE CONTAS
# =============================================================

def buscar_no_plano(nome_cliente: str, plano: list) -> tuple:
    """
    Retorna (cod_gerencial, descricao) ou (None, "") se não encontrar.
    Procura entradas com 'RECEITA' + nome do cliente via fuzzy.
    """
    opcoes = [p for p in plano if "RECEITA" in remover_acentos(p.get("descricao", "")) and p.get("codGerencial")]
    if not opcoes:
        return None, ""

    descricoes = [remover_acentos(p["descricao"]) for p in opcoes]
    termos     = gerar_termos_busca(nome_cliente)

    melhor_score, melhor_idx = 0, -1
    for termo in termos:
        if not RAPIDFUZZ_OK:
            break
        resultados = fuzz_process.extract(remover_acentos(termo), descricoes, scorer=fuzz.partial_ratio, limit=3)
        for _, score, idx in resultados:
            if score > melhor_score:
                melhor_score, melhor_idx = score, idx

    if melhor_idx >= 0 and melhor_score >= 60:
        p = opcoes[melhor_idx]
        return p["codGerencial"], p["descricao"]

    return None, ""

# =============================================================
# CONFIRMAR COM USUÁRIO
# =============================================================

def confirmar_com_usuario(nome_cliente: str, candidatos: list) -> tuple:
    """Pausa para o utilizador escolher quando há ambiguidade. Retorna (cod, desc)."""
    print(Fore.YELLOW + Style.BRIGHT + f"\n      ⚠️  AMBIGUIDADE para '{nome_cliente}'")
    for i, (cod, desc) in enumerate(candidatos):
        print(Fore.WHITE + f"      [{i+1}] {desc}")
    print(Fore.WHITE + "      [0] Pular")
    while True:
        try:
            escolha = int(input(Fore.CYAN + f"      👉 Escolha (0-{len(candidatos)}): ").strip())
            if escolha == 0:
                return None, ""
            if 1 <= escolha <= len(candidatos):
                cod, desc = candidatos[escolha - 1]
                print(Fore.GREEN + f"      ✅ Escolhido: {desc}")
                return cod, desc
        except (ValueError, KeyboardInterrupt):
            pass

# =============================================================
# MONTAR BODY PUT
# =============================================================

def montar_body_put(titulo: dict, novo_cod: str) -> dict:
    """Preserva todos os dados do título, substituindo apenas as gerencias."""
    db = titulo.get("dados_basicos", {})

    body = {
        "codFatura":   db["codFatura"],
        "cod_cliente": db["cod_cliente"],
        "empresa_id":  db["empresaId"],
        "tipo":        db["tipo"],
        "numero":      db.get("numero", ""),
        "data_emissao": db["data_emissao"],
        "data_entrada": db["data_entrada"],
        "valor":        db["valor"],
        "previsao":     db.get("previsao", "N"),
        "historico":    db.get("historico", ""),
        "observacoes":  db.get("observacao", ""),
        "referencia":   db.get("referencia", ""),
        "acrescimos":   db.get("acrescimos", "0"),
        "abatimentos":  db.get("abatimentos", "0"),
        "gerencias": [
            {"grupo": "1", "codigo": novo_cod, "percentual": "100"}
        ],
    }

    rateios = [
        {"grupo": r["grupo"], "codigo": r["cod_rateio"], "percentual": r["percentual"]}
        for r in titulo.get("rateios", [])
    ]
    if rateios:
        body["rateios"] = rateios

    duplicatas = [
        {"data_vencimento": d["data_vencimento"], "valor": d["valor"]}
        for d in titulo.get("duplicatas", [])
    ]
    if duplicatas:
        body["duplicatas"] = duplicatas

    return body

# =============================================================
# LOOP PRINCIPAL
# =============================================================

def executar_troca_codigos():
    print(Fore.BLUE + Style.BRIGHT + "=" * 65)
    print(Fore.BLUE + Style.BRIGHT + "   ROBÔ BSOFT — TROCA CÓDIGO GERENCIAL (API REST)")
    print(Fore.BLUE + Style.BRIGHT + f"   Alvo: '{CODIGO_ALVO}' → Receita [Cliente]")
    print(Fore.BLUE + Style.BRIGHT + "=" * 65 + "\n")

    api       = BsoftAPI()
    memoria   = carregar_memoria()
    relatorio = []

    print(Fore.CYAN + f"💾 Memória: {len(memoria)} cliente(s) já mapeados.")

    # 1. Carrega plano de contas (cache local — evita N chamadas)
    print(Fore.WHITE + "\n🔍 Carregando Plano de Contas Gerencial...")
    plano = api.get("financeiro/v1/planoDeContasGerencial", paginar=False)
    plano = plano if isinstance(plano, list) else []
    print(Fore.CYAN + f"   📋 {len(plano)} entradas carregadas.")

    # 2. Busca todos os títulos a receber com paginação automática
    print(Fore.WHITE + "\n📥 Buscando Títulos a Receber...")
    todos = api.get("financeiro/v1/titulosReceber")
    if not todos:
        print(Fore.YELLOW + "⚠️ Nenhum título retornado.")
        return

    # 3. Filtra localmente pelo código gerencial alvo
    titulos = filtrar_titulos_alvo(todos)
    if not titulos:
        print(Fore.WHITE + f"\n☕ Nenhum título com código gerencial '{CODIGO_ALVO}'.")
        return

    print(Fore.YELLOW + f"\n🎯 {len(titulos)} título(s) para processar.\n")
    print(Fore.CYAN + "-" * 65)

    # 4. Processa cada título
    for idx, titulo in enumerate(titulos):
        db           = titulo.get("dados_basicos", {})
        cod_fatura   = db.get("codFatura", "?")
        nome_cliente = db.get("cliente", "").strip()

        print(Fore.YELLOW + f"\n[{idx+1}/{len(titulos)}] Título #{cod_fatura} — {nome_cliente}")

        chave = chave_cliente(nome_cliente)

        # Prioridade 1: memória
        if chave in memoria:
            novo_cod = memoria[chave]
            print(Fore.GREEN + f"   💾 Memória: cod_gerencial={novo_cod}")

        else:
            # Prioridade 2: fuzzy no plano de contas local
            novo_cod, desc = buscar_no_plano(nome_cliente, plano)

            if not novo_cod:
                print(Fore.RED + f"   ❌ Não encontrado para '{nome_cliente}'. Pulando.")
                relatorio.append({"cod": cod_fatura, "cliente": nome_cliente, "status": "NÃO ENCONTRADO"})
                continue

            print(Fore.CYAN + f"   🎯 Fuzzy: {novo_cod} — {desc}")
            memoria[chave] = novo_cod
            salvar_memoria(memoria)

        # 5. PUT com body completo
        body     = montar_body_put(titulo, novo_cod)
        resultado = api.put("financeiro/v1/titulosReceber", body)

        if resultado is not None:
            print(Fore.GREEN + f"   ✅ Atualizado → cod_gerencial={novo_cod}")
            relatorio.append({"cod": cod_fatura, "cliente": nome_cliente, "status": "OK", "cod": novo_cod})
        else:
            print(Fore.RED + f"   ❌ Falha PUT #{cod_fatura}.")
            relatorio.append({"cod": cod_fatura, "cliente": nome_cliente, "status": "ERRO PUT"})

    # Relatório
    ok      = [r for r in relatorio if r["status"] == "OK"]
    erros   = [r for r in relatorio if r["status"] == "ERRO PUT"]
    nao_enc = [r for r in relatorio if r["status"] == "NÃO ENCONTRADO"]

    print(Fore.BLUE + "\n" + "=" * 65)
    print(Fore.YELLOW + Style.BRIGHT + " 📊 RELATÓRIO FINAL")
    print(Fore.BLUE + "=" * 65)
    print(Fore.GREEN  + f"  ✅ Alterados      : {len(ok)}")
    print(Fore.RED    + f"  ❌ Erros          : {len(erros)}")
    print(Fore.YELLOW + f"  🔍 Não encontrados: {len(nao_enc)}")
    if nao_enc:
        print(Fore.YELLOW + "\n  Clientes sem código no plano:")
        for r in nao_enc:
            print(Fore.YELLOW + f"    #{r['cod']} — {r['cliente']}")
    print(Fore.BLUE + "=" * 65)


if __name__ == "__main__":
    executar_troca_codigos()