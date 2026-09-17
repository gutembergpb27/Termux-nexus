"""Formal readiness contract for the Nexus Runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexus.runtime.engine import Runtime


class RuntimeReadiness:
    """Report whether a Runtime is ready to accept work."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    def check(self) -> dict[str, object]:
        """Return the structured readiness state."""

        if not self._runtime.started:
            return {
                "ready": False,
                "reason": "runtime_not_started",
            }

        return {
            "ready": True,
            "reason": "runtime_operational",
        }

    def summary(self) -> dict[str, object]:
        """Return the compact readiness state."""
        return self.check()