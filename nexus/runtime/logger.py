"""Structured runtime logging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class RuntimeLogger:
    """Store structured runtime log records in memory."""

    def __init__(self) -> None:
        self._records: list[dict[str, object]] = []

    def log(
        self,
        level: LogLevel,
        message: str,
        **context: object,
    ) -> dict[str, object]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "context": context,
        }

        self._records.append(record)
        return record

    def debug(self, message: str, **context: object) -> dict[str, object]:
        return self.log("DEBUG", message, **context)

    def info(self, message: str, **context: object) -> dict[str, object]:
        return self.log("INFO", message, **context)

    def warning(self, message: str, **context: object) -> dict[str, object]:
        return self.log("WARNING", message, **context)

    def error(self, message: str, **context: object) -> dict[str, object]:
        return self.log("ERROR", message, **context)

    def critical(self, message: str, **context: object) -> dict[str, object]:
        return self.log("CRITICAL", message, **context)

    def history(self) -> list[dict[str, object]]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)
