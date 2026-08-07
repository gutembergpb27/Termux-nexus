"""Registro explícito de handlers permitidos para Nexus Compute."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

TaskHandler = Callable[[Mapping[str, Any]], Any]


class TaskHandlerRegistry:
    """Registro controlado de operações remotas permitidas."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()

        if not normalized:
            raise ValueError("task handler name must not be empty")

        return normalized

    def register(
        self,
        name: str,
        handler: TaskHandler,
    ) -> None:
        normalized = self._normalize_name(name)

        if not callable(handler):
            raise TypeError("task handler must be callable")

        if normalized in self._handlers:
            raise ValueError(
                f"task handler already registered: {normalized}"
            )

        self._handlers[normalized] = handler

    def get(self, name: str) -> TaskHandler:
        normalized = self._normalize_name(name)

        try:
            return self._handlers[normalized]
        except KeyError as exc:
            raise KeyError(
                f"unknown task handler: {normalized}"
            ) from exc

    def execute(
        self,
        name: str,
        payload: Mapping[str, Any],
    ) -> Any:
        if not isinstance(payload, Mapping):
            raise TypeError(
                "task handler payload must be a mapping"
            )

        return self.get(name)(payload)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


def echo_handler(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return dict(payload)


def data_transform_handler(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    values = payload.get("values")
    operation = str(payload.get("operation", "")).strip()

    if not isinstance(values, list):
        raise ValueError("values must be a list")

    if operation == "double":
        return {
            "values": [value * 2 for value in values],
        }

    if operation == "square":
        return {
            "values": [value * value for value in values],
        }

    if operation == "sum":
        return {
            "value": sum(values),
        }

    raise ValueError(
        f"unsupported data transform operation: {operation}"
    )


def matrix_multiply_handler(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    left = payload.get("left")
    right = payload.get("right")

    if not isinstance(left, list) or not isinstance(right, list):
        raise ValueError("matrices must be lists")

    if not left or not right:
        raise ValueError("matrices must not be empty")

    if not all(isinstance(row, list) and row for row in left):
        raise ValueError("left matrix is invalid")

    if not all(isinstance(row, list) and row for row in right):
        raise ValueError("right matrix is invalid")

    left_width = len(left[0])
    right_width = len(right[0])

    if any(len(row) != left_width for row in left):
        raise ValueError("left matrix rows must have equal length")

    if any(len(row) != right_width for row in right):
        raise ValueError("right matrix rows must have equal length")

    if left_width != len(right):
        raise ValueError("matrix dimensions are incompatible")

    result = []

    for left_row in left:
        result_row = []

        for column_index in range(right_width):
            value = sum(
                left_row[index] * right[index][column_index]
                for index in range(left_width)
            )
            result_row.append(value)

        result.append(result_row)

    return {
        "matrix": result,
    }


def build_default_task_registry() -> TaskHandlerRegistry:
    registry = TaskHandlerRegistry()

    registry.register("echo", echo_handler)
    registry.register(
        "data_transform",
        data_transform_handler,
    )
    registry.register(
        "matrix_multiply",
        matrix_multiply_handler,
    )

    return registry
