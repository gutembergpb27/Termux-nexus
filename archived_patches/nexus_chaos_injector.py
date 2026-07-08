import socket
import time
import json
import random

def simulate_unstable_network_send(target_ip, target_port, payload, drop_chance=0.4):
    """
    Simula uma rede altamente instável enviando dados em pedaços (chunks)
    e forçando desconexões parciais para testar o modo WAL e o Catch-Up.
    """
    print(f"📡 [Chaos] Iniciando envio de estresse para {target_ip}:{target_port}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((target_ip, target_port))
        
        raw_data = json.dumps(payload).encode('utf-8')
        chunk_size = max(1, len(raw_data) // 4)
        
        for i in range(0, len(raw_data), chunk_size):
            # Garante que vai testar tanto a persistência parcial quanto a interrupção abrupta
            if random.random() < drop_chance:
                print("💥 [Chaos Injector] INTERRUPÇÃO FORÇADA! Simulando queda física de cabo/sinal.")
                s.close()
                return False
            
            chunk = raw_data[i:i+chunk_size]
            s.sendall(chunk)
            print(f"📦 [Chaos] Chunk de {len(chunk)} bytes transmitido...")
            time.sleep(0.3)
            
        s.close()
        print("✔ [Chaos] Dados enviados com sucesso (A rede resistiu desta vez).")
        return True
    except Exception as e:
        print(f"❌ [Chaos] Falha de rede capturada com sucesso: {e}")
        return False

if __name__ == "__main__":
    print("⚡ Injetor de Caos da v2100 calibrado com sucesso.")
    
    # Payload pesado para estressar a recepção assíncrona
    test_payload = {
        "type": "NEW_BLOCK",
        "block_id": 2,
        "content": "carga_caos_stresse_limite_" * 40,
        "prev_hash": "c5db4053e3390b66483c57156fef1610edabb810f9653c43307ed5605c0a2824",
        "current_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
    
    # Dispara o caos apontando para o IP local do MASTER (porta interna 9090) que está ativo
    simulate_unstable_network_send("121.0.0.1", 9090, test_payload)
