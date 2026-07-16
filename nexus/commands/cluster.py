"""Comando cluster da CLI."""

from __future__ import annotations

import argparse

from nexus.client import NexusClient
from nexus.exceptions import NexusClientError


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8081/cluster",
        help="URL do endpoint /cluster.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    client = NexusClient()

    try:
        payload = client.get_json(args.url)
    except NexusClientError as exc:
        print(f"Erro ao consultar o cluster: {exc}")
        return 1

    followers = payload.get("followers", [])
    followers_text = ", ".join(followers) if followers else "nenhum"

    print("Nexus Cluster")
    print("-------------")
    print(f"Status: {payload.get('status', 'desconhecido')}")
    print(f"Leader: {payload.get('leader', 'desconhecido')}")
    print(f"Nodes: {payload.get('nodes', 'desconhecido')}")
    print(f"Followers: {followers_text}")

    return 0
