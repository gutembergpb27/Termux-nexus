"""Cooperative cancellation primitives for Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from nexus.compute.task_completion import TaskCompletionRegistry


@dataclass(frozen=True, slots=True)
class CancellationToken:
    """Read-only cooperative cancellation view for a task."""

    task_id: str
    completions: TaskCompletionRegistry
    deadline: float | None = None

    @property
    def cancelled(self) -> bool:
        completion = self.completions.get(
            self.task_id
        )

        return (
            completion is not None
            and completion.status == "cancelled"
        )

    @property
    def expired(self) -> bool:
        return (
            self.deadline is not None
            and monotonic() >= self.deadline
        )

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskCancelledError(
                f"task cancelled: {self.task_id}"
            )

        if self.expired:
            raise TaskDeadlineExceededError(
                f"task deadline exceeded: {self.task_id}"
            )


class TaskCancelledError(RuntimeError):
    """Raised by cooperative handlers after cancellation."""


class TaskDeadlineExceededError(RuntimeError):
    """Raised when a cooperative task deadline expires."""
