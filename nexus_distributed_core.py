from nexus_security import NexusSecurityProvider
import socket
import threading
import time
import json
import sqlite3
import os
import urllib.request

class NexusDistributedCore:
    def __init__(self, node_id, web_port, tcp_port, role):
        self.node_id = node_id
        self.web_port = int(web_port)
        self.tcp_port = int(tcp_port)
        self.role = role
        self.hub_url = os.getenv("NEXUS_HUB_URL", "http://127.0.0.1:8500")
        self.last_master_heartbeat = time.time()
        
        self.db_name = f"nexus_{self.node_id}.db"
        self.init_db()
        
        threading.Thread(target=self.start_tcp_server, daemon=True).start()
        threading.Thread(target=self.async_polling_loop, daemon=True).start()
        
        if self.role == "MASTER":
            threading.Thread(target=self.shell_intake_loop, daemon=True).start()
            
        print(f"⚡ [Nexus v2100] Core pronto. Papel corrente: [{self.role}]")
        
    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT,
                prev_hash TEXT,
                current_hash TEXT,
                votes INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def start_tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.tcp_port))
        server.listen(5)
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
            except:
                pass

    def handle_client(self, conn):
        try:
            data = conn.recv(65535).decode('utf-8')
            if not data: return
            msg = json.loads(data)
            
            if msg.get("type") == "SYNC_CHECK":
                db = sqlite3.connect(self.db_name)
                cursor = db.cursor()
                cursor.execute("SELECT * FROM ledger ORDER BY id ASC")
                blocks = cursor.fetchall()
                db.close()
                payload = {"type": "SYNC_BATCH", "blocks": blocks}
                conn.sendall(json.dumps(payload).encode('utf-8'))
                
            elif msg.get("type") == "SYNC_BATCH":
                db = sqlite3.connect(self.db_name)
                cursor = db.cursor()
                for b in msg.get("blocks", []):
                    cursor.execute("INSERT OR IGNORE INTO ledger (id, payload, prev_hash, current_hash, votes) VALUES (?, ?, ?, ?, ?)", b)
                db.commit()
                db.close()
                print(f"✔ [Catch-Up] Sincronização concluída! Core alinhado.")
        except:
            pass
        finally:
            conn.close()

    def async_polling_loop(self):
        print("📡 [v2100 Polling] Thread de monitoramento e failover ativa.")
        while True:
            try:
                time.sleep(5)
                current_time = time.time()
                
                # Heartbeat via urllib nativo
                try:
                    payload = json.dumps({"node_id": self.node_id, "port": self.web_port, "tcp_port": self.tcp_port, "role": self.role}).encode('utf-8')
                    req = urllib.request.Request(f"{self.hub_url}/register", data=payload, headers={'Content-Type': 'application/json'}, method='POST')
                    with urllib.request.urlopen(req, timeout=2) as response:
                        pass
                except:
                    pass
                
                # Coleta Peers via urllib nativo
                raw_peers = {}
                try:
                    with urllib.request.urlopen(f"{self.hub_url}/peers", timeout=2) as response:
                        if response.status == 200:
                            raw_peers = json.loads(response.read().decode('utf-8'))
                except:
                    pass
                
                master_node = next((p for p, i in raw_peers.items() if i.get("role") == "MASTER" and p != self.node_id), None)
                
                if master_node:
                    self.last_master_heartbeat = current_time
                else:
                    delta = current_time - self.last_master_heartbeat
                    if self.role == "FOLLOWER" and delta > 15.0:
                        print(f"\n🚨 [Failover] MASTER ausente há {delta:.1f}s!")
                        print("🗳️ [Eleição] Iniciando autoproclamação de liderança por vacância...")
                        self.role = "MASTER"
                        print(f"👑 [Sucesso] Nó {self.node_id} promovido para [{self.role}]")
                        threading.Thread(target=self.shell_intake_loop, daemon=True).start()
                        break
            except Exception as e:
                print(f"❌ [Polling Error] {e}")

    def shell_intake_loop(self):
        while self.role == "MASTER":
            try:
                payload = input(f"[{self.node_id} Intake] Digite o payload -> ")
                if not payload: continue
                
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ledger (payload, prev_hash, current_hash, votes) VALUES (?, ?, ?, ?)", (payload, "hash_prev", "hash_curr", 0))
                conn.commit()
                conn.close()
                print(f"✔ [Aprovado] Bloco selado localmente sob modo WAL!")
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        print("Uso: python nexus_distributed_core.py <node_id> <web_port> <tcp_port> <role>")
    else:
        core = NexusDistributedCore(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        while True:
            time.sleep(1)
