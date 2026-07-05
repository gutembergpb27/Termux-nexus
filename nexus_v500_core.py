import os
import sys
import time
import multiprocessing
from persistence import NexusPersistence
from network_mesh import NexusMeshNode

class NexusSupervisor:
    def __init__(self, target_function, worker_count=2, mesh_port=8080, remote_nodes=None):
        self.target_function = target_function
        self.worker_count = worker_count
        self.workers = {}
        self.remote_nodes = remote_nodes or [] # Lista de IPs remotos: [("192.168.1.50", 8080)]
        
        # 1. Inicializa a Engine de Persistência Imutável v700
        self.persistence = NexusPersistence()
        print("⚡ [Nexus Core] Motor de persistência SHA-256 acoplado.")
        self.recovered_state = self.persistence.recover_state()
        
        # 2. Inicializa o Nó de Rede Mesh v800
        self.mesh = NexusMeshNode(port=mesh_port)
        self.mesh.start_server(self._handle_mesh_message)

    def _handle_mesh_message(self, message, addr):
        """Callback acionado quando um evento de rede remoto chega de outro nó."""
        print(f"\n📡 [Mesh Inbound] Pacote recebido de {addr[0]}:{addr[1]}")
        event = message.get("event")
        data = message.get("data", {})
        
        if event == "REMOTE_CRASH_ALERT":
            print(f"⚠️ [Alerta Global] O nó remoto avisou que o componente '{data.get('worker_id')}' caiu!")
        elif event == "CHAIN_SYNC":
            print(f"🔗 [Sincronização] Bloco de transação recebido via rede. Sincronizando ledger...")

    def _broadcast_mesh_event(self, payload):
        """Dispara as atualizações lógicas do nó local para todos os nós remotos cadastrados."""
        for host, port in self.remote_nodes:
            self.mesh.send_transaction(host, port, payload)

    def _spawn_worker(self, worker_id):
        """Instancia o worker na RAM, gera o bloco local e propaga na rede Mesh."""
        p = multiprocessing.Process(
            target=self.target_function, 
            args=(worker_id,), 
            name=worker_id
        )
        p.daemon = True
        p.start()
        
        self.workers[worker_id] = p
        
        # Gera o payload atômico
        payload_spawn = {
            "event": "WORKER_SPAWN",
            "data": {"worker_id": worker_id, "pid": p.pid}
        }
        
        # Salva localmente na cadeia de blocos (v700)
        self.persistence.append_transaction(payload_spawn)
        
        # Propaga para a rede distribuída (v800)
        self._broadcast_mesh_event(payload_spawn)
        
        print(f"🟩 [Spawn] Worker '{worker_id}' inicializado e propagado na Malha (PID: {p.pid}).")

    def start(self):
        print(f"🚀 [Core] Inicializando Árvore de Supervisão Ativa Distribuída...")
        for i in range(self.worker_count):
            worker_id = f"Worker-{i}"
            self._spawn_worker(worker_id)
            
        self._monitor_loop()

    def _monitor_loop(self):
        print("🔍 [Monitor] Supervisor ativo em segundo plano.")
        try:
            while True:
                time.sleep(1.0)
                for worker_id, process in list(self.workers.items()):
                    if not process.is_alive():
                        print(f"🚨 [CRASH] Falha física detectada localmente em: {worker_id}")
                        
                        payload_crash = {
                            "event": "WORKER_CRASH",
                            "data": {"worker_id": worker_id, "timestamp": time.time()}
                        }
                        
                        # Alerta o armazenamento local e propaga o pânico controlado via rede Mesh
                        self.persistence.append_transaction(payload_crash)
                        self._broadcast_mesh_event({"event": "REMOTE_CRASH_ALERT", "data": {"worker_id": worker_id}})
                        
                        print(f"🔄 [Mitigação] Restaurando ciclo de execução distribuída...")
                        self._spawn_worker(worker_id)
                        
        except KeyboardInterrupt:
            print("\n🛑 [Core] Encerramento controlado ativado pelo operador SRE.")

def dummy_worker_task(name):
    while True:
        time.sleep(5)

if __name__ == "__main__":
    # Para testar localmente, podemos simular que estamos escutando na porta 8080
    # E apontar um nó remoto falso para nós mesmos na porta 8081 se quisermos testar loopback!
    supervisor = NexusSupervisor(
        target_function=dummy_worker_task, 
        worker_count=2, 
        mesh_port=8080,
        remote_nodes=[] # Adicione IPs de outros dispositivos aqui no futuro! Ex: [("192.168.0.15", 8080)]
    )
    supervisor.start()

