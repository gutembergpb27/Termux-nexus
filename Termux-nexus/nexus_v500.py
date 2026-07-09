import multiprocessing
import time
import os
import sys

def telemetry_worker(queue):
    """[Filho 1] Coleta métricas de alta frequência (~125 Hz) para a RAM"""
    count = 0
    while True:
        try:
            count += 1
            metrics = {
                "tick": count,
                "timestamp": time.time(),
                "latency": 0.008,  # Simulação de latência de amostragem
                "cpu_mock": 15.4 + (count % 5)
            }
            queue.put(metrics)
            time.sleep(0.008)  # ~125 Hz
        except KeyboardInterrupt:
            break

def watcher_and_ui():
    """[Pai / Watcher / UI] O cérebro do sistema. Monitora e renderiza a tela"""
    # Inicialização do ecossistema e filas
    telemetry_queue = multiprocessing.Queue()
    crashes = 0
    start_time = time.time()
    
    # Inicializa o processo coletor
    telemetry_proc = multiprocessing.Process(target=telemetry_worker, args=(telemetry_queue,))
    telemetry_proc.start()
    
    last_tick = 0
    current_cpu = 0.0

    try:
        while True:
            # Captura os dados mais recentes da fila para atualizar a UI
            while not telemetry_queue.empty():
                data = telemetry_queue.get()
                last_tick = data["tick"]
                current_cpu = data["cpu_mock"]

            # Monitoramento de Caos: Se o coletor morrer, revive e conta o crash
            if not telemetry_proc.is_alive():
                crashes += 1
                telemetry_proc = multiprocessing.Process(target=telemetry_worker, args=(telemetry_queue,))
                telemetry_proc.start()

            # Cálculo do Índice de Resiliência (Métrica SRE)
            resilience_index = 100.0 if crashes == 0 else max(0.0, 100.0 - (crashes * 1.5))
            uptime = time.time() - start_time

            # Limpa o terminal para renderizar o frame de forma estável
            os.system('clear')
            
            # --- DASHBOARD VISUAL (NEXUS RUNTIME V500) ---
            print("=" * 60)
            print(f" 🪐  NEXUS RUNTIME v500  |  EDGE OBSERVABILITY INFRASTRUCTURE")
            print("=" * 60)
            print(f" [SISTEMA]")
            print(f" ├─ PID Watcher (UI): {os.getpid()}")
            print(f" ├─ PID Telemetria:   {telemetry_proc.pid} {'[ALERTA: REINICIADO]' if crashes > 0 else '[ESTÁVEL]'}")
            print(f" └─ Uptime Ativo:     {uptime:.1f}s")
            print("-" * 60)
            print(f" [MÉTRICAS DE ALTA FREQUÊNCIA]")
            print(f" ├─ Taxa de Amostragem: ~125 Hz")
            print(f" ├─ Total de Ticks:     {last_tick}")
            print(f" └─ Carga Simulada:     {current_cpu:.1f}%")
            print("-" * 60)
            print(f" [ENGINE DE CAOS & RESILIÊNCIA]")
            print(f" ├─ Histórico de Crashes: {crashes}")
            print(f" └─ Índice de Resiliência: {resilience_index:.1f}%")
            print("=" * 60)
            print(" Pressione CTRL + C para encerrar o ecossistema com segurança.")
            
            # Atualiza o dashboard 10 vezes por segundo (10 Hz)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[👑 Watcher] Finalizando processos filhos de forma limpa...")
        telemetry_proc.terminate()
        telemetry_proc.join()
        print("[👑 Watcher] Ecossistema Nexus encerrado com sucesso.")
        sys.exit(0)

if __name__ == "__main__":
    watcher_and_ui()
