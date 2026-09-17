from __future__ import annotations

import pytest

from nexus.compute import (
    BackendCapabilities,
    BackendRegistry,
    BackendScheduler,
    ComputeBackend,
    ComputeRequirements,
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


def test_gpu_requirement_selects_gpu_backend() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "cpu",
            BackendCapabilities(
                compute_type="cpu",
                priority=10,
            ),
        )
    )

    registry.register(
        FakeBackend(
            "gpu",
            BackendCapabilities(
                compute_type="gpu",
                priority=20,
                has_gpu=True,
            ),
        )
    )

    selection = BackendScheduler(registry).select(
        "auto",
        requirements=ComputeRequirements(
            requires_gpu=True,
        ),
    )

    assert selection.selected == "gpu"


def test_compute_type_filter() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "cpu",
            BackendCapabilities(compute_type="cpu"),
        )
    )

    registry.register(
        FakeBackend(
            "cluster",
            BackendCapabilities(compute_type="cluster"),
        )
    )

    selection = BackendScheduler(registry).select(
        "auto",
        requirements=ComputeRequirements(
            compute_type="cluster",
        ),
    )

    assert selection.selected == "cluster"


def test_memory_requirement() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "small",
            BackendCapabilities(
                compute_type="cpu",
                memory_mb=2048,
            ),
        )
    )

    registry.register(
        FakeBackend(
            "large",
            BackendCapabilities(
                compute_type="cpu",
                memory_mb=16384,
            ),
        )
    )

    selection = BackendScheduler(registry).select(
        "auto",
        requirements=ComputeRequirements(
            min_memory_mb=4096,
        ),
    )

    assert selection.selected == "large"


def test_no_backend_matches() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "cpu",
            BackendCapabilities(
                compute_type="cpu",
            ),
        )
    )

    with pytest.raises(RuntimeError, match="no backend satisfies"):
        BackendScheduler(registry).select(
            "auto",
            requirements=ComputeRequirements(
                compute_type="gpu",
            ),
        )


def test_explicit_backend_must_satisfy_requirements() -> None:
    registry = BackendRegistry()

    registry.register(
        FakeBackend(
            "cpu",
            BackendCapabilities(
                compute_type="cpu",
            ),
        )
    )

    with pytest.raises(RuntimeError, match="does not satisfy"):
        BackendScheduler(registry).select(
            "cpu",
            requirements=ComputeRequirements(
                compute_type="gpu",
            ),
        )


def test_default_requirements_are_empty() -> None:
    task = ComputeTask(name="demo")

    assert isinstance(task.requirements, ComputeRequirements)
