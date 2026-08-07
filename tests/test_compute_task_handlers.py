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


def test_registry_rejects_empty_name() -> None:
    registry = TaskHandlerRegistry()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        registry.register(
            " ",
            lambda payload: payload,
        )


def test_registry_rejects_non_callable_handler() -> None:
    registry = TaskHandlerRegistry()

    with pytest.raises(
        TypeError,
        match="must be callable",
    ):
        registry.register(
            "invalid",
            None,  # type: ignore[arg-type]
        )


def test_registry_rejects_unknown_handler() -> None:
    registry = TaskHandlerRegistry()

    with pytest.raises(
        KeyError,
        match="unknown task handler",
    ):
        registry.execute(
            "missing",
            {},
        )


def test_default_registry_exposes_echo_only() -> None:
    registry = build_default_task_registry()

    assert registry.names() == ("echo",)
    assert registry.execute(
        "echo",
        {"value": 42},
    ) == {"value": 42}
