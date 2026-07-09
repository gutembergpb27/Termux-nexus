import urllib.request
import json
import time

def monitor():
    while True:
        try:
            # Pega a lista de peers do Hub
            with urllib.request.urlopen("http://192.168.1.20:8500/peers") as res:
                data = json.loads(res.read())
                print(f"\n--- Status da Malha (v2200) ---")
                for node, info in data.items():
                    print(f"Nó: {node} | IP: {info['ip']} | Status: OK")
        except:
            print("Hub fora do ar ou rede instável...")
        time.sleep(5)

monitor()
