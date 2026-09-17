"""Explicit ownership contract for distributed Compute tasks."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


class StaleTaskOwnershipError(RuntimeError):
    """Raised when an execution no longer owns its task generation."""


@dataclass(frozen=True, slots=True)
class TaskOwnership:
    """Identifies one generation of distributed task ownership."""

    task_id: str
    node_id: str
    generation: int

    def __post_init__(self) -> None:
        task_id = str(self.task_id).strip()
        node_id = str(self.node_id).strip()

        if not task_id:
            raise ValueError("task id must not be empty")

        if not node_id:
            raise ValueError("node id must not be empty")

        if (
            isinstance(self.generation, bool)
            or not isinstance(self.generation, int)
            or self.generation < 1
        ):
            raise ValueError(
                "ownership generation must be a positive integer"
            )

        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "node_id", node_id)


class TaskOwnershipRegistry:
    """Tracks exclusive, generation-fenced distributed ownership."""

    def __init__(self) -> None:
        self._items: dict[str, TaskOwnership] = {}
        self._generations: dict[str, int] = {}
        self._lock = RLock()

    def claim(
        self,
        task_id: str,
        node_id: str,
    ) -> TaskOwnership:
        key = str(task_id).strip()
        owner = str(node_id).strip()

        if not key:
            raise ValueError("task id must not be empty")

        if not owner:
            raise ValueError("node id must not be empty")

        with self._lock:
            existing = self._items.get(key)

            if existing is not None:
                raise RuntimeError(
                    "task already owned: "
                    f"{key} -> {existing.node_id}"
                )

            generation = self._generations.get(key, 0) + 1

            ownership = TaskOwnership(
                task_id=key,
                node_id=owner,
                generation=generation,
            )

            self._generations[key] = generation
            self._items[key] = ownership

            return ownership

    def ownership(
        self,
        task_id: str,
    ) -> TaskOwnership | None:
        key = str(task_id).strip()

        if not key:
            raise ValueError("task id must not be empty")

        with self._lock:
            return self._items.get(key)

    def owner(
        self,
        task_id: str,
    ) -> str | None:
        ownership = self.ownership(task_id)

        if ownership is None:
            return None

        return ownership.node_id

    def release(
        self,
        task_id: str,
        node_id: str,
        generation: int,
    ) -> None:
        key = str(task_id).strip()
        owner = str(node_id).strip()

        if not key:
            raise ValueError("task id must not be empty")

        if not owner:
            raise ValueError("node id must not be empty")

        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError(
                "ownership generation must be a positive integer"
            )

        with self._lock:
            existing = self._items.get(key)

            if existing is None:
                raise StaleTaskOwnershipError(
                    f"task is not owned: {key}"
                )

            if existing.node_id != owner:
                raise StaleTaskOwnershipError(
                    "task ownership mismatch: "
                    f"{key} is owned by "
                    f"{existing.node_id}, not {owner}"
                )

            if existing.generation != generation:
                raise StaleTaskOwnershipError(
                    "stale task ownership generation: "
                    f"{key} expected "
                    f"{existing.generation}, got {generation}"
                )

            del self._items[key]

    def reclaim_orphaned(
        self,
        *,
        online_nodes: set[str],
    ) -> tuple[TaskOwnership, ...]:
        """Revoke ownership held by nodes outside online membership."""
        online = {
            str(node_id).strip()
            for node_id in online_nodes
            if str(node_id).strip()
        }

        with self._lock:
            reclaimed = tuple(
                ownership
                for ownership in self._items.values()
                if ownership.node_id not in online
            )

            for ownership in reclaimed:
                del self._items[ownership.task_id]

            return reclaimed

    def assert_current(
        self,
        task_id: str,
        node_id: str,
        generation: int,
    ) -> None:
        """Require an ownership generation to still be authoritative."""
        key = str(task_id).strip()
        owner = str(node_id).strip()

        if not key:
            raise ValueError("task id must not be empty")

        if not owner:
            raise ValueError("node id must not be empty")

        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError(
                "ownership generation must be a positive integer"
            )

        with self._lock:
            existing = self._items.get(key)

            if existing is None:
                raise StaleTaskOwnershipError(
                    f"task is not owned: {key}"
                )

            if existing.node_id != owner:
                raise StaleTaskOwnershipError(
                    "task ownership mismatch: "
                    f"{key} is owned by "
                    f"{existing.node_id}, not {owner}"
                )

            if existing.generation != generation:
                raise StaleTaskOwnershipError(
                    "stale task ownership generation: "
                    f"{key} expected "
                    f"{existing.generation}, got {generation}"
                )

    def snapshot(
        self,
    ) -> dict[str, str]:
        with self._lock:
            return {
                task_id: ownership.node_id
                for task_id, ownership
                in self._items.items()
            }
