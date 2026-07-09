with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Nova estrutura limpa e sem dependências para o loop de monitoramento
updated_loop = """    def async_polling_loop(self):
        print("📡 [v2100 Polling] Thread de monitoramento e failover ativa.")
        if not hasattr(self, 'last_master_heartbeat'):
            self.last_master_heartbeat = time.time()
            
        while True:
            try:
                time.sleep(5)
                current_time = time.time()
                
                # Coleta a tabela global do Hub
                import requests
                raw_peers = {}
                try:
                    r = requests.get(f"{self.hub_url}/peers", timeout=3)
                    if r.status_code == 200:
                        raw_peers = r.json()
                except:
                    pass
                
                master_node = next((p for p, i in raw_peers.items() if i.get("role") == "MASTER"), None)
                
                if master_node:
                    self.last_master_heartbeat = current_time
                    # Executa o Catch-Up se for seguidor
                    if self.role == "FOLLOWER":
                        self.trigger_catchup_protocol(master_node, raw_peers[master_node])
                else:
                    # Se não houver MASTER ativo no Hub, valida o timeout de vacância
                    delta = current_time - self.last_master_heartbeat
                    if self.role == "FOLLOWER" and delta > 15.0:
                        print(f"🚨 [Failover] MASTER ausente há {delta:.1f}s!")
                        print("🗳️ [Eleição] Iniciando autoproclamação de liderança por vacância...")
                        self.role = "MASTER"
                        self.node_id = f"MASTER-PROMOTE-{self.node_id}"
                        print(f"👑 [Sucesso] Nó promovido! Papel atual: [{self.role}] como {self.node_id}")
                        import threading
                        threading.Thread(target=self.shell_intake_loop, daemon=True).start()
                        break
            except Exception as e:
                print(f"❌ [Polling Error] {e}")
"""

# Substituição direta da assinatura antiga até o final da lógica padrão
import re
code = re.sub(r"    def async_polling_loop\(self\):.*?(\n    def |\Z)", updated_loop + "\n\\1", code, flags=re.DOTALL)

with open("nexus_distributed_core.py", "w") as f:
    f.write(code)

print("✔ [Core Rebuilt] Thread de monitoramento assíncrono reconstruída com sucesso!")
