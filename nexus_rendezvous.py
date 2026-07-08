import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

NODE_REGISTRY = {}
SESSION_TIMEOUT_SEC = 30

class NexusRendezvousHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return
    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            now = time.time()
            expired = [n for n, i in NODE_REGISTRY.items() if now - i["last_seen"] > SESSION_TIMEOUT_SEC]
            for n in expired: del NODE_REGISTRY[n]
            self.wfile.write(json.dumps({"infrastructure": "Nexus WAN Signaling Hub", "version": "v1950-spec", "active_nodes_count": len(NODE_REGISTRY), "registry": NODE_REGISTRY, "timestamp": now}, indent=4).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def do_POST(self):
        if self.path == "/register":
            try:
                content_length = int(self.headers["Content-Length"])
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                node_id = payload.get("node_id")
                if not node_id:
                    self.send_response(400); self.end_headers(); return
                NODE_REGISTRY[node_id] = {
                    "wan_ip": self.client_address[0], "wan_port": self.client_address[1],
                    "internal_tcp_port": payload.get("local_ports", {}).get("tcp", 8080),
                    "internal_metrics_port": payload.get("local_ports", {}).get("metrics", 9090),
                    "role": payload.get("role", "FOLLOWER"), "last_seen": time.time()
                }
                print(f"📡 [Rendezvous] No {node_id} registrado via {self.client_address[0]}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ACCEPTED", "active_peers": {n: i for n, i in NODE_REGISTRY.items() if n != node_id}}).encode("utf-8"))
            except:
                self.send_response(500); self.end_headers()

print("🚀 [Nexus Rendezvous Hub] Online na porta 8500...")
HTTPServer(("0.0.0.0", 8500), NexusRendezvousHandler).serve_forever()
