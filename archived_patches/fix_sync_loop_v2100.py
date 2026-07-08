import re

with open("nexus_distributed_core.py", "r") as f:
    code = f.read()

# Remove o bloco de sincronismo problemático da inicialização estática se houver
# E injeta a verificação robusta diretamente dentro da thread assíncrona de polling
old_polling_peer_loop = """                    if "ACCEPTED" in res_body.get("status", ""):
                        self.passport = res_body.get("your_passport")
                        self.passport_ts = res_body.get("passport_ts", 0.0)
                        self.hub_signature = res_body.get("hub_signature")
                        raw_peers = res_body.get("active_peers", {})"""

new_polling_peer_loop = """                    if "ACCEPTED" in res_body.get("status", ""):
                        self.passport = res_body.get("your_passport")
                        self.passport_ts = res_body.get("passport_ts", 0.0)
                        self.hub_signature = res_body.get("hub_signature")
                        raw_peers = res_body.get("active_peers", {})
                        
                        # Gatilho Dinâmico de Catch-Up v2100 dentro do loop de polling
                        if self.role == "FOLLOWER" and raw_peers:
                            master_node = next((p for p, i in raw_peers.items() if i.get("role") == "MASTER"), None)
                            # Se local tem 0 blocos e existe MASTER na rede, aciona sincronismo
                            if master_node and self.block_counter == 0:
                                try:
                                    import socket
                                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    m_info = raw_peers[master_node]
                                    s.connect((m_info["wan_ip"], m_info["internal_tcp_port"]))
                                    
                                    sync_payload = {
                                        "type": "SYNC_CHECK", "origin": self.node_id,
                                        "last_known_hash": "0" * 64,
                                        "auth_passport": self.passport, "auth_ts": self.passport_ts
                                    }
                                    s.sendall(json.dumps(sync_payload).encode('utf-8'))
                                    data = s.recv(65536)
                                    if data:
                                        resp = json.loads(data.decode('utf-8'))
                                        if resp.get("status") == "SYNC_BATCH" and resp.get("blocks"):
                                            print(f"📥 [Catch-Up] Defasagem detectada! Baixando {resp['total_blocks']} blocos do MASTER...")
                                            import sqlite3
                                            conn = sqlite3.connect("nexus_ledger.db")
                                            cursor = conn.cursor()
                                            for b in resp["blocks"]:
                                                cursor.execute("INSERT OR IGNORE INTO ledger (id, content, prev_hash, hash) VALUES (?, ?, ?, ?)",
                                                               (b["block_id"], b["content"], b["prev_hash"], b["current_hash"]))
                                                self.block_counter = max(self.block_counter, b["block_id"])
                                            conn.commit()
                                            conn.close()
                                            print(f"✔ [Catch-Up] Sincronização concluída! Core alinhado na altura de Bloco #{self.block_counter}")
                                    s.close()
                                except Exception as e:
                                    pass"""

if "Defasagem detectada" not in code and old_polling_peer_loop in code:
    code = code.replace(old_polling_peer_loop, new_polling_peer_loop)
    with open("nexus_distributed_core.py", "w") as f:
        f.write(code)
    print("✔ [Ajuste v2100] Sincronizador assíncrono movido para a thread cíclica com sucesso!")
else:
    print("⚠️ Verifique a estrutura do core.")
