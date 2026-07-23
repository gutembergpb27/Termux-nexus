"""Comando version da CLI."""

from __future__ import annotations

import argparse

from nexus import __version__


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(handler=run)


def run(_: argparse.Namespace) -> int:
    print(f"Nexus Runtime Platform v{__version__}")
    return 0
