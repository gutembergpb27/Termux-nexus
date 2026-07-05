import os
import sys
import time
import multiprocessing
from persistence import NexusPersistence

class NexusSupervisor:
    def __init__(self, target_function, worker_count=2):
        self.target_function = target_function
        self.worker_count = worker_count
        self.workers = {}
        
        # Inicializa a Engine de Persistência Imutável v700
        self.persistence = NexusPersistence()
        print("⚡ [Nexus Core] Motor de persistência SHA-256 acoplado.")
        
        # Recupera o estado lógico anterior se houver queda catastrófica
        self.recovered_state = self.persistence.recover_state()

    def _spawn_worker(self, worker_id):
        """Instancia um novo Worker isolado em memória e registra no WAL."""
        p = multiprocessing.Process(
            target=self.target_function, 
            args=(worker_id,), 
            name=worker_id
        )
        p.daemon = True
        p.start()
        
        self.workers[worker_id] = p
        
        # Ancoragem Atômica: Registra o nascimento do processo na cadeia imutável
        payload_spawn = {
            "event": "WORKER_SPAWN",
            "data": {"worker_id": worker_id, "pid": p.pid}
        }
        self.persistence.append_transaction(payload_spawn)
        print(f"🟩 [Spawn] Worker '{worker_id}' inicializado com sucesso (PID: {p.pid}).")

    def start(self):
        print(f"🚀 [Core] Inicializando Árvore de Supervisão Ativa (Workers solicitados: {self.worker_count})...")
        for i in range(self.worker_count):
            worker_id = f"Worker-{i}"
            self._spawn_worker(worker_id)
            
        self._monitor_loop()

    def _monitor_loop(self):
        """Loop de monitoramento não bloqueante de alta frequência."""
        print("🔍 [Monitor] Supervisor ativo em segundo plano.")
        try:
            while True:
                time.sleep(1.0) # Frequência de amostragem padrão do Nexus
                for worker_id, process in list(self.workers.items()):
                    # Verifica a integridade física do processo
                    if not process.is_alive():
                        print(f"🚨 [CRASH] Falha detectada no componente: {worker_id}")
                        
                        # Ancoragem Atômica: Registra a morte do processo no WAL antes da mitigação
                        payload_crash = {
                            "event": "WORKER_CRASH",
                            "data": {"worker_id": worker_id, "timestamp": time.time()}
                        }
                        self.persistence.append_transaction(payload_crash)
                        
                        # Protocolo de Mitigação Imediata (One-For-One Recovery)
                        print(f"🔄 [Mitigação] Restaurando ciclo de execução para '{worker_id}'...")
                        self._spawn_worker(worker_id)
                        
        except KeyboardInterrupt:
            print("\n🛑 [Core] Encerramento controlado ativado pelo operador SRE.")

# Função Dummy apenas para garantir compatibilidade caso o arquivo seja executado diretamente
def dummy_worker_task(name):
    print(f"⚙️ [{name}] Rodando loop de telemetria local...")
    while True:
        time.sleep(5)

if __name__ == "__main__":
    supervisor = NexusSupervisor(target_function=dummy_worker_task, worker_count=2)
    supervisor.start()

