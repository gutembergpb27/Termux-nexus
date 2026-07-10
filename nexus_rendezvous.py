import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from typing import Any, MutableMapping

from nexus_protocol import NexusProtocol, ReplayCache

PEERS = {}
PEER_TIMEOUT = 30


def register_peer(
    *,
    envelope: dict[str, Any],
    client_ip: str,
    protocol: NexusProtocol,
    replay_cache: ReplayCache,
    peers: MutableMapping[str, dict[str, Any]],
    now: float,
    ttl: float,
) -> dict[str, Any]:
    protocol.verify_envelope(
        envelope,
        now=now,
        ttl=ttl,
        replay_cache=replay_cache,
    )

    if envelope.get("type") != "REGISTER":
        raise ValueError("invalid registration message type")

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("invalid registration payload")

    node_id = str(payload.get("node_id", "")).strip()
    sender = str(envelope.get("sender", "")).strip()

    if not node_id:
        raise ValueError("missing node_id")

    if node_id != sender:
        raise ValueError("registration sender does not match node_id")

    role = str(payload.get("role", "")).strip().upper()
    if role not in {"FOLLOWER", "CANDIDATE", "MASTER"}:
        raise ValueError("invalid role")

    try:
        web_port = int(payload["web_port"])
        tcp_port = int(payload["tcp_port"])
        protocol_version = int(payload["protocol_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid registration fields") from exc

    if not 1 <= web_port <= 65535 or not 1 <= tcp_port <= 65535:
        raise ValueError("invalid registration port")

    record = {
        "node_id": node_id,
        "role": role,
        "web_port": web_port,
        "tcp_port": tcp_port,
        "protocol_version": protocol_version,
        "ip": client_ip,
        "last_seen": float(now),
    }

    peers[node_id] = record
    return record

class NexusRendezvousHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == "/register":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            node_id = payload.get("node_id")
            
            # NAT Traversal: captura o IP real de quem bateu no socket
            client_ip = self.headers.get("X-Forwarded-For")
            if client_ip:
                public_ip = client_ip.split(',')[0].strip()
            else:
                public_ip = self.client_address[0]
            
            payload["ip"] = public_ip
            payload["last_seen"] = time.time()
            
            PEERS[node_id] = payload
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "registered", "detected_ip": public_ip}).encode('utf-8'))

    def do_GET(self):
        if self.path == "/peers":
            current_time = time.time()
            active_peers = {k: v for k, v in PEERS.items() if current_time - v.get("last_seen", 0) < PEER_TIMEOUT}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(active_peers).encode('utf-8'))

def auto_reap_expired_nodes():
    while True:
        time.sleep(5)
        current_time = time.time()
        expired = [k for k, v in PEERS.items() if current_time - v.get("last_seen", 0) >= PEER_TIMEOUT]
        for node in expired:
            del PEERS[node]

if __name__ == "__main__":
    threading.Thread(target=auto_reap_expired_nodes, daemon=True).start()
    server_address = ("0.0.0.0", 8500)
    httpd = HTTPServer(server_address, NexusRendezvousHandler)
    print("🚀 [Nexus Hub v2200] Online na porta 8500 com mapeamento dinâmico de NAT.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Hub encerrado.")
