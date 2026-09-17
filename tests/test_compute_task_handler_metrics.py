from __future__ import annotations

import pytest

from nexus.compute import (
    TaskHandlerMetrics,
    TaskHandlerRegistry,
    build_default_task_registry,
)


def test_registered_handler_starts_with_zero_metrics() -> None:
    registry = TaskHandlerRegistry()
    registry.register("echo", lambda payload: dict(payload))

    metrics = registry.metrics("echo")

    assert isinstance(metrics, TaskHandlerMetrics)
    assert metrics.runs == 0
    assert metrics.successes == 0
    assert metrics.failures == 0
    assert metrics.average_duration_ms == 0.0
    assert metrics.last_execution_at is None
    assert metrics.last_error is None


def test_successful_execution_updates_metrics() -> None:
    registry = build_default_task_registry()

    registry.execute("echo", {"value": 42})

    metrics = registry.metrics("echo")

    assert metrics.runs == 1
    assert metrics.successes == 1
    assert metrics.failures == 0
    assert metrics.last_execution_at is not None
    assert metrics.last_error is None


def test_multiple_executions_accumulate_metrics() -> None:
    registry = build_default_task_registry()

    registry.execute("echo", {"run": 1})
    registry.execute("echo", {"run": 2})
    registry.execute("echo", {"run": 3})

    metrics = registry.metrics("echo")

    assert metrics.runs == 3
    assert metrics.successes == 3
    assert metrics.failures == 0


def test_failed_execution_updates_failure_metrics() -> None:
    registry = build_default_task_registry()

    with pytest.raises(ValueError):
        registry.execute(
            "data_transform",
            {
                "operation": "invalid",
                "values": [1, 2, 3],
            },
        )

    metrics = registry.metrics("data_transform")

    assert metrics.runs == 1
    assert metrics.failures == 1
    assert metrics.successes == 0
    assert metrics.last_error is not None
    assert "ValueError" in metrics.last_error


def test_success_after_failure_clears_last_error() -> None:
    registry = build_default_task_registry()

    with pytest.raises(ValueError):
        registry.execute(
            "data_transform",
            {
                "operation": "invalid",
                "values": [1],
            },
        )

    registry.execute(
        "data_transform",
        {
            "operation": "double",
            "values": [21],
        },
    )

    metrics = registry.metrics("data_transform")

    assert metrics.runs == 2
    assert metrics.failures == 1
    assert metrics.successes == 1
    assert metrics.last_error is None


def test_metrics_snapshot_contains_all_handlers() -> None:
    registry = build_default_task_registry()

    registry.execute("echo", {"value": 1})

    snapshot = registry.metrics_snapshot()

    assert tuple(snapshot) == (
        "data_transform",
        "echo",
        "matrix_multiply",
    )
    assert snapshot["echo"].runs == 1
    assert snapshot["data_transform"].runs == 0
    assert snapshot["matrix_multiply"].runs == 0


def test_metrics_reject_unknown_handler() -> None:
    registry = TaskHandlerRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task handler",
    ):
        registry.metrics("missing")


def test_core_node_load_snapshot_aggregates_handler_metrics() -> None:
    from nexus_distributed_core import NexusDistributedCore

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()

    core.compute_task_handlers.execute(
        "echo",
        {"value": 1},
    )

    core.compute_task_handlers.execute(
        "echo",
        {"value": 2},
    )

    load = core.compute_node_load()

    assert load.completed_tasks == 2
    assert load.failed_tasks == 0
    assert load.active_tasks == 0
    assert load.queued_tasks == 0
    assert load.average_duration_ms >= 0.0


def test_core_node_load_snapshot_counts_failed_handler_execution() -> None:
    from nexus_distributed_core import NexusDistributedCore

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = TaskHandlerRegistry()

    def failing_handler(payload):
        raise RuntimeError("boom")

    core.compute_task_handlers.register(
        "failing",
        failing_handler,
    )

    core.compute_task_handlers.register(
        "working",
        lambda payload: dict(payload),
    )

    core.compute_task_handlers.execute(
        "working",
        {"value": 1},
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        core.compute_task_handlers.execute(
            "failing",
            {"value": 2},
        )

    load = core.compute_node_load()

    assert load.completed_tasks == 1
    assert load.failed_tasks == 1
    assert load.active_tasks == 0
    assert load.queued_tasks == 0
    assert load.average_duration_ms >= 0.0


def test_registry_reports_active_execution() -> None:
    import threading

    registry = TaskHandlerRegistry()

    started = threading.Event()
    release = threading.Event()

    def blocking_handler(payload):
        started.set()
        release.wait(timeout=2)
        return dict(payload)

    registry.register(
        "blocking",
        blocking_handler,
    )

    result_holder = {}

    def run_handler():
        result_holder["value"] = registry.execute(
            "blocking",
            {"value": 1},
        )

    thread = threading.Thread(
        target=run_handler,
    )

    thread.start()

    assert started.wait(timeout=1)

    snapshot = registry.load_snapshot()

    assert snapshot.active_tasks == 1
    assert snapshot.queued_tasks == 0

    release.set()
    thread.join(timeout=2)

    assert thread.is_alive() is False

    final = registry.load_snapshot()

    assert final.active_tasks == 0
    assert final.completed_tasks == 1
    assert final.failed_tasks == 0
    assert result_holder["value"] == {
        "value": 1,
    }


def test_core_node_load_reports_real_queued_tasks() -> None:
    from nexus.compute import ComputeTask, TaskQueue
    from nexus_distributed_core import NexusDistributedCore

    core = object.__new__(NexusDistributedCore)
    core.compute_task_handlers = build_default_task_registry()
    core.compute_task_queue = TaskQueue()

    core.compute_task_queue.enqueue(
        ComputeTask(name="echo")
    )

    core.compute_task_queue.enqueue(
        ComputeTask(name="data_transform")
    )

    load = core.compute_node_load()

    assert load.active_tasks == 0
    assert load.queued_tasks == 2
