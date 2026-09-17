from __future__ import annotations

import pytest

from nexus.compute import (
    BackendRegistry,
    ComputeRuntime,
    ComputeTask,
    LocalBackend,
)


def test_compute_task_requires_name() -> None:
    with pytest.raises(ValueError, match="task name"):
        ComputeTask(name="   ")


def test_registry_registers_and_lists_backends() -> None:
    registry = BackendRegistry()
    registry.register(LocalBackend())

    assert registry.names() == ("local",)
    assert registry.get("local").name == "local"


def test_registry_rejects_duplicate_backend() -> None:
    registry = BackendRegistry()
    registry.register(LocalBackend())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(LocalBackend())


def test_runtime_executes_local_task() -> None:
    runtime = ComputeRuntime()
    task = ComputeTask(
        name="echo",
        payload={"value": 42},
    )

    result = runtime.run(task)

    assert result.task_id == task.task_id
    assert result.backend == "local"
    assert result.status == "completed"
    assert result.output == {
        "name": "echo",
        "payload": {"value": 42},
    }
    assert result.duration_seconds >= 0


def test_runtime_rejects_unknown_backend() -> None:
    runtime = ComputeRuntime()
    task = ComputeTask(name="example")

    with pytest.raises(KeyError, match="unknown backend"):
        runtime.run(task, backend="quantum")
