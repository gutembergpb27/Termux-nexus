with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Substitui o método de sincronização para usar o IP público mapeado pelo Hub
old_catchup = """    def trigger_catchup(self, master_info):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", int(master_info["tcp_port"])))
            req = {"type": "SYNC_CHECK", "node_id": self.node_id}
            s.sendall(json.dumps(req).encode('utf-8'))
            s.close()
        except:
            pass"""

new_catchup = """    def trigger_catchup(self, master_info):
        try:
            # WAN Ready: Conecta usando o IP real detectado pelo Hub de sinalização
            target_ip = master_info.get("ip", "127.0.0.1")
            target_port = int(master_info["tcp_port"])
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5) # Evita travamento de thread se a porta estiver fechada
            s.connect((target_ip, target_port))
            
            req = {"type": "SYNC_CHECK", "node_id": self.node_id}
            s.sendall(json.dumps(req).encode('utf-8'))
            s.close()
        except Exception as e:
            pass"""

if "target_ip = master_info.get" not in code:
    code = code.replace(old_catchup, new_catchup)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [WAN Upgrade] Core atualizado para realizar sincronização via IP Público!")
else:
    print("⚠️ Upgrade WAN já aplicado.")
