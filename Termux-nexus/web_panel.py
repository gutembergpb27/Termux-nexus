from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading

# Referência global para expor os dados do supervisor sem travar o escopo
_supervisor_instance = None

class MetricsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return # Silencia os logs de requisição no terminal para não poluir o monitor do Core

    def do_GET(self):
        global _supervisor_instance
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            # Monta o snapshot de telemetria atual do sistema
            metrics = {
                "status": "OPERATIONAL",
                "engine_version": "Nexus v1000 (SRE Production)",
                "active_workers_count": len(_supervisor_instance.workers) if _supervisor_instance else 0,
                "workers": [w_id for w_id in _supervisor_instance.workers.keys()] if _supervisor_instance else [],
                "last_chain_hash": _supervisor_instance.persistence.last_hash if _supervisor_instance else "N/A"
            }
            
            self.wfile.write(json.dumps(metrics, indent=2).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_web_server(supervisor_instance, port=9090):
    """Inicializa o servidor HTTP de telemetria em segundo plano."""
    global _supervisor_instance
    _supervisor_instance = supervisor_instance
    
    server = HTTPServer(("0.0.0.0", port), MetricsHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"📊 [Web SRE] Painel de métricas de produção online em: http://localhost:{port}/metrics")
