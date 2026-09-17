"""Public execution observability facade for Nexus Compute."""

from __future__ import annotations

from nexus.compute.task_completion import (
    TaskCompletionRegistry,
    TaskCompletionSnapshot,
    TaskExecutionObservability,
)


class ComputeExecutionObservability:
    """Expose task execution observability for Nexus Compute."""

    def __init__(
        self,
        completions: TaskCompletionRegistry,
    ) -> None:
        self._completions = completions

    def execution(
        self,
        *,
        max_elapsed: float = 30.0,
    ) -> TaskExecutionObservability:
        """Return aggregated task execution observability."""

        return self._completions.execution_observability(
            max_elapsed
        )

    def completions(self) -> TaskCompletionSnapshot:
        """Return the task completion registry snapshot."""

        return self._completions.snapshot()

    def snapshot(
        self,
        *,
        max_elapsed: float = 30.0,
    ) -> dict[str, object]:
        """Return a consolidated Compute execution snapshot."""

        return {
            "execution": self.execution(
                max_elapsed=max_elapsed,
            ),
            "completions": self.completions(),
        }
