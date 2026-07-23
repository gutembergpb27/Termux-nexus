"""Comando doctor da CLI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from nexus import __version__
from nexus.client import NexusClient
from nexus.exceptions import NexusClientError


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Exibe o diagnostico em formato JSON.",
    )
    parser.add_argument(
        "--url",
        help="URL opcional do endpoint /status do runtime.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Atualiza continuamente o diagnostico.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Intervalo entre atualizacoes em segundos.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Limpa a tela antes de cada atualizacao no modo watch.",
    )
    parser.set_defaults(handler=run)


def check_write_permission(directory: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix=".nexus-doctor-",
            delete=True,
        ):
            return True
    except OSError:
        return False


def collect_diagnostics() -> dict[str, Any]:
    working_dir = Path.cwd()
    writable = check_write_permission(working_dir)

    checks = {
        "python": {
            "status": "OK",
            "version": platform.python_version(),
        },
        "working_directory": {
            "path": str(working_dir),
            "status": "OK" if writable else "ERROR",
            "writable": writable,
        },
    }

    overall_status = (
        "OK"
        if all(check["status"] == "OK" for check in checks.values())
        else "ERROR"
    )

    return {
        "checks": checks,
        "executable": sys.executable,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": overall_status,
        "version": __version__,
        "working_dir": str(working_dir),
    }


def endpoint_url(status_url: str, endpoint: str) -> str:
    base_url = status_url.removesuffix("/status").rstrip("/")
    return f"{base_url}/{endpoint}"


def collect_runtime_status(
    url: str,
    client: NexusClient | None = None,
) -> dict[str, Any]:
    runtime_client = client or NexusClient()
    return runtime_client.status(url)


def add_runtime_diagnostics(
    diagnostics: dict[str, Any],
    url: str,
) -> dict[str, Any] | None:
    client = NexusClient()
    health_url = endpoint_url(url, "health")
    cluster_url = endpoint_url(url, "cluster")

    try:
        runtime = client.status(url)
        health = client.health(health_url)
        cluster = client.cluster(cluster_url)
    except NexusClientError as exc:
        diagnostics["checks"]["runtime"] = {
            "status": "ERROR",
            "url": url,
            "error": str(exc),
        }
        diagnostics["status"] = "ERROR"
        return None

    diagnostics["checks"]["runtime"] = {
        "status": "OK",
        "url": url,
        "node_id": runtime.get("node_id"),
        "role": runtime.get("role"),
        "runtime_status": runtime.get("status"),
        "height": runtime.get("height"),
        "term": runtime.get("term"),
    }
    diagnostics["checks"]["health"] = {
        "status": "OK" if health.get("healthy") else "ERROR",
        "url": health_url,
        "healthy": health.get("healthy"),
        "storage_valid": health.get("storage", {}).get("valid"),
    }
    diagnostics["checks"]["cluster"] = {
        "status": "OK",
        "url": cluster_url,
        "leader": cluster.get("leader"),
        "followers": cluster.get("followers", []),
        "nodes": cluster.get("nodes"),
    }

    if diagnostics["checks"]["health"]["status"] != "OK":
        diagnostics["status"] = "ERROR"

    diagnostics["runtime"] = runtime
    diagnostics["health"] = health
    diagnostics["cluster"] = cluster

    return runtime


def print_runtime(runtime: dict[str, Any]) -> None:
    print()
    print("Runtime:")
    print(f"[ OK ] Node ID: {runtime.get('node_id', 'desconhecido')}")
    print(f"[ OK ] Role: {runtime.get('role', 'desconhecido')}")
    print(
        "[ OK ] Runtime status: "
        f"{runtime.get('status', 'desconhecido')}"
    )
    print(f"[ OK ] Height: {runtime.get('height', 'desconhecido')}")
    print(f"[ OK ] Term: {runtime.get('term', 'desconhecido')}")


def print_health(health: dict[str, Any]) -> None:
    storage = health.get("storage", {})

    print()
    print("Health:")
    print(f"[ OK ] Healthy: {health.get('healthy', 'desconhecido')}")
    print(
        "[ OK ] Storage valid: "
        f"{storage.get('valid', 'desconhecido')}"
    )


def print_cluster(cluster: dict[str, Any]) -> None:
    followers = cluster.get("followers", [])
    followers_text = ", ".join(followers) if followers else "nenhum"

    print()
    print("Cluster:")
    print(f"[ OK ] Leader: {cluster.get('leader', 'desconhecido')}")
    print(f"[ OK ] Followers: {followers_text}")
    print(f"[ OK ] Nodes: {cluster.get('nodes', 'desconhecido')}")


def print_runtime_error(runtime_check: dict[str, Any]) -> None:
    print()
    print("Runtime:")
    print(f"[ERROR] {runtime_check['error']}")


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def run_once(args: argparse.Namespace) -> int:
    diagnostics = collect_diagnostics()
    runtime = None

    if args.url:
        runtime = add_runtime_diagnostics(diagnostics, args.url)

    if args.json_output:
        print(json.dumps(diagnostics, sort_keys=True))
        return 0 if diagnostics["status"] == "OK" else 1

    print("Nexus Runtime Platform Doctor")
    print("=============================")
    print()
    print(f"CLI Version : {diagnostics['version']}")
    print(f"Python      : {diagnostics['python']}")
    print(f"Platform    : {diagnostics['platform']}")
    print(f"Executable  : {diagnostics['executable']}")
    print(f"Working Dir : {diagnostics['working_dir']}")
    print()
    print("Checks:")
    print(
        "[ OK ] Python "
        f"{diagnostics['checks']['python']['version']}"
    )

    working_directory = diagnostics["checks"]["working_directory"]
    marker = " OK " if working_directory["writable"] else "ERROR"
    print(
        f"[{marker}] Working directory writable: "
        f"{working_directory['writable']}"
    )

    if runtime is not None:
        print_runtime(runtime)
        print_health(diagnostics["health"])
        print_cluster(diagnostics["cluster"])
    elif args.url:
        print_runtime_error(diagnostics["checks"]["runtime"])

    print()
    print(f"Status: {diagnostics['status']}")

    return 0 if diagnostics["status"] == "OK" else 1


def run(args: argparse.Namespace) -> int:
    if not args.watch:
        return run_once(args)

    try:
        while True:
            if args.clear:
                clear_screen()
            run_once(args)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
