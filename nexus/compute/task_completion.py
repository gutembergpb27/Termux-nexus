"""Contrato de conclusão de tarefas Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, RLock
from time import monotonic
from typing import Any


@dataclass(frozen=True, slots=True)
class TaskCompletionSnapshot:
    """Snapshot observ?vel das conclus?es mantidas no registry."""

    pending: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


@dataclass(frozen=True)
class TaskCompletion:
    """Representa o estado final ou pendente de uma tarefa compute."""

    task_id: str
    status: str
    result: Any = None
    error: str | None = None

    def __post_init__(self) -> None:
        task_id = str(self.task_id).strip()

        if not task_id:
            raise ValueError(
                "task id must not be empty"
            )

        object.__setattr__(
            self,
            "task_id",
            task_id,
        )

        if self.status not in {
            "pending",
            "completed",
            "failed",
        }:
            raise ValueError(
                "invalid task completion status"
            )

        if self.status == "completed":
            if self.error is not None:
                raise ValueError(
                    "completed task must not contain error"
                )

        if self.status == "failed":
            if not str(self.error or "").strip():
                raise ValueError(
                    "failed task must contain error"
                )

            if self.result is not None:
                raise ValueError(
                    "failed task must not contain result"
                )

        if self.status == "pending":
            if self.result is not None:
                raise ValueError(
                    "pending task must not contain result"
                )

            if self.error is not None:
                raise ValueError(
                    "pending task must not contain error"
                )

    @classmethod
    def pending(
        cls,
        *,
        task_id: str,
    ) -> "TaskCompletion":
        return cls(
            task_id=task_id,
            status="pending",
        )

    @classmethod
    def completed(
        cls,
        *,
        task_id: str,
        result: Any,
    ) -> "TaskCompletion":
        return cls(
            task_id=task_id,
            status="completed",
            result=result,
        )

    @classmethod
    def failed(
        cls,
        *,
        task_id: str,
        error: str,
    ) -> "TaskCompletion":
        return cls(
            task_id=task_id,
            status="failed",
            error=str(error),
        )


class TaskCompletionRegistry:
    """Mantém e sinaliza conclusões de tarefas por task_id."""

    def __init__(self) -> None:
        self._items: dict[str, TaskCompletion] = {}
        self._finished_at: dict[str, float] = {}
        self._lock = RLock()
        self._condition = Condition(self._lock)

    def create(
        self,
        task_id: str,
    ) -> TaskCompletion:
        completion = TaskCompletion.pending(
            task_id=task_id,
        )

        with self._condition:
            if completion.task_id in self._items:
                raise ValueError(
                    "task completion already exists"
                )

            self._items[completion.task_id] = completion
            self._condition.notify_all()

        return completion

    def get(
        self,
        task_id: str,
    ) -> TaskCompletion | None:
        key = str(task_id).strip()

        with self._condition:
            return self._items.get(key)

    def complete(
        self,
        task_id: str,
        result: Any,
    ) -> TaskCompletion:
        key = str(task_id).strip()

        with self._condition:
            if key not in self._items:
                raise KeyError(
                    "unknown task completion"
                )

            current = self._items[key]

            if current.status != "pending":
                raise ValueError(
                    "task completion already terminal"
                )

            completion = TaskCompletion.completed(
                task_id=key,
                result=result,
            )

            self._items[key] = completion
            self._finished_at[key] = monotonic()
            self._condition.notify_all()

        return completion

    def fail(
        self,
        task_id: str,
        error: str,
    ) -> TaskCompletion:
        key = str(task_id).strip()

        with self._condition:
            if key not in self._items:
                raise KeyError(
                    "unknown task completion"
                )

            current = self._items[key]

            if current.status != "pending":
                raise ValueError(
                    "task completion already terminal"
                )

            completion = TaskCompletion.failed(
                task_id=key,
                error=error,
            )

            self._items[key] = completion
            self._finished_at[key] = monotonic()
            self._condition.notify_all()

        return completion

    def snapshot(
        self,
    ) -> TaskCompletionSnapshot:
        with self._condition:
            pending = 0
            completed = 0
            failed = 0

            for completion in self._items.values():
                if completion.status == "pending":
                    pending += 1
                elif completion.status == "completed":
                    completed += 1
                elif completion.status == "failed":
                    failed += 1

            return TaskCompletionSnapshot(
                pending=pending,
                completed=completed,
                failed=failed,
                total=len(self._items),
            )

    def cleanup(
        self,
        *,
        max_age: float,
    ) -> int:
        age = float(max_age)

        if age < 0:
            raise ValueError(
                "max age must not be negative"
            )

        now = monotonic()

        with self._condition:
            expired = [
                task_id
                for task_id, finished_at
                in self._finished_at.items()
                if now - finished_at >= age
            ]

            for task_id in expired:
                self._items.pop(
                    task_id,
                    None,
                )
                self._finished_at.pop(
                    task_id,
                    None,
                )

            if expired:
                self._condition.notify_all()

            return len(expired)

    def wait(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> TaskCompletion:
        key = str(task_id).strip()

        with self._condition:
            if key not in self._items:
                raise KeyError(
                    "unknown task completion"
                )

            deadline = (
                None
                if timeout is None
                else monotonic() + float(timeout)
            )

            while True:
                completion = self._items[key]

                if completion.status in {
                    "completed",
                    "failed",
                }:
                    return completion

                if deadline is None:
                    self._condition.wait()
                    continue

                remaining = deadline - monotonic()

                if remaining <= 0:
                    raise TimeoutError(
                        "task completion timed out"
                    )

                self._condition.wait(
                    timeout=remaining
                )
