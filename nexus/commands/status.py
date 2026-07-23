"""Comando status da CLI."""

from __future__ import annotations

import argparse
import json

from nexus.client import NexusClient
from nexus.exceptions import NexusClientError


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8081/status",
        help="URL do endpoint /status.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Exibe a resposta em JSON.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    client = NexusClient()

    try:
        payload = client.status(args.url)
    except NexusClientError as exc:
        print(f"Erro ao consultar o Nexus: {exc}")
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    print("Nexus Runtime Platform")
    print("----------------------")
    print(f"Node: {payload.get('node_id', 'desconhecido')}")
    print(f"Role: {payload.get('role', 'desconhecido')}")
    print(f"Status: {payload.get('status', 'desconhecido')}")
    print(f"Height: {payload.get('height', 'desconhecido')}")
    print(f"Term: {payload.get('term', 'desconhecido')}")

    return 0
