import os
import sys
import time
import multiprocessing
from persistence import NexusPersistence
from network_mesh import NexusMeshNode
from heartbeat import HeartbeatMonitor

class NexusSupervisor:
    def __init__(self, target_function, worker_count=2, mesh_port=8080, remote_nodes=None):
        self.target_function = target_function
        self.worker_count = worker_count
        self.workers = {}
        self.remote_nodes = remote_nodes or []
        
        # 1. Inicializa a Engine de Persistência Imutável v700
        self.persistence = NexusPersistence()
        print("⚡ [Nexus Core] Motor de persistência SHA-256 acoplado.")
        self.recovered_state = self.persistence.recover_state()
        
        # 2. Inicializa o Monitor Distribuído de Heartbeats v900
        self.heartbeat = HeartbeatMonitor(timeout_threshold=3.0)
        self.heartbeat.start_validation_loop(on_missing_callback=self._handle_node_timeout)
        
        # 3. Inicializa o Nó de Rede Mesh v800
        self.mesh = NexusMeshNode(port=mesh_port)
        self.mesh.start_server(self._handle_mesh_message)

    def _handle_mesh_message(self, message, addr):
        """Processa mensagens e sinalizações de vida (PING) vindas da rede."""
        event = message.get("event")
        data = message.get("data", {})
        node_id = data.get("node_id", f"{addr[0]}:{addr[1]}")
        
        if event == "HEARTBEAT_PING":
            # Registra a presença ativa do nó remoto
            self.heartbeat.register_ping(node_id)
        elif event == "REMOTE_CRASH_ALERT":
            print(f"\n🚨 [Mesh Inbound] Alerta Global: O componente remoto '{data.get('worker_id')}' falhou!")
        elif event == "CHAIN_SYNC":
            print(f"\n🔗 [Mesh Inbound] Sincronizando novo bloco de transação recebido...")

    def _handle_node_timeout(self, entity_id):
        """Callback acionado se um nó remoto parar de responder (Heartbeat Timeout)."""
        print(f"\n💀 [Consenso] Nó remoto {entity_id} foi declarado morto por ausência de batimentos cardíacos!")
        # Aqui o Nexus pode iniciar o failover distribuído elegendo um novo nó líder

    def _broadcast_mesh_event(self, payload):
        """Propaga dados para todos os membros ativos cadastrados na malha."""
        for host, port in self.remote_nodes:
            self.mesh.send_transaction(host, port, payload)

    def _spawn_worker(self, worker_id):
        p = multiprocessing.Process(
            target=self.target_function, 
            args=(worker_id,), 
            name=worker_id
        )
        p.daemon = True
        p.start()
        
        self.workers[worker_id] = p
        
        payload_spawn = {
            "event": "WORKER_SPAWN",
            "data": {"worker_id": worker_id, "pid": p.pid}
        }
        self.persistence.append_transaction(payload_spawn)
        self._broadcast_mesh_event(payload_spawn)
        print(f"🟩 [Spawn] Worker '{worker_id}' ativo e registrado (PID: {p.pid}).")

    def start(self):
        print(f"🚀 [Core] Inicializando Árvore de Supervisão Ativa Baseada em Consenso...")
        for i in range(self.worker_count):
            worker_id = f"Worker-{i}"
            self._spawn_worker(worker_id)
            
        self._monitor_loop()

    def _monitor_loop(self):
        print("🔍 [Monitor] Supervisor local ativo.")
        try:
            while True:
                time.sleep(1.0)
                # Simula o envio periódico do próprio batimento cardíaco para a malha
                self._broadcast_mesh_event({"event": "HEARTBEAT_PING", "data": {"node_id": "Local_Master"}})
                
                for worker_id, process in list(self.workers.items()):
                    if not process.is_alive():
                        print(f"🚨 [CRASH] Falha física local detectada em: {worker_id}")
                        
                        payload_crash = {
                            "event": "WORKER_CRASH",
                            "data": {"worker_id": worker_id, "timestamp": time.time()}
                        }
                        self.persistence.append_transaction(payload_crash)
                        self._broadcast_mesh_event({"event": "REMOTE_CRASH_ALERT", "data": {"worker_id": worker_id}})
                        
                        print(f"🔄 [Mitigação] Reinstanciando worker através da política padrão...")
                        self._spawn_worker(worker_id)
                        
        except KeyboardInterrupt:
            print("\n🛑 [Core] Encerramento controlado ativado pelo operador SRE.")

def dummy_worker_task(name):
    while True:
        time.sleep(5)

if __name__ == "__main__":
    supervisor = NexusSupervisor(
        target_function=dummy_worker_task, 
        worker_count=2, 
        mesh_port=8080,
        remote_nodes=[]
    )
    supervisor.start()
