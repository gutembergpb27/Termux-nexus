from __future__ import annotations

import pytest

from nexus.compute import (
    BackendCapabilities,
    BackendRegistry,
    BackendScheduler,
    ComputeBackend,
    ComputeResult,
    ComputeTask,
)


class FakeBackend(ComputeBackend):
    def __init__(
        self,
        name: str,
        capabilities: BackendCapabilities,
        *,
        available: bool = True,
    ) -> None:
        self.name = name
        self._capabilities = capabilities
        self._available = available

    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def is_available(self) -> bool:
        return self._available

    def run(self, task: ComputeTask) -> ComputeResult:
        return ComputeResult(
            task_id=task.task_id,
            backend=self.name,
            status="completed",
            output=None,
            duration_seconds=0.0,
        )


def test_capabilities_validate_reliability() -> None:
    with pytest.raises(ValueError, match="reliability"):
        BackendCapabilities(
            compute_type="cpu",
            reliability=1.1,
        )


def test_scheduler_ignores_unavailable_backend() -> None:
    registry = BackendRegistry()
    registry.register(
        FakeBackend(
            "fast-unavailable",
            BackendCapabilities(
                compute_type="gpu",
                priority=1,
            ),
            available=False,
        )
    )
    registry.register(
        FakeBackend(
            "local",
            BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "local"


def test_scheduler_prefers_lower_priority_value() -> None:
    registry = BackendRegistry()
    registry.register(
        FakeBackend(
            "slow",
            BackendCapabilities(
                compute_type="cpu",
                priority=20,
            ),
        )
    )
    registry.register(
        FakeBackend(
            "preferred",
            BackendCapabilities(
                compute_type="gpu",
                priority=5,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "preferred"


def test_scheduler_uses_latency_as_tiebreaker() -> None:
    registry = BackendRegistry()
    registry.register(
        FakeBackend(
            "high-latency",
            BackendCapabilities(
                compute_type="cpu",
                priority=10,
                estimated_latency_ms=100.0,
            ),
        )
    )
    registry.register(
        FakeBackend(
            "low-latency",
            BackendCapabilities(
                compute_type="cpu",
                priority=10,
                estimated_latency_ms=5.0,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert selection.selected == "low-latency"


def test_scheduler_rejects_explicit_unavailable_backend() -> None:
    registry = BackendRegistry()
    registry.register(
        FakeBackend(
            "offline",
            BackendCapabilities(compute_type="cluster"),
            available=False,
        )
    )

    with pytest.raises(RuntimeError, match="backend unavailable"):
        BackendScheduler(registry).select("offline")


def test_selection_reason_contains_metrics() -> None:
    registry = BackendRegistry()
    registry.register(
        FakeBackend(
            "local",
            BackendCapabilities(
                compute_type="cpu",
                priority=10,
                estimated_latency_ms=1.0,
                estimated_cost=0.0,
                reliability=1.0,
            ),
        )
    )

    selection = BackendScheduler(registry).select("auto")

    assert "priority=10" in selection.reason
    assert "latency_ms=1.0" in selection.reason
    assert "reliability=1.0" in selection.reason
