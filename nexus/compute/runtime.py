"""Runtime inicial da camada Nexus Compute."""

from __future__ import annotations

from time import monotonic

from dataclasses import replace

from nexus.compute.cancellation import CancellationToken
from nexus.compute.completion_store import TaskCompletionStore
from nexus.compute.backend import ComputeBackend
from nexus.compute.local import LocalBackend
from nexus.compute.observability import ComputeExecutionObservability
from nexus.compute.registry import BackendRegistry
from nexus.compute.result import ComputeResult
from nexus.compute.retry import RetryPolicy
from nexus.compute.scheduler import BackendScheduler
from nexus.compute.task import ComputeTask
from nexus.compute.task_ownership import StaleTaskOwnershipError
from nexus.compute.task_completion import TaskCompletionRegistry


class ComputeRuntime:
    """Coordena registro, seleção e execução de backends."""

    def __init__(
        self,
        registry: BackendRegistry | None = None,
        *,
        additional_backends: tuple[ComputeBackend, ...] = (),
        completions: TaskCompletionRegistry | None = None,
        completion_store: TaskCompletionStore | None = None,
    ) -> None:
        self.registry = registry or BackendRegistry()

        if completions is not None and completion_store is not None:
            raise ValueError(
                "completions and completion_store are mutually exclusive"
            )

        self._completion_store = completion_store

        if completion_store is not None:
            self.completions = completion_store.load()
        elif completions is not None:
            self.completions = completions
        else:
            self.completions = TaskCompletionRegistry()

        self.observability = ComputeExecutionObservability(
            self.completions
        )

        if "local" not in self.registry.names():
            self.registry.register(LocalBackend())

        for backend in additional_backends:
            if backend.name not in self.registry.names():
                self.registry.register(backend)

        self.scheduler = BackendScheduler(self.registry)

    def _persist_if_configured(self) -> None:
        """Persiste completions quando um store estiver configurado."""

        if self._completion_store is None:
            return

        self._completion_store.save(
            self.completions
        )

    def persist(self) -> None:
        """Persiste explicitamente o estado atual de completions."""

        if self._completion_store is None:
            raise RuntimeError(
                "completion store is not configured"
            )

        self._completion_store.save(
            self.completions
        )

    def health(self) -> dict[str, object]:
        """Retorna um snapshot operacional do subsistema Compute."""

        snapshot = self.completions.snapshot()

        return {
            "healthy": True,
            "pending": snapshot.pending,
            "running": snapshot.running,
            "completed": snapshot.completed,
            "failed": snapshot.failed,
            "cancelled": snapshot.cancelled,
            "total": snapshot.total,
        }

    def cancellation_token(
        self,
        task_id: str,
        *,
        deadline: float | None = None,
        timeout: float | None = None,
    ) -> CancellationToken:
        """Retorna um token cooperativo para uma tarefa conhecida."""

        if self.completions.get(task_id) is None:
            raise KeyError(
                "unknown task completion"
            )

        if deadline is not None and timeout is not None:
            raise ValueError(
                "deadline and timeout are mutually exclusive"
            )

        if timeout is not None:
            if timeout < 0:
                raise ValueError(
                    "timeout must be non-negative"
                )

            deadline = monotonic() + timeout

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

        completion = self.completions.cancel(
            task_id
        )

        self._persist_if_configured()

        return completion

    def run(
        self,
        task: ComputeTask,
        *,
        backend: str = "auto",
        retry: RetryPolicy | None = None,
        idempotent: bool = False,
    ) -> ComputeResult:
        existing = self.completions.get(
            task.task_id
        )

        if existing is not None:
            if not idempotent:
                raise ValueError(
                    f"task completion already exists: {task.task_id}"
                )

            if existing.status == "completed":
                if not isinstance(existing.result, ComputeResult):
                    raise RuntimeError(
                        "completed task does not contain a ComputeResult"
                    )

                return existing.result

            if existing.status == "failed":
                raise RuntimeError(
                    existing.error or "task execution previously failed"
                )

            if existing.status == "cancelled":
                raise RuntimeError(
                    existing.error or "task execution was cancelled"
                )

            raise RuntimeError(
                f"task execution already in progress: {task.task_id}"
            )

        self.completions.create(
            task.task_id
        )

        self._persist_if_configured()

        self.completions.start(
            task.task_id
        )

        self._persist_if_configured()

        policy = retry or RetryPolicy()

        for attempt in range(1, policy.max_attempts + 1):
            selected_backend = None

            try:
                selection = self.scheduler.select(
                    backend,
                    requirements=task.requirements,
                )

                selected_backend = self.registry.get(
                    selection.selected
                )

                result = selected_backend.run(task)

                normalized = replace(
                    result,
                    requested_backend=selection.requested,
                    selection_reason=selection.reason,
                )

            except Exception as exc:
                if attempt < policy.max_attempts:
                    continue

                if selected_backend is not None:
                    publish_terminal_failure = getattr(
                        selected_backend,
                        "publish_terminal_failure",
                        None,
                    )
                else:
                    publish_terminal_failure = None

                if (
                    publish_terminal_failure is not None
                    and not isinstance(
                        exc,
                        StaleTaskOwnershipError,
                    )
                ):
                    authoritative_failure = (
                        publish_terminal_failure(
                            task.task_id,
                            exc,
                        )
                    )
                else:
                    authoritative_failure = str(exc)

                self.completions.fail(
                    task.task_id,
                    authoritative_failure,
                )

                self._persist_if_configured()

                raise

            self.completions.complete(
                task.task_id,
                normalized,
            )

            self._persist_if_configured()

            return normalized

        raise RuntimeError(
            "retry execution completed without terminal result"
        )
