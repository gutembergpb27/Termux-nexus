"""Interface oficial de linha de comando do Nexus."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from nexus import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexus",
        description="Nexus Runtime Platform CLI",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    version_parser = subparsers.add_parser(
        "version",
        help="Exibe a versão da plataforma.",
    )
    version_parser.set_defaults(handler=show_version)

    return parser


def show_version(_: argparse.Namespace) -> int:
    print(f"Nexus Runtime Platform v{__version__}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
