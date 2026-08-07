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
