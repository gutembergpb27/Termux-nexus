import time
import random
from nexus_v500_core import NexusRuntime

def iniciar_simulacao():
    runtime = NexusRuntime()
    print("=========================================================")
    print("        NEXUS RUNTIME - LOOP DE CARGA DE ESTRESSE        ")
    print("=========================================================")
    print("⚡ Ingerindo fluxo contínuo a 125 Hz...")
    print("⚠️  Pressione CTRL+C a qualquer momento para simular falha/caos.")
    print("---------------------------------------------------------")
    
    contador = 0
    try:
        # Loop para gerar a massa de ~300k eventos
        while contador < 301521:
            contador += 1
            sinal_simulado = random.uniform(36.0, 37.5) # Ex: Sinal biomédico estável
            
            runtime.processar_evento(evento_id=contador, dados=sinal_simulado)
            
            # Controla a taxa aproximada de 125 Hz (1 / 125 = 0.008s)
            time.sleep(0.008)
            
            if contador % 25000 == 0:
                print(f"│ [PROCESSADO] {contador} eventos injetados em memória com sucesso.")
                
        print("\n✅ Carga nominal de estresse concluída com sucesso.")
        
    except KeyboardInterrupt:
        print("\n🛑 [CAOS ENGENHARIA] Processo interrompido via sinal simulado (SIGKILL/kill -9).")
        print("💡 O estado volátil foi encerrado. Rode 'analisar_stress.py' para auditar a integridade.")

if __name__ == "__main__":
    iniciar_simulacao()
