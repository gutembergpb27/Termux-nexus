"""Explicit ownership contract for distributed Compute tasks."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class TaskOwnership:
    """Identifies the node currently owning a logical task execution."""

    task_id: str
    node_id: str

    def __post_init__(self) -> None:
        task_id = str(self.task_id).strip()
        node_id = str(self.node_id).strip()

        if not task_id:
            raise ValueError("task id must not be empty")

        if not node_id:
            raise ValueError("node id must not be empty")

        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "node_id", node_id)


class TaskOwnershipRegistry:
    """Tracks exclusive in-flight ownership of distributed tasks."""

    def __init__(self) -> None:
        self._items: dict[str, TaskOwnership] = {}
        self._lock = RLock()

    def claim(
        self,
        task_id: str,
        node_id: str,
    ) -> TaskOwnership:
        ownership = TaskOwnership(
            task_id=task_id,
            node_id=node_id,
        )

        with self._lock:
            existing = self._items.get(
                ownership.task_id
            )

            if existing is not None:
                raise RuntimeError(
                    "task already owned: "
                    f"{ownership.task_id} -> "
                    f"{existing.node_id}"
                )

            self._items[
                ownership.task_id
            ] = ownership

            return ownership

    def owner(
        self,
        task_id: str,
    ) -> str | None:
        key = str(task_id).strip()

        if not key:
            raise ValueError(
                "task id must not be empty"
            )

        with self._lock:
            ownership = self._items.get(key)

            if ownership is None:
                return None

            return ownership.node_id

    def release(
        self,
        task_id: str,
        node_id: str,
    ) -> None:
        key = str(task_id).strip()
        owner = str(node_id).strip()

        if not key:
            raise ValueError(
                "task id must not be empty"
            )

        if not owner:
            raise ValueError(
                "node id must not be empty"
            )

        with self._lock:
            existing = self._items.get(key)

            if existing is None:
                raise RuntimeError(
                    f"task is not owned: {key}"
                )

            if existing.node_id != owner:
                raise RuntimeError(
                    "task ownership mismatch: "
                    f"{key} is owned by "
                    f"{existing.node_id}, not {owner}"
                )

            del self._items[key]

    def snapshot(
        self,
    ) -> dict[str, str]:
        with self._lock:
            return {
                task_id: ownership.node_id
                for task_id, ownership
                in self._items.items()
            }