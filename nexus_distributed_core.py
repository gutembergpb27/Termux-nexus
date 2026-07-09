import yaml
import time
import json
from flask import Flask, jsonify

# === Carrega configuração do arquivo YAML ===
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

NODE_ID = config.get("node_id", "Node01")
WEB_PORT = config.get("web_port", 5000)
TCP_PORT = config.get("tcp_port", 9090)
ROLE = config.get("role", "MASTER")

# === Inicializa métricas básicas ===
metrics = {
    "node_id": NODE_ID,
    "role": ROLE,
    "status": "ativo",
    "timestamp": time.time(),
    "payloads_total": 0
}

# Salva métricas em arquivo JSON
def save_metrics():
    with open("metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)

save_metrics()

# === Servidor Flask para observabilidade ===
app = Flask(__name__)

@app.route("/metrics")
def get_metrics():
    with open("metrics.json") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/heartbeat")
def heartbeat():
    return jsonify({
        "node_id": NODE_ID,
        "role": ROLE,
        "heartbeat": "ok" if metrics["status"] == "ativo" else "falho",
        "timestamp": time.time()
    })

# Endpoint Prometheus
@app.route("/prometheus")
def prometheus():
    return (
        f'nexus_payloads_total {metrics["payloads_total"]}\n'
        f'nexus_status{{node_id="{NODE_ID}"}} {1 if metrics["status"]=="ativo" else 0}\n'
    )

# Simulador de falha
@app.route("/simulate_fail")
def simulate_fail():
    metrics["status"] = "falho"
    save_metrics()
    return jsonify({"message": "Nó marcado como falho", "node_id": NODE_ID})

# Simulador de recuperação
@app.route("/simulate_recover")
def simulate_recover():
    metrics["status"] = "ativo"
    save_metrics()
    return jsonify({"message": "Nó recuperado", "node_id": NODE_ID})

if __name__ == "__main__":
    print(f"Nexus iniciado como {ROLE} ({NODE_ID}) na porta {WEB_PORT}")
    app.run(host="0.0.0.0", port=WEB_PORT)
