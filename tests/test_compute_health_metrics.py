from __future__ import annotations

from nexus.compute import (
    BackendCapabilities,
    BackendHealth,
    BackendMetrics,
    BackendRegistry,
    BackendScheduler,
    ComputeBackend,
    ComputeResult,
    ComputeTask,
    LocalBackend,
)


class FakeBackend(ComputeBackend):
    def __init__(
        self,
        name: str,
        *,
        capabilities: BackendCapabilities,
        health: BackendHealth,
        metrics: BackendMetrics,
    ) -> None:
        self.name = name
        self._capabilities = capabilities
        self._health = health
        self._metrics = metrics

    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def health(self) -> BackendHealth:
        return self._health

    def metrics(self) -> BackendMetrics:
        return self._metrics

    def run(self, task: ComputeTask) -> ComputeResult:
        return ComputeResult(
            task_id=task.task_id,
            backend=self.name,
            status="completed",
            output=None,
            duration_seconds=0.0,
        )


def test_backend_metrics_calculates_success_rate() -> None:
    metrics = BackendMetrics(
        completed_runs=8,
        failed_runs=2,
    )

    assert metrics.total_runs == 10
    assert metrics.success_rate == 0.8


def test_backend_metrics_calculates_average_latency() -> None:
    metrics = BackendMetrics(
        completed_runs=3,
        failed_runs=1,
        total_duration_seconds=2.0,
    )

    assert metrics.average_latency_ms == 500.0


def test_backend_metrics_defaults_are_safe() -> None:
    metrics = BackendMetrics()

    assert metrics.total_runs == 0
    assert metrics.success_rate == 1.0
    assert metrics.average_latency_ms == 0.0


def test_local_backend_updates_metrics_after_run() -> None:
    backend = LocalBackend()
    task = ComputeTask(name="metrics-test")

    before = backend.metrics()
    result = backend.run(task)
    after = backend.metrics()

    assert before.completed_runs == 0
    assert result.status == "completed"
    assert after.completed_runs == 1
    assert after.failed_runs == 0
    assert after.active_runs == 0
    assert after.total_duration_seconds >= 0


def test_local_backend_reports_healthy() -> None:
    health = LocalBackend().health()

    assert health.available is True
    assert health.status == "healthy"
    assert health.message == "local backend operational"


def test_scheduler_ignores_unhealthy_backend() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "unhealthy",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=1,
            ),
            health=BackendHealth(
                available=False,
                status="unavailable",
            ),
            metrics=BackendMetrics(),
        )
    )

    registry.register(
        FakeBackend(
            "healthy",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "healthy"


def test_scheduler_prefers_backend_with_lower_active_load() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "busy",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(
                completed_runs=10,
                active_runs=4,
            ),
        )
    )

    registry.register(
        FakeBackend(
            "idle",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(
                completed_runs=10,
                active_runs=0,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "idle"


def test_scheduler_prefers_lower_observed_latency() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "slow",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
                estimated_latency_ms=1.0,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(
                completed_runs=2,
                total_duration_seconds=0.2,
            ),
        )
    )

    registry.register(
        FakeBackend(
            "fast",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
                estimated_latency_ms=100.0,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(
                completed_runs=2,
                total_duration_seconds=0.01,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "fast"


def test_selection_reason_contains_dynamic_metrics() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "local",
            capabilities=BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
            health=BackendHealth(
                available=True,
                status="healthy",
            ),
            metrics=BackendMetrics(
                completed_runs=4,
                failed_runs=1,
                active_runs=2,
                queued_tasks=3,
                total_duration_seconds=0.05,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert "dynamic auto policy" in selection.reason
    assert "active_runs=2" in selection.reason
    assert "queued_tasks=3" in selection.reason
    assert "success_rate=0.8" in selection.reason
