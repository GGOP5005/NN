import os
import time
import schedule
from datetime import datetime
from colorama import init, Fore, Style
from sheets_suape import buscar_containers_pendentes, buscar_containers_falta_passe, buscar_containers_passe_solicitado, atualizar_status_planilha, obter_aba_atual
from scraper_tecon import processar_lote_tecon, solicitar_passes_tecon, verificar_passes_aprovados

# Inicializa as cores no terminal
init(autoreset=True)

# ==========================================
# ⚙️ CONFIGURAÇÃO DOS HORÁRIOS DO ROBÔ
# ==========================================
HORARIOS_AGENDADOS = ["09:00", "12:00", "16:00", "20:00", "03:00"]

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

# ==========================================
# 🚀 MÓDULO DE INTEGRAÇÃO (PROJETO 1 -> PROJETO 2)
# ==========================================
def executar_ciclo_expresso(numero_container, linha_planilha=None, aba_planilha=None):
    if not numero_container or len(numero_container) < 11:
        return

    # CORREÇÃO BUG 6: aba dinâmica em vez de "MARÇO" hardcoded
    # Antes: aba_planilha="MARÇO" como padrão causava escrita no mês errado
    if aba_planilha is None:
        aba_planilha = obter_aba_atual()
        
    print(Fore.MAGENTA + "\n" + "="*70)
    print(Fore.WHITE + Style.BRIGHT + f"🚀 MISSÃO EXPRESSA TECON: {numero_container}")
    print(Fore.MAGENTA + "-"*70)
    print(Fore.WHITE + "🔍 Verificando presença no terminal...")
    
    resultados_fase1 = processar_lote_tecon([numero_container])
    status_fase1 = resultados_fase1.get(numero_container)
    
    if status_fase1 == "DISPONIVEL":
        print(Fore.GREEN + f"   🟢 O contêiner {numero_container} JÁ ESTÁ NO PORTO! Iniciando faturamento instantâneo...")
        if linha_planilha:
            atualizar_status_planilha(linha_planilha, "FALTA PASSE", aba_planilha)
            
        resultados_fase2 = solicitar_passes_tecon([numero_container])
        status_fase2 = resultados_fase2.get(numero_container)
        
        if status_fase2 == "SOLICITADO":
            print(Fore.GREEN + Style.BRIGHT + f"   ✅ [SUCESSO EXPRESSO] Faturamento concluído! Ele será verificado no ciclo de 45 minutos.")
            if linha_planilha:
                atualizar_status_planilha(linha_planilha, "PASSE SOLICITADO", aba_planilha)
        else:
            print(Fore.RED + f"   ❌ [ERRO EXPRESSO] Falha ou bloqueio ao tentar faturar {numero_container} agora.")
            
    else:
        # ---> ESCREVE NA PLANILHA SE NÃO CHEGOU (NO MODO EXPRESSO) <---
        print(Fore.YELLOW + f"   ⏳ [EXPRESSO] O contêiner {numero_container} ainda não chegou (Não Liberado). O relógio agendado cuidará dele mais tarde.")
        if linha_planilha:
            atualizar_status_planilha(linha_planilha, "NÃO LIBERADO", aba_planilha)

    print(Fore.MAGENTA + "="*70 + "\n")

# ==========================================
# 🧭 MÓDULO DE 45 MINUTOS (SÓ VERIFICA PASSES)
# ==========================================
def rotina_monitoramento_passes():
    print(Fore.MAGENTA + "\n" + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + f" 🧭 CICLO 45 MIN: VERIFICAÇÃO DE PASSES ({datetime.now().strftime('%H:%M:%S')})")
    print(Fore.MAGENTA + "="*70)
    
    fila_aprovacao = buscar_containers_passe_solicitado()
    
    if fila_aprovacao:
        lista_monitoramento = [item["numero"] for item in fila_aprovacao]
        print(Fore.WHITE + f"   📋 Encontrados {len(lista_monitoramento)} contêiner(es) aguardando aprovação do Tecon.")
        
        resultados_fase3 = verificar_passes_aprovados(lista_monitoramento)
        
        for item in fila_aprovacao:
            numero = item["numero"]
            status_retornado = resultados_fase3.get(numero)
            
            if status_retornado:
                if "VENCE" in status_retornado:
                    print(Fore.MAGENTA + f"   🎯 {numero}: {status_retornado}")
                elif status_retornado in ["EM ANÁLISE", "EM_ANALISE"]:
                    print(Fore.YELLOW + f"   ⏳ {numero}: EM ANÁLISE (Mantendo como PASSE SOLICITADO na planilha)")
                elif status_retornado in ["NÃO ENCONTRADO", "ERRO NA VERIFICAÇÃO"]:
                    print(Fore.RED + f"   ❌ {numero}: {status_retornado}")
                else:
                    print(Fore.GREEN + f"   ✅ {numero}: {status_retornado}")
            
            # ATENÇÃO: Nunca escreve "EM ANÁLISE" na planilha! Fica intacto até ter o passe final.
            if status_retornado and status_retornado not in ["EM ANÁLISE", "EM_ANALISE", "ERRO NA VERIFICAÇÃO", "NÃO ENCONTRADO"]:
                # CORREÇÃO BUG 6: usa item.get("aba") que já vem dinâmico do sheets_suape
                atualizar_status_planilha(item["linha"], status_retornado, item.get("aba", obter_aba_atual()))
                time.sleep(1)
    else:
        print(Fore.WHITE + "   ☕ Nenhum contêiner aguardando aprovação de passe neste momento.")
        
    print(Fore.MAGENTA + "-"*70 + "\n")

