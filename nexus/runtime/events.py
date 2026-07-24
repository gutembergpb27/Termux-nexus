"""Runtime event management."""

from __future__ import annotations


class RuntimeEvents:
    """Simple in-memory runtime event registry."""

    def __init__(self) -> None:
        self._events: list[dict[str, object]] = []

    def publish(self, event: str, **payload: object) -> dict[str, object]:
        record = {
            "event": event,
            "payload": payload,
        }

        self._events.append(record)
        return record

    def history(self) -> list[dict[str, object]]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()

    def count(self) -> int:
        return len(self._events)
