import json
import os
import subprocess
import sys
import time
import urllib.request


SECRET = "demo-secret"
HUB_URL = "http://127.0.0.1:8500"


def get_peers():
    with urllib.request.urlopen(f"{HUB_URL}/peers", timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_peers(expected, timeout=15):
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            peers = get_peers()
            if len(peers) >= expected:
                return peers
        except Exception:
            pass

        time.sleep(0.5)

    raise RuntimeError(f"timeout aguardando {expected} peers")


def wait_for_role(node_id, role, timeout=70):
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            peers = get_peers()
            if peers.get(node_id, {}).get("role") == role:
                return peers
        except Exception:
            pass

        time.sleep(1)

    raise RuntimeError(
        f"timeout aguardando {node_id} assumir papel {role}"
    )


def stop_process(process):
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def main():
    env = os.environ.copy()
    env["NEXUS_SECRET_KEY"] = SECRET
    env["NEXUS_HUB_URL"] = HUB_URL

    processes = []

    try:
        hub = subprocess.Popen(
            [sys.executable, "nexus_rendezvous.py"],
            env=env,
        )
        processes.append(hub)
        time.sleep(1)

        node_a = subprocess.Popen(
            [
                sys.executable,
                "nexus_distributed_core.py",
                "NO-DEMO-A",
                "8081",
                "9091",
                "MASTER",
            ],
            env=env,
            stdin=subprocess.DEVNULL,
        )
        processes.append(node_a)

        node_b = subprocess.Popen(
            [
                sys.executable,
                "nexus_distributed_core.py",
                "NO-DEMO-B",
                "8082",
                "9092",
                "FOLLOWER",
            ],
            env=env,
            stdin=subprocess.DEVNULL,
        )
        processes.append(node_b)

        peers = wait_for_peers(2)
        assert peers["NO-DEMO-A"]["role"] == "MASTER"
        assert peers["NO-DEMO-B"]["role"] == "FOLLOWER"

        print("PASS 1: registro e heartbeat operando com 2 nós")
        print("TESTE: encerrando o MASTER NO-DEMO-A...")

        stop_process(node_a)

        peers = wait_for_role("NO-DEMO-B", "MASTER")

        assert "NO-DEMO-A" not in peers
        assert peers["NO-DEMO-B"]["role"] == "MASTER"

        print("PASS 2: follower promovido automaticamente para MASTER")
        print("PASS: demo de registro, heartbeat e failover concluída")

    finally:
        for process in reversed(processes):
            stop_process(process)


if __name__ == "__main__":
    main()
