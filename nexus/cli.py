"""Interface oficial de linha de comando do Nexus."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from nexus.commands import version


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
        help="Exibe a vers?o da plataforma.",
    )
    version.configure_parser(version_parser)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
