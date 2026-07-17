"""Comando doctor da CLI."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from nexus import __version__


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(handler=run)


def run(_: argparse.Namespace) -> int:
    print("Nexus Runtime Platform Doctor")
    print("=============================")
    print()
    print(f"CLI Version : {__version__}")
    print(f"Python      : {platform.python_version()}")
    print(f"Platform    : {platform.platform()}")
    print(f"Executable  : {sys.executable}")
    print(f"Working Dir : {Path.cwd()}")
    print()
    print("Status: OK")

    return 0
