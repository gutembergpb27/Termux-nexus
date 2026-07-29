"""Runtime tracing."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class RuntimeTracing:
    """Simple in-memory runtime tracing."""

    def __init__(self) -> None:
        self._traces: list[dict[str, object]] = []

    def begin(self, operation: str, **context: object) -> dict[str, object]:
        trace = {
            "trace_id": str(uuid4()),
            "operation": operation,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "status": "RUNNING",
            "context": context,
        }

        self._traces.append(trace)
        return trace

    def finish(self, trace_id: str) -> bool:
        for trace in self._traces:
            if trace["trace_id"] == trace_id:
                trace["finished_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                trace["status"] = "FINISHED"
                return True

        return False

    def history(self) -> list[dict[str, object]]:
        return list(self._traces)

    def clear(self) -> None:
        self._traces.clear()

    def count(self) -> int:
        return len(self._traces)
