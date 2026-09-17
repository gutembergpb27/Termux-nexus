from __future__ import annotations

import pytest

from nexus.compute import (
    TaskHandlerRegistry,
    build_default_task_registry,
)


def test_registry_registers_and_executes_handler() -> None:
    registry = TaskHandlerRegistry()

    registry.register(
        "double",
        lambda payload: {
            "value": payload["value"] * 2,
        },
    )

    assert registry.execute(
        "double",
        {"value": 21},
    ) == {"value": 42}


def test_registry_rejects_duplicate_handler() -> None:
    registry = TaskHandlerRegistry()
    registry.register("echo", lambda payload: payload)

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            "echo",
            lambda payload: payload,
        )


def test_registry_rejects_unknown_handler() -> None:
    registry = TaskHandlerRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task handler",
    ):
        registry.execute("missing", {})


def test_default_registry_contains_builtin_handlers() -> None:
    registry = build_default_task_registry()

    assert registry.names() == (
        "data_transform",
        "echo",
        "matrix_multiply",
    )


def test_data_transform_double() -> None:
    registry = build_default_task_registry()

    result = registry.execute(
        "data_transform",
        {
            "operation": "double",
            "values": [1, 2, 3],
        },
    )

    assert result == {
        "values": [2, 4, 6],
    }


def test_data_transform_square() -> None:
    registry = build_default_task_registry()

    result = registry.execute(
        "data_transform",
        {
            "operation": "square",
            "values": [2, 3, 4],
        },
    )

    assert result == {
        "values": [4, 9, 16],
    }


def test_data_transform_sum() -> None:
    registry = build_default_task_registry()

    result = registry.execute(
        "data_transform",
        {
            "operation": "sum",
            "values": [10, 20, 12],
        },
    )

    assert result == {
        "value": 42,
    }


def test_data_transform_rejects_unknown_operation() -> None:
    registry = build_default_task_registry()

    with pytest.raises(
        ValueError,
        match="unsupported data transform operation",
    ):
        registry.execute(
            "data_transform",
            {
                "operation": "invalid",
                "values": [1, 2],
            },
        )


def test_matrix_multiply_2x2() -> None:
    registry = build_default_task_registry()

    result = registry.execute(
        "matrix_multiply",
        {
            "left": [
                [1, 2],
                [3, 4],
            ],
            "right": [
                [5, 6],
                [7, 8],
            ],
        },
    )

    assert result == {
        "matrix": [
            [19, 22],
            [43, 50],
        ],
    }


def test_matrix_multiply_rectangular() -> None:
    registry = build_default_task_registry()

    result = registry.execute(
        "matrix_multiply",
        {
            "left": [
                [1, 2, 3],
                [4, 5, 6],
            ],
            "right": [
                [7, 8],
                [9, 10],
                [11, 12],
            ],
        },
    )

    assert result == {
        "matrix": [
            [58, 64],
            [139, 154],
        ],
    }


def test_matrix_multiply_rejects_incompatible_dimensions() -> None:
    registry = build_default_task_registry()

    with pytest.raises(
        ValueError,
        match="dimensions are incompatible",
    ):
        registry.execute(
            "matrix_multiply",
            {
                "left": [[1, 2]],
                "right": [[1, 2]],
            },
        )


def test_registry_passes_cancellation_token_to_opt_in_handler() -> None:
    from nexus.compute.cancellation import CancellationToken
    from nexus.compute.handlers import TaskHandlerRegistry
    from nexus.compute.task_completion import TaskCompletionRegistry

    registry = TaskHandlerRegistry()
    completions = TaskCompletionRegistry()

    completions.create("task-token-pass")

    token = CancellationToken(
        task_id="task-token-pass",
        completions=completions,
    )

    received = []

    def handler(payload, *, cancellation_token):
        received.append(cancellation_token)
        return payload["value"]

    registry.register(
        "token-aware",
        handler,
    )

    result = registry.execute(
        "token-aware",
        {"value": 42},
        cancellation_token=token,
    )

    assert result == 42
    assert received == [token]


def test_registry_keeps_legacy_handler_signature() -> None:
    from nexus.compute.handlers import TaskHandlerRegistry

    registry = TaskHandlerRegistry()

    registry.register(
        "legacy-token-test",
        lambda payload: payload["value"],
    )

    result = registry.execute(
        "legacy-token-test",
        {"value": 42},
        cancellation_token=object(),
    )

    assert result == 42
