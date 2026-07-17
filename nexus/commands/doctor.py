"""Comando doctor da CLI."""

from __future__ import annotations

import argparse


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(handler=run)


def run(_: argparse.Namespace) -> int:
    print("Nexus Runtime Platform Doctor")
    print("=============================")
    print("Em desenvolvimento...")

    return 0
