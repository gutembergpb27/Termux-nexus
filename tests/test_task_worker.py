from __future__ import annotations

from nexus.compute import (
    ComputeTask,
    TaskQueue,
    build_default_task_registry,
)
from nexus.compute.task_worker import TaskWorker


def test_worker_executes_single_queued_task() -> None:
    queue = TaskQueue()
    registry = build_default_task_registry()

    queue.enqueue(
        ComputeTask(
            name="echo",
            payload={"value": 42},
        )
    )

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    result = worker.run_once()

    assert result == {"value": 42}
    assert queue.pending_count() == 0

    metrics = registry.metrics("echo")

    assert metrics.runs == 1
    assert metrics.successes == 1


def test_worker_returns_none_when_queue_is_empty() -> None:
    worker = TaskWorker(
        queue=TaskQueue(),
        registry=build_default_task_registry(),
    )

    assert worker.run_once() is None


def test_worker_preserves_fifo_execution() -> None:
    queue = TaskQueue()
    calls = []

    registry = build_default_task_registry()

    registry.register(
        "track",
        lambda payload: (
            calls.append(payload["value"])
            or payload["value"]
        ),
    )

    queue.enqueue(
        ComputeTask(
            name="track",
            payload={"value": 1},
        )
    )

    queue.enqueue(
        ComputeTask(
            name="track",
            payload={"value": 2},
        )
    )

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    assert worker.run_once() == 1
    assert worker.run_once() == 2

    assert calls == [1, 2]
    assert queue.pending_count() == 0


def test_worker_runs_until_queue_is_empty() -> None:
    queue = TaskQueue()
    calls = []

    registry = build_default_task_registry()

    registry.register(
        "track_all",
        lambda payload: (
            calls.append(payload["value"])
            or payload["value"]
        ),
    )

    for value in (1, 2, 3):
        queue.enqueue(
            ComputeTask(
                name="track_all",
                payload={"value": value},
            )
        )

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    results = worker.run_until_empty()

    assert results == [1, 2, 3]
    assert calls == [1, 2, 3]
    assert queue.pending_count() == 0


def test_worker_starts_and_stops_background_loop() -> None:
    import time

    queue = TaskQueue()
    registry = build_default_task_registry()

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    assert worker.running is False

    assert worker.start() is True
    assert worker.running is True

    time.sleep(0.02)

    assert worker.stop(timeout=1.0) is True
    assert worker.running is False


def test_worker_start_is_idempotent() -> None:
    worker = TaskWorker(
        queue=TaskQueue(),
        registry=build_default_task_registry(),
    )

    assert worker.start() is True
    assert worker.start() is False

    assert worker.stop(timeout=1.0) is True


def test_worker_stop_when_not_running_returns_false() -> None:
    worker = TaskWorker(
        queue=TaskQueue(),
        registry=build_default_task_registry(),
    )

    assert worker.stop(timeout=1.0) is False


def test_background_worker_consumes_task_enqueued_after_start() -> None:
    import time

    queue = TaskQueue()
    completed = []

    registry = build_default_task_registry()

    registry.register(
        "background_track",
        lambda payload: (
            completed.append(payload["value"])
            or payload["value"]
        ),
    )

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    assert worker.start() is True

    queue.enqueue(
        ComputeTask(
            name="background_track",
            payload={"value": 42},
        )
    )

    deadline = time.time() + 1.0

    while (
        not completed
        and time.time() < deadline
    ):
        time.sleep(0.01)

    assert completed == [42]
    assert queue.pending_count() == 0

    metrics = registry.metrics(
        "background_track"
    )

    assert metrics.runs == 1
    assert metrics.successes == 1

    assert worker.stop(timeout=1.0) is True
    assert worker.running is False


def test_background_worker_continues_after_task_failure() -> None:
    import time

    queue = TaskQueue()
    completed = []

    registry = build_default_task_registry()

    def failing_handler(payload):
        raise RuntimeError("boom")

    registry.register(
        "background_fail",
        failing_handler,
    )

    registry.register(
        "background_success",
        lambda payload: (
            completed.append(payload["value"])
            or payload["value"]
        ),
    )

    worker = TaskWorker(
        queue=queue,
        registry=registry,
    )

    assert worker.start() is True

    queue.enqueue(
        ComputeTask(
            name="background_fail",
            payload={"value": 1},
        )
    )

    queue.enqueue(
        ComputeTask(
            name="background_success",
            payload={"value": 2},
        )
    )

    deadline = time.time() + 1.0

    while (
        not completed
        and time.time() < deadline
    ):
        time.sleep(0.01)

    assert completed == [2]
    assert queue.pending_count() == 0
    assert worker.running is True

    failed_metrics = registry.metrics(
        "background_fail"
    )

    success_metrics = registry.metrics(
        "background_success"
    )

    assert failed_metrics.runs == 1
    assert failed_metrics.failures == 1

    assert success_metrics.runs == 1
    assert success_metrics.successes == 1

    assert worker.stop(timeout=1.0) is True
    assert worker.running is False
