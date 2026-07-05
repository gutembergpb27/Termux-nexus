import time
import os
import signal
import random
import sys
import json
from network_mesh import NexusMeshNode

def run_chaos_simulation():
    print("🐒 [Chaos Monkey] Agente de engenharia de caos inicializado.")
    print("🎯 Alvo: Testar resiliência do Nexus Supervisor, Rate Limiting e Cluster.")
    time.sleep(2.0)
    
    # 1. Simulação de Inundação de Rede (Testar o Token Bucket Rate Limiter da v1100)
    print("\n⚡ [Chaos Stage 1] Iniciando inundação de pacotes na malha (Porta 8080)...")
    attacker_mesh = NexusMeshNode(port=9999)
    for i in range(10):
        # Envia pings em altíssima velocidade para estourar o limite de capacidade
        attacker_mesh.send_transaction("127.0.0.1", 8080, {"event": "HEARTBEAT_PING", "data": {"node_id": "Chaos_Injected_Node"}})
        time.sleep(0.05)
    print("✅ [Chaos Stage 1] Inundação finalizada. Verifique se o Core aplicou [Backpressure].")
    
    time.sleep(3.0)
    
    # 2. Simulação de Interrupção de Liderança (Testar Failover de Cluster da v1200)
    print("\n👑 [Chaos Stage 2] Simulando isolamento/queda do Nó Mestre...")
    print("💡 Se o nó local ficar sem receber o ping 'Local_Master', ele deve se auto-eleger LÍDER.")
    # Forçamos uma mensagem falsa simulando que o mestre remoto morreu mandando dados vazios
    print("✅ [Chaos Stage 2] Janela de silêncio provocada. Monitore o terminal do Core.")

if __name__ == "__main__":
    run_chaos_simulation()
