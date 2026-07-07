import socket
import threading
import time
import json
import sys
import sqlite3
import hashlib
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

UDP_BROADCAST_PORT = 50005
BUFFER_SIZE = 4096

class NexusMetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return
        
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            core = self.server.core_instance
            
            ram_usage_mb = 0.0
            try:
                with open('/proc/self/status', 'r') as f:
                    for line in f:
                        if 'VmRSS:' in line:
                            ram_usage_mb = float(line.split()[1]) / 1024.0
                            break
            except Exception:
                ram_usage_mb = -1.0

            db_size_bytes = 0
            try:
                if os.path.exists(core.db_name):
                    db_size_bytes = os.path.getsize(core.db_name)
            except Exception: pass

            metrics_payload = {
                "vision": "Sistema Operacional Logico para Edge AI Resiliente",
                "node_id": core.node_id,
                "role": core.role,
                "tcp_port": core.tcp_port,
                "last_known_hash": core.last_block_hash,
                "active_peers_count": len(core.active_nodes),
                "sre_metrics": {
                    "total_blocks_committed": core.block_counter,
                    "last_consensus_latency_ms": round(core.last_latency_ms, 2),
                    "process_ram_footprint_mb": round(ram_usage_mb, 2),
                    "sqlite_wal_size_bytes": db_size_bytes
                },
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(metrics_payload, indent=4).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        core = self.server.core_instance
        if self.path == '/inject':
            if core.role != "MASTER":
                self.send_response(403)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Apenas o MASTER aceita injecoes"}).encode('utf-8'))
                return

            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                tx_data = payload.get("data", "")
                success, latency, b_id, b_hash = core.process_new_transaction(tx_data, silent=True)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    "status": "COMMITTED" if success else "REJECTED",
                    "block_id": b_id,
                    "latency_ms": round(latency, 2),
                    "hash": b_hash
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception:
                self.send_response(500)
                self.end_headers()

class NexusDistributedCore:
    def __init__(self, node_id, tcp_port, metrics_port):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.metrics_port = metrics_port
        self.db_name = f"nexus_{self.node_id}.db"
        self.active_nodes = {}
        self.role = "FOLLOWER"
        self.running = True
        self.last_block_hash = "0" * 64 
        self.block_counter = 0
        self.last_latency_ms = 0.0

        self.init_local_storage()

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(('', UDP_BROADCAST_PORT))

        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server.bind(('0.0.0.0', self.tcp_port))
        self.tcp_server.listen(50)

    def init_local_storage(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                origin_node TEXT,
                block_payload TEXT,
                prev_hash TEXT,
                current_hash TEXT
            )
        """)
        cursor.execute("SELECT current_hash, id FROM ledger ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row: 
            self.last_block_hash = row[0]
            self.block_counter = row[1]
        conn.commit()
        conn.close()
        print(f"🗄️ [Storage] Base {self.db_name} ativa (WAL). Bloco: #{self.block_counter}")

    def calculate_hash(self, index, payload_text, prev_hash):
        block_string = f"{index}{payload_text}{prev_hash}".encode('utf-8')
        return hashlib.sha256(block_string).hexdigest()

    def save_block_to_db(self, origin, payload_text, prev_hash, current_hash):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ledger (timestamp, origin_node, block_payload, prev_hash, current_hash) VALUES (?, ?, ?, ?, ?)",
                (time.time(), origin, payload_text, prev_hash, current_hash)
            )
            conn.commit()
            conn.close()
            self.last_block_hash = current_hash
        except Exception: pass

    def start_udp_beacon(self):
        def beacon_loop():
            while self.running:
                try:
                    payload = {"node_id": self.node_id, "tcp_port": self.tcp_port, "role": self.role}
                    self.udp_socket.sendto(json.dumps(payload).encode('utf-8'), ('255.255.255.255', UDP_BROADCAST_PORT))
                except Exception: pass
                time.sleep(1)
        threading.Thread(target=beacon_loop, daemon=True).start()

    def start_udp_listener(self):
        def listener_loop():
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(BUFFER_SIZE)
                    payload = json.loads(data.decode('utf-8'))
                    r_id = payload["node_id"]
                    if r_id == self.node_id: continue
                    self.active_nodes[r_id] = {
                        "ip": addr[0], "port": payload["tcp_port"], "role": payload["role"], "last_seen": time.time()
                    }
                except Exception: pass
        threading.Thread(target=listener_loop, daemon=True).start()

    def start_tcp_listener(self):
        def tcp_loop():
            while self.running:
                try:
                    client_sock, addr = self.tcp_server.accept()
                    data = client_sock.recv(BUFFER_SIZE)
                    if data:
                        msg = json.loads(data.decode('utf-8'))
                        self.save_block_to_db(msg['origin'], msg['content'], msg['prev_hash'], msg['current_hash'])
                        ack_response = {"status": "ACK", "node_id": self.node_id, "verified_hash": self.last_block_hash}
                        client_sock.sendall(json.dumps(ack_response).encode('utf-8'))
                    client_sock.close()
                except Exception: pass
        threading.Thread(target=tcp_loop, daemon=True).start()

    def start_metrics_server(self):
        def http_loop():
            print(f"📊 [SRE Metrics] Escutando telemetria na porta {self.metrics_port}...")
            server = HTTPServer(('0.0.0.0', self.metrics_port), NexusMetricsHandler)
            server.core_instance = self
            while self.running: server.handle_request()
        threading.Thread(target=http_loop, daemon=True).start()

    def start_async_intake(self):
        def intake_loop():
            time.sleep(2.0)
            while self.running:
                if self.role == "MASTER":
                    try:
                        tx_data = input("\n📥 [v1900 Edge Console] Propor Bloco -> ")
                        if tx_data.strip() and self.role == "MASTER":
                            self.process_new_transaction(tx_data, silent=False)
                    except (KeyboardInterrupt, EOFError): break
                else:
                    time.sleep(1)
        threading.Thread(target=intake_loop, daemon=True).start()

    def send_tcp_proposal(self, text_message, prev_hash, current_hash):
        ack_votes = 0
        for n_id, info in list(self.active_nodes.items()):
            if info["role"] == "FOLLOWER":
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2.5)
                    sock.connect((info["ip"], info["port"]))
                    payload = {"origin": self.node_id, "content": text_message, "prev_hash": prev_hash, "current_hash": current_hash}
                    sock.sendall(json.dumps(payload).encode('utf-8'))
                    reply = sock.recv(BUFFER_SIZE)
                    if reply:
                        ack_msg = json.loads(reply.decode('utf-8'))
                        if ack_msg.get("status") == "ACK" and ack_msg.get("verified_hash") == current_hash:
                            ack_votes += 1
                    sock.close()
                except Exception: pass
        return ack_votes

    def process_new_transaction(self, payload_text, silent=False):
        self.block_counter += 1
        p_hash = self.last_block_hash
        c_hash = self.calculate_hash(self.block_counter, payload_text, p_hash)
        
        total_network_nodes = len(self.active_nodes) + 1
        required_quorum = (total_network_nodes // 2) + 1
        
        start_time = time.time()
        network_acks = self.send_tcp_proposal(payload_text, p_hash, c_hash)
        total_votes = network_acks + 1
        self.last_latency_ms = (time.time() - start_time) * 1000.0
        
        if total_votes >= required_quorum:
            if not silent:
                print(f"⏱️ Consenso Wi-Fi: {self.last_latency_ms:.2f} ms | Bloco #{self.block_counter} selado!")
            self.save_block_to_db(self.node_id, payload_text, p_hash, c_hash)
            return True, self.last_latency_ms, self.block_counter, c_hash
        else:
            self.block_counter -= 1
            return False, self.last_latency_ms, self.block_counter, p_hash

    def run_cluster_lifecycle(self):
        now = time.time()
        to_remove = [n_id for n_id, info in self.active_nodes.items() if now - info["last_seen"] > 10]
        for n_id in to_remove: del self.active_nodes[n_id]
        
        higher_nodes_alive = [n_id for n_id in self.active_nodes.keys() if n_id > self.node_id]
        if self.role == "MASTER" and higher_nodes_alive: self.role = "FOLLOWER"
        master_exists = any(info["role"] == "MASTER" for info in self.active_nodes.values())
        if not master_exists and self.role != "MASTER" and not higher_nodes_alive: self.role = "MASTER"

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(1)
    core = NexusDistributedCore(node_id=sys.argv[1], tcp_port=int(sys.argv[2]), metrics_port=int(sys.argv[3]))
    core.start_udp_beacon(); core.start_udp_listener(); core.start_tcp_listener(); core.start_metrics_server()
    core.start_async_intake()
    try:
        while core.running:
            core.run_cluster_lifecycle()
            time.sleep(1)
    except (KeyboardInterrupt, EOFError): pass
