import urllib.request
import json
import time

def run_stress_test(target_url, total_requests):
    print("🚀 [Agente de Carga] Iniciando bombardeio de estresse...")
    print(f"🎯 Alvo: {target_url} | Volume: {total_requests} transações contínuas\n")
    success_count = 0
    total_latency_ms = 0.0
    global_start = time.time()
    
    for i in range(total_requests):
        payload = {"data": f"benchmark_payload_automatico_v1800_tx_{i}"}
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(target_url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=2.0) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                if res_body.get("status") == "COMMITTED":
                    success_count += 1
                    total_latency_ms += res_body.get("latency_ms", 0.0)
        except Exception:
            pass
        time.sleep(0.01) # Cadência de segurança para concorrência em hardware mobile
            
    global_duration = time.time() - global_start
    tps = success_count / global_duration if global_duration > 0 else 0
    avg_latency = total_latency_ms / success_count if success_count > 0 else 0
    
    print("-" * 55)
    print("📊 RESULTADO DO BENCHMARK CIENTÍFICO (NEXUS v1800)")
    print("-" * 55)
    print(f"⏱️  Duração Total do Teste:   {global_duration:.2f} segundos")
    print(f"📦 Transações Confirmadas:  {success_count}/{total_requests}")
    print(f"⚡ Throughput Médio (Vazão): {tps:.2f} TPS (Transações/Seg)")
    print(f"📶 Latência Média Interna:  {avg_latency:.2f} ms por consenso")
    print("-" * 55)

if __name__ == "__main__":
    # Testando primeiro na porta 9090 (Nó 1). Se falhar, mude para 9090.
    run_stress_test("http://127.0.0.1:9090/inject", 100)
