import json
import os
import subprocess
import sys
import time
import urllib.request


SECRET = "demo-secret"
HUB_URL = "http://127.0.0.1:8500"


def wait_for_peers(expected, timeout=15):
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{HUB_URL}/peers", timeout=2) as response:
                peers = json.loads(response.read().decode("utf-8"))
                if len(peers) >= expected:
                    return peers
        except Exception:
            pass

        time.sleep(0.5)

    raise RuntimeError(f"timeout aguardando {expected} peers")


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

        print("PASS: Hub, registro e heartbeat operando com 2 nós")

    finally:
        for process in reversed(processes):
            process.terminate()

        for process in reversed(processes):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
