import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


_runtime_instance = None


class MetricsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _send_json(self, status, payload):
        body = json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        runtime = _runtime_instance

        if runtime is None:
            self._send_json(503, {"error": "runtime unavailable"})
            return

        if self.path == "/health":
            payload = runtime.runtime_health()
            status = 200 if payload.get("healthy") else 503
            self._send_json(status, payload)
            return

        if self.path == "/status":
            summary = runtime.persistence.state_summary(
                term=getattr(runtime, "term", 0)
            )

            self._send_json(
                200,
                {
                    "status": "OPERATIONAL",
                    "node_id": runtime.node_id,
                    "role": runtime.role,
                    "web_port": runtime.web_port,
                    "tcp_port": runtime.tcp_port,
                    **summary,
                },
            )
            return

        if self.path == "/cluster":
            peers = getattr(runtime, "peers", {})
            leader = next(
                (
                    node_id
                    for node_id, info in peers.items()
                    if info.get("role") == "MASTER"
                ),
                None,
            )
            followers = [
                node_id
                for node_id, info in peers.items()
                if info.get("role") == "FOLLOWER"
            ]

            self._send_json(
                200,
                {
                    "status": "OPERATIONAL",
                    "leader": leader,
                    "followers": followers,
                    "nodes": len(peers),
                    "peers": peers,
                },
            )
            return

        if self.path == "/metrics":
            summary = runtime.persistence.state_summary(
                term=getattr(runtime, "term", 0)
            )

            self._send_json(
                200,
                {
                    "status": "OPERATIONAL",
                    "engine_version": "Nexus Runtime v1.1 RC1",
                    "node_id": runtime.node_id,
                    "role": runtime.role,
                    "height": summary["height"],
                    "tip_hash": summary["tip_hash"],
                    "term": summary["term"],
                },
            )
            return

        self._send_json(404, {"error": "not found"})


def start_web_server(runtime_instance, port):
    global _runtime_instance
    _runtime_instance = runtime_instance

    server = HTTPServer(("0.0.0.0", int(port)), MetricsHTTPHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()
    return server
