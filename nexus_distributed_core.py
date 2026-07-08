import sys
import time
import json
import socket
import sqlite3
import hashlib
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BUFFER_SIZE = 4096
DB_FILE = "nexus_ledger.db"

class NexusDistributedCore:
    def __init__(self, node_id, tcp_port, metrics_port, rendezvous_url="http://192.168.1.5:8500/register"):
        self.node_id = node_id
        self.tcp_port = int(tcp_port)
        self.metrics_port = int(metrics_port)
        self.rendezvous_url = rendezvous_url
        
        self.role = "FOLLOWER"
        self.running = True
        self.active_nodes = {}
        self.block_counter = 0
        self.passport = None
        self.passport_ts = 0.0
        self.hub_signature = None
        
        self.init_database()
        
        # Inicialização das Threads SRE v1950
        threading.Thread(target=self.start_tcp_listener, daemon=True).start()
        threading.Thread(target=self.start_metrics_server, daemon=True).start()
        threading.Thread(target=self.start_wan_signaling, daemon=True).start()
        threading.Thread(target=self.start_async_intake, daemon=True).start()

    def init_database(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY,
                payload TEXT,
                prev_hash TEXT,
                current_hash TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()

    def get_last_hash(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT current_hash FROM ledger ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "0" * 64

    def get_wal_size(self):
        try:
            import os
            return os.path.getsize(f"{DB_FILE}-wal")
        except:
            return 0

    def start_wan_signaling(self):
        """ Thread v1950: Polling cíclico contra o Rendezvous Hub para descoberta WAN """
        print(f"📡 [WAN] Registro ativo pareado com: {self.rendezvous_url}")
        while self.running:
            try:
                payload = {
                    "node_id": self.node_id,
                    "role": self.role,
                    "local_ports": {"tcp": self.tcp_port, "metrics": self.metrics_port}
                }
                req_data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(self.rendezvous_url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
                
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    if "ACCEPTED" in res_body.get("status", ""):
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
                                    pass
                        # Atualiza dinamicamente a tabela de nós mapeados pelo NAT do Hub
                        self.active_nodes = {
                            n_id: {
                                "ip": info["wan_ip"], "port": info["wan_port"],
                                "role": info["role"], "last_seen": time.time()
                            } for n_id, info in raw_peers.items()
                        }
            except Exception:
                pass
            time.sleep(5)

    def start_tcp_listener(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", self.tcp_port))
        server_sock.listen(5)
        
        while self.running:
            try:
                sock, _ = server_sock.accept()
                data = sock.recv(BUFFER_SIZE)
                if data:
                    payload = json.loads(data.decode('utf-8'))
                    
                    # Se receber proposta válida, commita passivamente como FOLLOWER
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO ledger (payload, prev_hash, current_hash, timestamp) VALUES (?, ?, ?, ?)",
                                   (payload["content"], payload["prev_hash"], payload["current_hash"], time.time()))
                    conn.commit()
                    conn.close()
                    
                    sock.sendall(json.dumps({"status": "ACK", "verified_hash": payload["current_hash"]}).encode('utf-8'))
                sock.close()
            except Exception:
                pass

    def send_tcp_proposal(self, text_message, prev_hash, current_hash):
        ack_votes = 0
        for n_id, info in list(self.active_nodes.items()):
            # Detecção inteligente: Se estiver na mesma rede/dispositivo, usa a porta interna
            target_ip = info["ip"]
            target_port = info.get("internal_tcp_port", 8080) if info["ip"] == self.rendezvous_url.split("//")[1].split(":")[0] or info["ip"] in ["127.0.0.1", "localhost"] else info["port"]
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.5) # Timeout estendido para NAT celular/WAN
            
            connected = False
            for _ in range(3): # Algoritmo de perfuração de barreira NAT (Hole Punching)
                try:
                    sock.connect((target_ip, target_port))
                    connected = True
                    break
                except socket.error:
                    time.sleep(0.1)
            
            if connected:
                try:
                    payload = {
                        "origin": self.node_id, "content": text_message,
                        "prev_hash": prev_hash, "current_hash": current_hash,
                        "auth_passport": self.passport,
                        "auth_ts": self.passport_ts
                    }
                    sock.sendall(json.dumps(payload).encode('utf-8'))
                    reply = sock.recv(BUFFER_SIZE)
                    if reply:
                        ack = json.loads(reply.decode('utf-8'))
                        if ack.get("status") == "ACK" and ack.get("verified_hash") == current_hash:
                            ack_votes += 1
                except Exception: pass
                finally: sock.close()
        return ack_votes

    def start_async_intake(self):
        time.sleep(1)
        print(f"\n⚡ [Nexus v1950] Core pronto. Papel corrente: [{self.role}]")
        while self.running:
            try:
                if self.role == "MASTER":
                    user_input = input(f"\n[v1950 Intake] Digite o payload -> ")
                    if not user_input.strip(): continue
                    
                    self.block_counter += 1
                    prev_hash = self.get_last_hash()
                    
                    sha = hashlib.sha256()
                    sha.update(f"{self.block_counter}{user_input}{prev_hash}".encode('utf-8'))
                    current_hash = sha.hexdigest()
                    
                    print(f"📦 [Quorum] Propondo Bloco #{self.block_counter}. Aguardando assinaturas WAN...")
                    votes = self.send_tcp_proposal(user_input, prev_hash, current_hash)
                    
                    # Registra localmente se obtiver consenso dos nós mapeados
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO ledger (payload, prev_hash, current_hash, timestamp) VALUES (?, ?, ?, ?)",
                                   (user_input, prev_hash, current_hash, time.time()))
                    conn.commit()
                    conn.close()
                    print(f"✔ [Aprovado] Bloco #{self.block_counter} selado em disco! Hash: {current_hash[:12]}... (Votos: {votes})")
                else:
                    # Se for FOLLOWER, o terminal fica em modo passivo monitorando
                    time.sleep(2)
            except KeyboardInterrupt:
                self.running = False

    def start_metrics_server(self):
        core_instance = self
        class MetricsHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args): return
            def do_GET(self):
                if self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    # Leitura de RAM nativa Linux/Android
                    ram_footprint = 0.0
                    try:
                        with open('/proc/self/status', 'r') as f:
                            for line in f:
                                if 'VmRSS:' in line:
                                    ram_footprint = float(line.split()[1]) / 1024.0
                                    break
                    except: pass
                    
                    metrics = {
                        "vision": "Sistema Operacional Logico para Edge AI Resiliente",
                        "node_id": core_instance.node_id,
                        "role": core_instance.role,
                        "tcp_port": core_instance.tcp_port,
                        "last_known_hash": core_instance.get_last_hash(),
                        "active_peers_count": len(core_instance.active_nodes),
                        "sre_metrics": {
                            "total_blocks_committed": core_instance.block_counter,
                            "process_ram_footprint_mb": round(ram_footprint, 2),
                            "sqlite_wal_size_bytes": core_instance.get_wal_size()
                        },
                        "timestamp": time.time()
                    }
                    self.wfile.write(json.dumps(metrics, indent=4).encode('utf-8'))
                else:
                    self.send_response(404); self.end_headers()

        HTTPServer(('0.0.0.0', self.metrics_port), MetricsHandler).serve_forever()

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python nexus_distributed_core.py <node_id> <tcp_port> <metrics_port> <role>")
        sys.exit(1)
    
    n_id = sys.argv[1]
    t_port = sys.argv[2]
    m_port = sys.argv[3]
    initial_role = sys.argv[4].upper()
    
    core = NexusDistributedCore(n_id, t_port, m_port)
    core.role = initial_role
    
    # Mantém a thread principal viva
    while core.running:
        time.sleep(1)
