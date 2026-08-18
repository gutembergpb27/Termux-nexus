"""Runtime inicial da camada Nexus Compute."""

from __future__ import annotations

from dataclasses import replace

from nexus.compute.cancellation import CancellationToken
from nexus.compute.backend import ComputeBackend
from nexus.compute.local import LocalBackend
from nexus.compute.observability import ComputeExecutionObservability
from nexus.compute.registry import BackendRegistry
from nexus.compute.result import ComputeResult
from nexus.compute.scheduler import BackendScheduler
from nexus.compute.task import ComputeTask
from nexus.compute.task_completion import TaskCompletionRegistry


class ComputeRuntime:
    """Coordena registro, seleção e execução de backends."""

    def __init__(
        self,
        registry: BackendRegistry | None = None,
        *,
        additional_backends: tuple[ComputeBackend, ...] = (),
        completions: TaskCompletionRegistry | None = None,
    ) -> None:
        self.registry = registry or BackendRegistry()
        self.completions = completions or TaskCompletionRegistry()
        self.observability = ComputeExecutionObservability(
            self.completions
        )

        if "local" not in self.registry.names():
            self.registry.register(LocalBackend())

        for backend in additional_backends:
            if backend.name not in self.registry.names():
                self.registry.register(backend)

        self.scheduler = BackendScheduler(self.registry)

    def cancellation_token(
        self,
        task_id: str,
        *,
        deadline: float | None = None,
    ) -> CancellationToken:
        """Retorna um token cooperativo para uma tarefa conhecida."""

        if self.completions.get(task_id) is None:
            raise KeyError(
                "unknown task completion"
            )

        return CancellationToken(
            task_id=task_id,
            completions=self.completions,
            deadline=deadline,
        )

    def cancel(
        self,
        task_id: str,
    ):
        """Cancela logicamente uma tarefa pending ou running."""

        return self.completions.cancel(
            task_id
        )

    def run(
        self,
        task: ComputeTask,
        *,
        backend: str = "auto",
    ) -> ComputeResult:
        self.completions.create(
            task.task_id
        )

        self.completions.start(
            task.task_id
        )

        try:
            selection = self.scheduler.select(
                backend,
                requirements=task.requirements,
            )

            result = self.registry.get(
                selection.selected
            ).run(task)

            normalized = replace(
                result,
                requested_backend=selection.requested,
                selection_reason=selection.reason,
            )

        except Exception as exc:
            self.completions.fail(
                task.task_id,
                str(exc),
            )
            raise

        self.completions.complete(
            task.task_id,
            normalized,
        )

        return normalized
