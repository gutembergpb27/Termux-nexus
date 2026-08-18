"""Cooperative cancellation primitives for Nexus Compute."""

from __future__ import annotations

from dataclasses import dataclass

from nexus.compute.task_completion import TaskCompletionRegistry


@dataclass(frozen=True, slots=True)
class CancellationToken:
    """Read-only cooperative cancellation view for a task."""

    task_id: str
    completions: TaskCompletionRegistry

    @property
    def cancelled(self) -> bool:
        completion = self.completions.get(
            self.task_id
        )

        return (
            completion is not None
            and completion.status == "cancelled"
        )

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TaskCancelledError(
                f"task cancelled: {self.task_id}"
            )


class TaskCancelledError(RuntimeError):
    """Raised by cooperative handlers after cancellation."""
