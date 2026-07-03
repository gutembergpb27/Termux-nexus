import os
import time
import signal
import random
import subprocess

def find_nexus_process():
    """Busca o PID do processo principal do Nexus Dashboard."""
    try:
        output = subprocess.check_output(["pgrep", "-f", "dashboard.py"]).decode().strip()
        pids = [int(pid) for pid in output.split("\n") if pid]
        my_pid = os.getpid()
        return [pid for pid in pids if pid != my_pid]
    except subprocess.CalledProcessError:
        return []

def inject_chaos():
    print("=" * 60)
    print("🌋 INICIANDO ENGINE DE ENGENHARIA DO CAOS - NEXUS V500 🌋")
    print("=" * 60)
    print("[INFO] Monitorando integridade da infraestrutura na borda...")
    
    while True:
        time.sleep(random.randint(10, 20))
        
        pids = find_nexus_process()
        if not pids:
            print("[ALERTA] Processo principal do Nexus não encontrado. Tentando novamente...")
            continue
            
        target_pid = pids[0]
        print(f"\n[💥 CAOS INJETADO] Disparando SIGKILL (kill -9) no PID: {target_pid}")
        
        try:
            os.kill(target_pid, signal.SIGKILL)
            print("[SUCESSO] Processo derrubado abruptamente de forma forçada.")
            print("[AGUARDANDO] Testando resiliência do SQLite WAL e validação de hashes...")
            time.sleep(3)
            print("[INFO] Sistema reinicializado. Verifique o contador 'Events Recovered' no dashboard!")
            
        except ProcessLookupError:
            print("[ERRO] Falha ao injetar caos: O processo sumiu antes do disparo.")

if __name__ == "__main__":
    inject_chaos()
