import multiprocessing
import time
import os
import sys

def telemetry_worker(queue):
    """Filho 1: Coleta dados simulados a ~125 Hz e joga na Fila (RAM)"""
    print(f"[🚀 Telemetria] Iniciado com PID: {os.getpid()}")
    count = 0
    while True:
        try:
            count += 1
            data = {"tick": count, "timestamp": time.time(), "status": "OK"}
            queue.put(data)
            time.sleep(0.008)  # ~125 Hz
        except KeyboardInterrupt:
            break

def database_worker(queue):
    """Filho 2: Escuta a Fila em RAM e simula a escrita no banco"""
    print(f"[💾 Banco de Dados] Iniciado com PID: {os.getpid()}")
    while True:
        try:
            if not queue.empty():
                data = queue.get()
                if data["tick"] % 125 == 0:
                    print(f"[💾 Banco de Dados] Lote salvo. Último tick: {data['tick']}")
            else:
                time.sleep(0.1)
        except KeyboardInterrupt:
            break

def watcher_master():
    """Processo Pai: O supervisor que gerencia a vida dos filhos"""
    print(f"[👑 Watcher Master] Iniciado com PID: {os.getpid()}")
    
    queue = multiprocessing.Queue()

    telemetry_proc = multiprocessing.Process(target=telemetry_worker, args=(queue,))
    database_proc = multiprocessing.Process(target=database_worker, args=(queue,))

    telemetry_proc.start()
    database_proc.start()

    print("[👑 Watcher Master] Sistema monitorado ativo. Loop de resiliência iniciado.")

    try:
        while True:
            time.sleep(1)
            
            if not telemetry_proc.is_alive():
                print("\n[🚨 CAOS] Telemetria morreu! Reiniciando...")
                telemetry_proc = multiprocessing.Process(target=telemetry_worker, args=(queue,))
                telemetry_proc.start()

            if not database_proc.is_alive():
                print("\n[🚨 CAOS] Banco de Dados morreu! Reiniciando...")
                database_proc = multiprocessing.Process(target=database_worker, args=(queue,))
                database_proc.start()

    except KeyboardInterrupt:
        print("\n[👑 Watcher Master] Encerrando ecossistema...")
        telemetry_proc.terminate()
        database_proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    watcher_master()
