"""Comando status da CLI."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8081/status",
        help="URL do endpoint /status.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    try:
        with urllib.request.urlopen(args.url, timeout=5) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Erro ao consultar o Nexus: {exc}")
        return 1

    print("Nexus Runtime Platform")
    print("----------------------")
    print(f"Node: {payload.get('node_id', 'desconhecido')}")
    print(f"Role: {payload.get('role', 'desconhecido')}")
    print(f"Status: {payload.get('status', 'desconhecido')}")
    print(f"Height: {payload.get('height', 'desconhecido')}")
    print(f"Term: {payload.get('term', 'desconhecido')}")

    return 0
