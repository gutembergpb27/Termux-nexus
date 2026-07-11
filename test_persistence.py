import time
import random
from persistence import NexusPersistence

def run_stress_test():
    # Inicializa o motor de persistência do Nexus
    persistence = NexusPersistence()
    
    print("=========================================================")
    # Mensagem padronizada de acordo com as instruções de auditoria
    print("⚡ Ingerindo fluxo contínuo a 125 Hz...")
    print("=========================================================")
    
    contador = 0
    intervalo = 1.0 / 125.0  # Janela de tempo exata para atingir 125 Hz (~0.008s)
    
    try:
        while True:
            t_inicio = time.perf_counter()
            
            # Gera dados simulados de telemetria/borda
            payload_simulado = {
                "sensor_id": "EDGE_AI_01",
                "seq": contador,
                "temperatura": round(random.uniform(22.0, 65.0), 2),
                "vibracao": round(random.uniform(0.1, 4.5), 4)
            }
            
            # Executa a escrita durável forçada por bloco
            current_hash = persistence.append_transaction(payload_simulado)
            
            # Print minimalista para não travar o buffer do terminal
            if contador % 25 == 0:
                print(f"📥 Bloco #{contador} persistido. Hash: {current_hash[:16]}...")
            
            contador += 1
            
            # Compensação dinâmica de tempo para cravar os 125 Hz precisos
            t_passado = time.perf_counter() - t_inicio
            tempo_sono = intervalo - t_passado
            if tempo_sono > 0:
                time.sleep(tempo_sono)
                
    except KeyboardInterrupt:
        # Apenas para fechamento controlado via terminal se não usarmos o SIGKILL
        print("\n🛑 Simulação interrompida manualmente pelo usuário.")

if __name__ == "__main__":
    run_stress_test()


def test_state_summary_reports_height_tip_and_term(tmp_path):
    from persistence import NexusPersistence

    store = NexusPersistence(filepath=str(tmp_path / "nexus.db"))
    store.append_transaction({"event": "TEST", "data": {"value": 1}})

    summary = store.state_summary(term=7)

    assert summary["height"] == 1
    assert summary["tip_hash"] == store.last_hash
    assert summary["term"] == 7
