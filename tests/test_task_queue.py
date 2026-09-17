from __future__ import annotations

import pytest

from nexus.compute import ComputeTask
from nexus.compute.task_queue import TaskQueue


def test_task_queue_starts_empty() -> None:
    queue = TaskQueue()

    assert len(queue) == 0
    assert queue.pending_count() == 0


def test_task_queue_enqueues_task() -> None:
    queue = TaskQueue()
    task = ComputeTask(name="echo")

    queue.enqueue(task)

    assert len(queue) == 1
    assert queue.pending_count() == 1


def test_task_queue_dequeues_in_fifo_order() -> None:
    queue = TaskQueue()

    first = ComputeTask(name="first")
    second = ComputeTask(name="second")

    queue.enqueue(first)
    queue.enqueue(second)

    assert queue.dequeue() is first
    assert queue.dequeue() is second
    assert queue.pending_count() == 0


def test_task_queue_rejects_dequeue_when_empty() -> None:
    queue = TaskQueue()

    with pytest.raises(
        RuntimeError,
        match="task queue is empty",
    ):
        queue.dequeue()


def test_task_queue_rejects_non_compute_task() -> None:
    queue = TaskQueue()

    with pytest.raises(
        TypeError,
        match="ComputeTask",
    ):
        queue.enqueue("invalid")


def test_task_queue_snapshot_is_isolated() -> None:
    queue = TaskQueue()

    first = ComputeTask(name="first")
    second = ComputeTask(name="second")

    queue.enqueue(first)
    queue.enqueue(second)

    snapshot = queue.snapshot()

    assert snapshot == (
        first,
        second,
    )

    assert queue.pending_count() == 2
