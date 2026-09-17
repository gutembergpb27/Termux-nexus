"""Atomic persistence for Nexus Compute completion state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nexus.compute.task_completion import TaskCompletionRegistry


class TaskCompletionStore:
    """Persist and recover TaskCompletionRegistry state atomically."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(
        self,
        registry: TaskCompletionRegistry,
    ) -> None:
        state = registry.export_state()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path = self.path.with_name(
            f"{self.path.name}.tmp"
        )

        payload = json.dumps(
            state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        try:
            with temp_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temp_path,
                self.path,
            )

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def load(self) -> TaskCompletionRegistry:
        if not self.path.exists():
            return TaskCompletionRegistry()

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                state: Any = json.load(handle)

        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid task completion state JSON"
            ) from exc

        return TaskCompletionRegistry.restore_state(
            state
        )
