"""Comando doctor da CLI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from nexus import __version__


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Exibe o diagnostico em formato JSON.",
    )
    parser.set_defaults(handler=run)


def collect_diagnostics() -> dict[str, str]:
    return {
        "executable": sys.executable,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": "OK",
        "version": __version__,
        "working_dir": str(Path.cwd()),
    }


def run(args: argparse.Namespace) -> int:
    diagnostics = collect_diagnostics()

    if args.json_output:
        print(json.dumps(diagnostics, sort_keys=True))
        return 0

    print("Nexus Runtime Platform Doctor")
    print("=============================")
    print()
    print(f"CLI Version : {diagnostics['version']}")
    print(f"Python      : {diagnostics['python']}")
    print(f"Platform    : {diagnostics['platform']}")
    print(f"Executable  : {diagnostics['executable']}")
    print(f"Working Dir : {diagnostics['working_dir']}")
    print()
    print(f"Status: {diagnostics['status']}")

    return 0