# ==========================================
# 🔄 MÓDULO PADRÃO (VARREDURA PESADA)
# ==========================================
def executar_ciclo_completo():
    print(Fore.BLUE + "\n" + "="*70)
    print(Fore.YELLOW + Style.BRIGHT + f" 🔄 INICIANDO CICLO DE VARREDURA PESADA ({datetime.now().strftime('%H:%M:%S')})")
    print(Fore.BLUE + "="*70)
    
    # CORREÇÃO BUG 6: aba calculada uma vez por ciclo (dinâmica)
    aba_ciclo = obter_aba_atual()
    
    print(Fore.WHITE + Style.BRIGHT + "\n🛳️  FASE 1: RASTREIO DE CHEGADAS")
    fila_pendentes = buscar_containers_pendentes()
    
    if fila_pendentes:
        lista_numeros = [item["numero"] for item in fila_pendentes]
        resultados = processar_lote_tecon(lista_numeros)
        
        for item in fila_pendentes:
            status = resultados.get(item["numero"])
            # CORREÇÃO BUG 6: item.get("aba") já é dinâmico; fallback usa aba_ciclo
            aba_item = item.get("aba", aba_ciclo)
            if status == "DISPONIVEL":
                print(Fore.GREEN + f"   ✅ {item['numero']}: DISPONÍVEL (Chegou ao porto!)")
                atualizar_status_planilha(item["linha"], "FALTA PASSE", aba_item)
                time.sleep(1)
            else:
                print(Fore.YELLOW + f"   ⏳ {item['numero']}: NÃO LIBERADO (Ainda não disponível no sistema)")
                atualizar_status_planilha(item["linha"], "NÃO LIBERADO", aba_item)
                time.sleep(1)
    else:
        print(Fore.WHITE + "   ☕ Nenhum contêiner pendente de chegada na planilha.")

    print(Fore.WHITE + Style.BRIGHT + "\n📑 FASE 2: FATURAMENTO (SOLICITAÇÃO DE PASSES)")
    fila_faturamento = buscar_containers_falta_passe()
    
    if fila_faturamento:
        lista_passes = [item["numero"] for item in fila_faturamento]
        print(Fore.WHITE + f"   📋 Encontrados {len(lista_passes)} contêineres para faturar.")
        
        resultados_passes = solicitar_passes_tecon(lista_passes)
        
        for item in fila_faturamento:
            status = resultados_passes.get(item["numero"])
            aba_item = item.get("aba", aba_ciclo)
            if status == "SOLICITADO":
                print(Fore.GREEN + f"   ✅ {item['numero']}: FATURAMENTO SOLICITADO!")
                atualizar_status_planilha(item["linha"], "PASSE SOLICITADO", aba_item)
                time.sleep(1)
            elif status in ["SEM_ARQUIVOS", "AGUARDANDO_DOCS"]:
                print(Fore.YELLOW + f"   ⚠️ {item['numero']}: {status} (Aguardando PDFs no Dropbox).")
            else:
                print(Fore.RED + f"   ❌ {item['numero']}: {status}")
    else:
        print(Fore.WHITE + "   ☕ Nenhum contêiner aguardando solicitação de passe.")
        
    print(Fore.BLUE + "-"*70)
    print(Fore.GREEN + f"🏁 Varredura Pesada finalizada com sucesso.\n")
    
    # Após a varredura pesada, ele executa a Fase 3 automaticamente
    rotina_monitoramento_passes()

if __name__ == "__main__":
    limpar_tela()
    print(Fore.BLUE + Style.BRIGHT + "======================================================================")
    print(Fore.BLUE + Style.BRIGHT + "                ROBÔ TECON SUAPE - MONITORAMENTO 24/7")
    print(Fore.BLUE + Style.BRIGHT + "======================================================================\n")
    print(Fore.GREEN + f"⏰ Relógio Mestre (Chegadas/Faturar): {', '.join(HORARIOS_AGENDADOS)}")
    print(Fore.MAGENTA + f"⏱️ Relógio Secundário (Monitorar Passes): A cada 45 minutos")
    print(Fore.WHITE + "⚡ Modo Expresso: ATIVO (Aguardando chamados do Robô 1).")
    print(Fore.WHITE + "💤 O sistema está em modo de escuta. Pode minimizar esta janela.\n")
    
    ultimo_minuto_rodado = None

    # Agenda a rotina de passes a cada 45 minutos!
    schedule.every(45).minutes.do(rotina_monitoramento_passes)

    while True:
        agora = datetime.now().strftime("%H:%M")
        
        # Disparo dos Horários Mestres
        if agora in HORARIOS_AGENDADOS and agora != ultimo_minuto_rodado:
            print(Fore.YELLOW + Style.BRIGHT + f"\n⏰ O relógio bateu {agora}! Acordando o robô para Varredura Pesada...")
            try:
                executar_ciclo_completo()
            except Exception as e:
                print(Fore.RED + f"\n🚨 Erro crítico na execução do ciclo: {e}")
            ultimo_minuto_rodado = agora
            print(Fore.WHITE + f"💤 Robô voltou a dormir no relógio principal.")
            
        # O schedule.run_pending() cuida do loop de 45 minutos automaticamente no fundo
        schedule.run_pending()
        time.sleep(30)
