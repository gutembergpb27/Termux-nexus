from __future__ import annotations

import pytest

from nexus.compute import (
    BackendRegistry,
    BackendScheduler,
    ComputeRuntime,
    ComputeTask,
    LocalBackend,
)


def test_scheduler_selects_local_for_auto() -> None:
    registry = BackendRegistry()
    registry.register(LocalBackend())
    scheduler = BackendScheduler(registry)

    selection = scheduler.select("auto")

    assert selection.requested == "auto"
    assert selection.selected == "local"
    assert "auto policy" in selection.reason


def test_scheduler_preserves_explicit_backend() -> None:
    registry = BackendRegistry()
    registry.register(LocalBackend())
    scheduler = BackendScheduler(registry)

    selection = scheduler.select("local")

    assert selection.requested == "local"
    assert selection.selected == "local"
    assert selection.reason == "explicit backend selection"


def test_scheduler_rejects_empty_selection() -> None:
    registry = BackendRegistry()
    scheduler = BackendScheduler(registry)

    with pytest.raises(ValueError, match="must not be empty"):
        scheduler.select("   ")


def test_scheduler_rejects_auto_without_backends() -> None:
    registry = BackendRegistry()
    scheduler = BackendScheduler(registry)

    with pytest.raises(RuntimeError, match="no backend satisfies task requirements"):
        scheduler.select("auto")


def test_runtime_uses_auto_policy_by_default() -> None:
    runtime = ComputeRuntime()
    task = ComputeTask(name="auto-example", payload={"value": 42})

    result = runtime.run(task)

    assert result.backend == "local"
    assert result.requested_backend == "auto"
    assert result.selection_reason is not None
    assert "auto policy" in result.selection_reason


def test_runtime_preserves_explicit_selection_metadata() -> None:
    runtime = ComputeRuntime()
    task = ComputeTask(name="explicit-example")

    result = runtime.run(task, backend="local")

    assert result.backend == "local"
    assert result.requested_backend == "local"
    assert result.selection_reason == "explicit backend selection"
