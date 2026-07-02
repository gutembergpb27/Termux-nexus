import os
import subprocess
import time
import random
import json
import statistics

def run_single_experiment(run_id):
    # 1. Limpa os outputs anteriores
    subprocess.run("rm -rf outputs/*", shell=True)
    
    # 2. Inicia o simulador em background
    start_time = time.perf_counter()
    process = subprocess.Popen("python3 test_persistence.py > /dev/null 2>&1", shell=True)
    
    # 3. Aguarda um tempo aleatório para injetar o Caos (entre 200ms e 1500ms)
    chaos_delay = random.uniform(0.2, 1.5)
    time.sleep(chaos_delay)
    
    # 4. Injeta o SIGKILL de forma abrupta
    subprocess.run(f"pkill -9 -f test_persistence.py", shell=True)
    
    # 5. Mede o tempo que o analisador leva para recuperar e auditar
    audit_start = time.perf_counter()
    
    # Executa o analyzer internamente e captura a saída estruturada (se houver)
    # Para coletar os dados de forma limpa, vamos rodar o analisador
    import analyzer
    # Modificamos levemente a chamada para retornar dados para o orquestrador
    base_path = "outputs/nexus_store.db"
    backup_path = f"{base_path}.1"
    
    expected_prev_hash = None
    total_blocks = 0
    global_integrity = True
    
    arquivos = [f for f in [backup_path, base_path] if os.path.exists(f)]
    
    for filepath in arquivos:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    block = json.loads(line)
                    if expected_prev_hash is None:
                        expected_prev_hash = block["prev_hash"]
                    if block["prev_hash"] != expected_prev_hash:
                        global_integrity = False
                    expected_prev_hash = block["hash"]
                    total_blocks += 1
        except Exception:
            global_integrity = False
            
    audit_end = time.perf_counter()
    recovery_time_ms = (audit_end - audit_start) * 1000
    
    # Determina o status da rotação
    rotation_operational = os.path.exists(backup_path)
    
    return {
        "integrity": global_integrity and total_blocks > 0,
        "blocks": total_blocks,
        "recovery_time": recovery_time_ms,
        "rotation": rotation_operational
    }

def main():
    total_runs = 100
    print(f"⚡ Iniciando Suite de Testes Estocásticos (Caos Continúo) - {total_runs} Execuções")
    print("=" * 70)
    
    results = []
    
    for i in range(1, total_runs + 1):
        res = run_single_experiment(i)
        results.append(res)
        if i % 10 == 0:
            print(f"🔄 Progresso: {i}/{total_runs} experimentos concluídos...")
            
    # Processamento Estatístico
    successful_recoveries = sum(1 for r in results if r["integrity"])
    total_blocks_saved = sum(r["blocks"] for r in results)
    recovery_times = [r["recovery_time"] for r in results]
    rotations_triggered = sum(1 for r in results if r["rotation"])
    
    mean_recovery = statistics.mean(recovery_times)
    recovery_times.sort()
    p95_recovery = statistics.quantiles(recovery_times, n=20)[18] # 95th percentile
    p99_recovery = statistics.quantiles(recovery_times, n=100)[98] # 99th percentile
    
    print("\n" + "="*50)
    print("        NEXUS V500 - RELATÓRIO ESTATÍSTICO DE RESILIÊNCIA     ")
    print("="*50)
    print(f"{'Métrica':<35} | {'Resultado':<12}")
    print("-" * 50)
    print(f"{'Execuções Totais':<35} | {total_runs:<12}")
    print(f"{'Recuperações Completas (100% Íntegras)':<35} | {successful_recoveries:<12}")
    print(f"{'Falhas de Cadeia/Corrupção':<35} | {total_runs - successful_recoveries:<12}")
    print(f"{'Total de Blocos Gravados/Recuperados':<35} | {total_blocks_saved:<12}")
    print(f"{'Rotações de Log Operacionais':<35} | {rotations_triggered:<12}")
    print(f"{'Tempo Médio de Recuperação':<35} | {mean_recovery:.2f} ms")
    print(f"{'Latência de Recuperação P95':<35} | {p95_recovery:.2f} ms")
    print(f"{'Latência de Recuperação P99':<35} | {p99_recovery:.2f} ms")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
