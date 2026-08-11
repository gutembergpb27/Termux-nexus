from __future__ import annotations

import pytest

from nexus.compute.node_load import NodeLoad


def test_node_load_defaults_are_safe() -> None:
    load = NodeLoad()

    assert load.active_tasks == 0
    assert load.queued_tasks == 0
    assert load.completed_tasks == 0
    assert load.failed_tasks == 0
    assert load.average_duration_ms == 0.0


def test_node_load_accepts_valid_snapshot() -> None:
    load = NodeLoad(
        active_tasks=2,
        queued_tasks=3,
        completed_tasks=10,
        failed_tasks=1,
        average_duration_ms=12.5,
    )

    assert load.active_tasks == 2
    assert load.queued_tasks == 3
    assert load.completed_tasks == 10
    assert load.failed_tasks == 1
    assert load.average_duration_ms == 12.5


@pytest.mark.parametrize(
    "field",
    [
        "active_tasks",
        "queued_tasks",
        "completed_tasks",
        "failed_tasks",
    ],
)
def test_node_load_rejects_negative_counters(
    field: str,
) -> None:
    values = {
        "active_tasks": 0,
        "queued_tasks": 0,
        "completed_tasks": 0,
        "failed_tasks": 0,
    }

    values[field] = -1

    with pytest.raises(
        ValueError,
        match="greater than or equal to zero",
    ):
        NodeLoad(**values)


def test_node_load_rejects_negative_average_duration() -> None:
    with pytest.raises(
        ValueError,
        match="duration",
    ):
        NodeLoad(
            average_duration_ms=-1.0,
        )


def test_node_load_serializes_to_wire_snapshot() -> None:
    load = NodeLoad(
        active_tasks=1,
        queued_tasks=2,
        completed_tasks=8,
        failed_tasks=1,
        average_duration_ms=25.0,
    )

    assert load.to_dict() == {
        "active_tasks": 1,
        "queued_tasks": 2,
        "completed_tasks": 8,
        "failed_tasks": 1,
        "average_duration_ms": 25.0,
    }
