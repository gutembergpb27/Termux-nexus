import time
import threading

class HeartbeatMonitor:
    def __init__(self, timeout_threshold=3.0):
        self.timeout_threshold = timeout_threshold
        self.last_seen = {} # Estrutura: {"node_id" ou "worker_id": timestamp}
        self.is_monitoring = False

    def register_ping(self, entity_id):
        """Atualiza o marcador de tempo sempre que um sinal de vida chega."""
        self.last_seen[entity_id] = time.time()

    def start_validation_loop(self, on_missing_callback):
        """Dispara uma thread para inspecionar nós fantasmas ou mortos por timeout."""
        self.is_monitoring = True
        def _loop():
            while self.is_monitoring:
                time.sleep(1.0)
                now = time.time()
                # Copia as chaves para evitar erro de concorrência ao deletar/modificar
                for entity_id, last_timestamp in list(self.last_seen.items()):
                    if now - last_timestamp > self.timeout_threshold:
                        print(f"⚠️ [Heartbeat] Timeout atingido para a entidade: {entity_id}")
                        del self.last_seen[entity_id]
                        # Dispara o gatilho de mitigação distribuída
                        on_missing_callback(entity_id)
                        
        threading.Thread(target=_loop, daemon=True).start()
