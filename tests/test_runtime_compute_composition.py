from __future__ import annotations

from nexus import RuntimeClient
from nexus.compute import (
    ComputeRuntime,
    ComputeTask,
)
from nexus.runtime import Runtime
from nexus.runtime_observability import RuntimeObservability


def test_runtime_client_exposes_compute_runtime() -> None:
    client = RuntimeClient()

    assert isinstance(
        client.compute,
        ComputeRuntime,
    )


def test_runtime_client_compute_instance_is_stable() -> None:
    client = RuntimeClient()

    assert client.compute is client.compute


def test_runtime_client_accepts_external_compute_runtime() -> None:
    compute = ComputeRuntime()

    client = RuntimeClient(
        compute=compute,
    )

    assert client.compute is compute


def test_runtime_observability_exposes_same_compute_runtime_state() -> None:
    client = RuntimeClient()

    task = ComputeTask(
        name="runtime-client-compute",
    )

    result = client.compute.run(task)

    compute_snapshot = (
        client.observability.compute()
    )

    assert compute_snapshot is not None

    completion = client.compute.completions.get(
        task.task_id
    )

    assert completion is not None
    assert completion.status == "completed"
    assert completion.result == result

    assert (
        compute_snapshot["completions"].completed
        == 1
    )

    assert (
        compute_snapshot["completions"].total
        == 1
    )

    assert (
        compute_snapshot["execution"].running_tasks
        == 0
    )


def test_runtime_observability_without_compute_remains_supported() -> None:
    runtime = Runtime()

    observability = RuntimeObservability(
        runtime
    )

    assert observability.compute() is None


def test_runtime_observability_snapshot_contract_is_unchanged() -> None:
    client = RuntimeClient()

    snapshot = client.observability.snapshot()

    assert snapshot == {
        "health": client.health(),
        "metrics": client.metrics(),
        "diagnostics": client.diagnostics(),
        "telemetry": client.telemetry(),
    }

    assert "compute" not in snapshot


def test_runtime_client_compute_and_observability_share_registry() -> None:
    client = RuntimeClient()

    before = client.observability.compute()

    assert before is not None
    assert before["completions"].total == 0

    task = ComputeTask(
        name="shared-compute-registry",
    )

    client.compute.run(task)

    after = client.observability.compute()

    assert after is not None

    assert after["completions"].completed == 1
    assert after["completions"].total == 1


def test_runtime_lifecycle_remains_independent_from_compute() -> None:
    client = RuntimeClient()

    assert client.started is False

    task = ComputeTask(
        name="compute-does-not-start-runtime",
    )

    client.compute.run(task)

    assert client.started is False
    assert client.status()["state"] == "stopped"
