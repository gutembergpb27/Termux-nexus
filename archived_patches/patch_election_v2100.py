import re

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Definição do novo bloco de failover dinâmico para a thread de monitoramento assíncrono
failover_logic = """                        # Gatilho Dinâmico de Catch-Up v2100 dentro do loop de polling
                        if self.role == "FOLLOWER" and raw_peers:
                            master_node = next((p for p, i in raw_peers.items() if i.get("role") == "MASTER"), None)
                            
                            # Algoritmo de Eleição e Failover Automatizado
                            current_time = time.time()
                            if master_node:
                                self.last_master_heartbeat = current_time
                            elif hasattr(self, 'last_master_heartbeat') and (current_time - self.last_master_heartbeat > 15.0):
                                print("🚨 [Failover] MASTER ausente do ecossistema por mais de 15s!")
                                print("🗳️ [Eleição] Iniciando autoproclamação de liderança por vacância...")
                                self.role = "MASTER"
                                self.node_id = f"MASTER-PROMOTE-{self.node_id}"
                                print(f"👑 [Sucesso] Nó promovido com sucesso! Novo papel: [{self.role}] como {self.node_id}")
                                # Configura o prompt de input para aceitar novos blocos locais
                                import threading
                                threading.Thread(target=self.shell_intake_loop, daemon=True).start()"""

# Substitui o gatilho antigo para expandir o comportamento da thread assíncrona
if "MASTER-PROMOTE-" not in code:
    code = code.replace('if self.role == "FOLLOWER" and raw_peers:\n                            master_node = next((p for p, i in raw_peers.items() if i.get("role") == "MASTER"), None)', failover_logic)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [Ajuste v2100] Algoritmo de eleição e failover automatizado injetado no Core!")
else:
    print("⚠️ Algoritmo de failover já presente no arquivo fonte.")
