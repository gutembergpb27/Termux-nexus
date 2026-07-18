"""Comando doctor da CLI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from nexus import __version__


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Exibe o diagnostico em formato JSON.",
    )
    parser.set_defaults(handler=run)


def check_write_permission(directory: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix=".nexus-doctor-",
            delete=True,
        ):
            return True
    except OSError:
        return False


def collect_diagnostics() -> dict[str, Any]:
    working_dir = Path.cwd()
    writable = check_write_permission(working_dir)

    checks = {
        "python": {
            "status": "OK",
            "version": platform.python_version(),
        },
        "working_directory": {
            "path": str(working_dir),
            "status": "OK" if writable else "ERROR",
            "writable": writable,
        },
    }

    overall_status = (
        "OK"
        if all(check["status"] == "OK" for check in checks.values())
        else "ERROR"
    )

    return {
        "checks": checks,
        "executable": sys.executable,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": overall_status,
        "version": __version__,
        "working_dir": str(working_dir),
    }


def run(args: argparse.Namespace) -> int:
    diagnostics = collect_diagnostics()

    if args.json_output:
        print(json.dumps(diagnostics, sort_keys=True))
        return 0 if diagnostics["status"] == "OK" else 1

    print("Nexus Runtime Platform Doctor")
    print("=============================")
    print()
    print(f"CLI Version : {diagnostics['version']}")
    print(f"Python      : {diagnostics['python']}")
    print(f"Platform    : {diagnostics['platform']}")
    print(f"Executable  : {diagnostics['executable']}")
    print(f"Working Dir : {diagnostics['working_dir']}")
    print()
    print("Checks:")
    print(
        "[ OK ] Python "
        f"{diagnostics['checks']['python']['version']}"
    )

    working_directory = diagnostics["checks"]["working_directory"]
    marker = " OK " if working_directory["writable"] else "ERROR"
    print(
        f"[{marker}] Working directory writable: "
        f"{working_directory['writable']}"
    )

    print()
    print(f"Status: {diagnostics['status']}")

    return 0 if diagnostics["status"] == "OK" else 1
