"""Comando peers da CLI."""

from __future__ import annotations

import argparse

from nexus.client import NexusClient
from nexus.exceptions import NexusClientError


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8500/peers",
        help="URL do endpoint /peers do Hub.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    client = NexusClient()

    try:
        payload = client.get_json(args.url)
    except NexusClientError as exc:
        print(f"Erro ao consultar os peers: {exc}")
        return 1

    if not payload:
        print("Nenhum peer registrado.")
        return 0

    print("Peers registrados")
    print("-----------------")

    for node_id, peer in sorted(payload.items()):
        role = peer.get("role", "desconhecido")
        ip = peer.get("ip", "desconhecido")
        web_port = peer.get("web_port", "desconhecido")
        tcp_port = peer.get("tcp_port", "desconhecido")

        print(
            f"{node_id}: role={role} "
            f"ip={ip} web={web_port} tcp={tcp_port}"
        )

    return 0
