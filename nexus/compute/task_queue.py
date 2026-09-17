"""Fila FIFO thread-safe para tarefas Nexus Compute."""

from __future__ import annotations

from collections import deque
from threading import RLock

from nexus.compute.task import ComputeTask


class TaskQueue:
    """Mantém tarefas pendentes em ordem FIFO."""

    def __init__(self) -> None:
        self._tasks: deque[ComputeTask] = deque()
        self._lock = RLock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._tasks)

    def enqueue(self, task: ComputeTask) -> None:
        if not isinstance(task, ComputeTask):
            raise TypeError(
                "task must be a ComputeTask"
            )

        with self._lock:
            self._tasks.append(task)

    def dequeue(self) -> ComputeTask:
        with self._lock:
            if not self._tasks:
                raise RuntimeError(
                    "task queue is empty"
                )

            return self._tasks.popleft()

    def snapshot(self) -> tuple[ComputeTask, ...]:
        with self._lock:
            return tuple(self._tasks)
