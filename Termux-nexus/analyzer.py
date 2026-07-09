import csv
import os
import math

CSV_FILE = "benchmarks_edge.csv"

def load_latencies():
    latencies = []
    if not os.path.exists(CSV_FILE):
        print(f"❌ Erro: Arquivo '{CSV_FILE}' não encontrado. Execute 'collect_benchmarks.py' primeiro.")
        return latencies

    with open(CSV_FILE, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["event_type"] == "RECOVERY_EVENT":
                try:
                    latencies.append(float(row["recovery_latency_ms"]))
                except ValueError:
                    continue
    return latencies

def calculate_statistics():
    latencies = load_latencies()
    if not latencies:
        print("⚠️ Sem amostras de mitigação suficientes no CSV para calcular estatísticas.")
        return

    latencies.sort()
    n = len(latencies)
    
    avg_latency = sum(latencies) / n
    min_latency = latencies[0]
    max_latency = latencies[-1]
    
    variance = sum((x - avg_latency) ** 2 for x in latencies) / n
    std_dev = math.sqrt(variance)
    
    p95 = latencies[max(0, min(n - 1, int(math.ceil(n * 0.95)) - 1))]
    p99 = latencies[max(0, min(n - 1, int(math.ceil(n * 0.99)) - 1))]

    print("\n" + "="*50)
    print("🔬 ANÁLISE ESTATÍSTICA DE RESILIÊNCIA - NEXUS v600")
    print("="*50)
    print(f"Amostras de Falhas Analisadas : {n}")
    print(f"Latência Mínima de Resposta  : {min_latency:.2f} ms")
    print(f"Latência Média (MFTR)         : {avg_latency:.2f} ms")
    print(f"Desvio Padrão (Jitter)        : {std_dev:.2f} ms")
    print(f"Latência de Cauda p95         : {p95:.2f} ms")
    print(f"Latência de Cauda p99 (Worst) : {p99:.2f} ms")
    print("="*50 + "\n")

if __name__ == "__main__":
    calculate_statistics()
