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
    running: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class TaskExecutionObservability:
    """Snapshot agregado da execucao de tarefas compute."""

    running_tasks: int = 0
    long_running_tasks: int = 0
    max_running_elapsed: float = 0.0

    def __post_init__(self) -> None:
        if self.running_tasks < 0:
            raise ValueError(
                "running_tasks must be non-negative"
            )

        if self.long_running_tasks < 0:
            raise ValueError(
                "long_running_tasks must be non-negative"
            )

        if self.long_running_tasks > self.running_tasks:
            raise ValueError(
                "long_running_tasks must not exceed running_tasks"
            )

        if self.max_running_elapsed < 0:
            raise ValueError(
                "max_running_elapsed must be non-negative"
            )


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
            "running",
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

        if self.status == "running":
            if self.result is not None:
                raise ValueError(
                    "running task must not contain result"
                )

            if self.error is not None:
                raise ValueError(
                    "running task must not contain error"
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
    def running(
        cls,
        *,
        task_id: str,
    ) -> "TaskCompletion":
        return cls(
            task_id=task_id,
            status="running",
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
        self._started_at: dict[str, float] = {}
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

    def start(
        self,
        task_id: str,
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
                    "task completion cannot start"
                )

            completion = TaskCompletion.running(
                task_id=key,
            )

            self._items[key] = completion
            self._started_at[key] = monotonic()
            self._condition.notify_all()

        return completion

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

            if current.status not in {
                "pending",
                "running",
            }:
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

            if current.status not in {
                "pending",
                "running",
            }:
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

    def execution_elapsed(
        self,
        task_id: str,
    ) -> float | None:
        """Retorna o tempo de execucao observado da tarefa."""
        key = str(task_id).strip()

        with self._condition:
            if key not in self._items:
                raise KeyError(
                    "unknown task completion"
                )

            started_at = self._started_at.get(
                key
            )

            if started_at is None:
                return None

            finished_at = self._finished_at.get(
                key
            )

            if finished_at is not None:
                return max(
                    0.0,
                    finished_at - started_at,
                )

            return max(
                0.0,
                monotonic() - started_at,
            )

    def running_over(
        self,
        max_elapsed: float,
    ) -> dict[str, float]:
        """Retorna tarefas running acima do limite informado."""
        threshold = float(max_elapsed)

        if threshold < 0:
            raise ValueError(
                "max_elapsed must be non-negative"
            )

        with self._condition:
            now = monotonic()
            result: dict[str, float] = {}

            for task_id, completion in self._items.items():
                if completion.status != "running":
                    continue

                started_at = self._started_at.get(
                    task_id
                )

                if started_at is None:
                    continue

                elapsed = max(
                    0.0,
                    now - started_at,
                )

                if elapsed > threshold:
                    result[task_id] = elapsed

            return result

    def execution_observability(
        self,
        max_elapsed: float,
    ) -> TaskExecutionObservability:
        """Retorna observabilidade agregada das tarefas running."""
        threshold = float(max_elapsed)

        if threshold < 0:
            raise ValueError(
                "max_elapsed must be non-negative"
            )

        with self._condition:
            now = monotonic()

            running_tasks = 0
            long_running_tasks = 0
            max_running_elapsed = 0.0

            for task_id, completion in self._items.items():
                if completion.status != "running":
                    continue

                started_at = self._started_at.get(
                    task_id
                )

                if started_at is None:
                    continue

                elapsed = max(
                    0.0,
                    now - started_at,
                )

                running_tasks += 1

                if elapsed > max_running_elapsed:
                    max_running_elapsed = elapsed

                if elapsed > threshold:
                    long_running_tasks += 1

            return TaskExecutionObservability(
                running_tasks=running_tasks,
                long_running_tasks=long_running_tasks,
                max_running_elapsed=max_running_elapsed,
            )

    def snapshot(
        self,
    ) -> TaskCompletionSnapshot:
        with self._condition:
            pending = 0
            running = 0
            completed = 0
            failed = 0

            for completion in self._items.values():
                if completion.status == "pending":
                    pending += 1
                elif completion.status == "running":
                    running += 1
                elif completion.status == "completed":
                    completed += 1
                elif completion.status == "failed":
                    failed += 1

            return TaskCompletionSnapshot(
                pending=pending,
                running=running,
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

                self._started_at.pop(
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
