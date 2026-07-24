"""Runtime health inspection."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Runtime


def _get_runtime_version() -> str:
    """Return the installed Nexus Runtime Platform version."""
    try:
        return version("nexus-runtime-platform")
    except PackageNotFoundError:
        return "2500.0.0-dev"


class RuntimeHealth:
    """Provide structured health information for a Runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def check(self) -> dict[str, object]:
        """Return a structured health report."""
        runtime_status = self._runtime.status()

        return {
            "healthy": self._runtime.started,
            "runtime": runtime_status,
            "python": platform.python_version(),
            "platform": platform.system(),
            "version": _get_runtime_version(),
            "executable": sys.executable,
        }

    def summary(self) -> dict[str, object]:
        """Return a compact health summary."""
        report = self.check()
        runtime_status = report["runtime"]

        if not isinstance(runtime_status, dict):
            raise TypeError("runtime status must be a dictionary")

        return {
            "healthy": report["healthy"],
            "state": runtime_status["state"],
            "version": report["version"],
        }