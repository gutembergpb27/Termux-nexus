import subprocess
import time
import sys

def launch_cluster():
    print("🌐 [Cluster Orchestrator] Inicializando Malha Virtual v1400...")
    ports = [8080, 8081, 8082]
    processes = []

    try:
        for i, port in enumerate(ports):
            # Define o papel inicial: o primeiro nó será o Master candidato, os outros serão Followers
            role = "MASTER" if i == 0 else "FOLLOWER"
            print(f"🚀 Lançando Nó {i} na porta {port} como [{role}]...")
            
            # Executa o core passando argumentos de inicialização dinâmicos
            p = subprocess.Popen([sys.executable, "nexus_v500_core.py", str(port), role])
            processes.append(p)
            time.sleep(1.0) # Janela para evitar colisão de subida

        print("✅ [v1400] Todos os nós virtuais inicializados em background. Pressione CTRL+C para derrubar o cluster.")
        
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 [Cluster Orchestrator] Encerrando todos os nós da malha de forma controlada...")
        for p in processes:
            p.terminate()
            p.wait()
        print("🧹 Cluster finalizado com sucesso.")

if __name__ == "__main__":
    launch_cluster()
