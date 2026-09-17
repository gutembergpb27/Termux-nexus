"""Registro explícito de handlers permitidos para Nexus Compute."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from threading import RLock
from nexus.compute.node_load import NodeLoad

from collections.abc import Callable, Mapping
from typing import Any

TaskHandler = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class TaskHandlerMetrics:
    runs: int = 0
    failures: int = 0
    total_duration_seconds: float = 0.0
    last_execution_at: float | None = None
    last_error: str | None = None

    @property
    def successes(self) -> int:
        return self.runs - self.failures

    @property
    def average_duration_ms(self) -> float:
        if self.runs == 0:
            return 0.0

        return (
            self.total_duration_seconds
            / self.runs
            * 1000.0
        )


@dataclass
class _MutableTaskHandlerMetrics:
    runs: int = 0
    failures: int = 0
    total_duration_seconds: float = 0.0
    last_execution_at: float | None = None
    last_error: str | None = None

    def snapshot(self) -> TaskHandlerMetrics:
        return TaskHandlerMetrics(
            runs=self.runs,
            failures=self.failures,
            total_duration_seconds=self.total_duration_seconds,
            last_execution_at=self.last_execution_at,
            last_error=self.last_error,
        )


class TaskHandlerRegistry:
    """Registro controlado de operações remotas permitidas."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}
        self._metrics: dict[str, _MutableTaskHandlerMetrics] = {}
        self._metrics_lock = RLock()
        self._active_tasks = 0

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

        with self._metrics_lock:
            self._metrics[normalized] = _MutableTaskHandlerMetrics()

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
        *,
        cancellation_token: Any | None = None,
    ) -> Any:
        normalized = self._normalize_name(name)
        handler = self.get(normalized)

        with self._metrics_lock:
            self._active_tasks += 1

        started = time.perf_counter()

        try:
            signature = inspect.signature(
                handler
            )

            accepts_token = (
                "cancellation_token"
                in signature.parameters
            )

            if accepts_token:
                result = handler(
                    payload,
                    cancellation_token=cancellation_token,
                )
            else:
                result = handler(payload)
        except Exception as exc:
            duration = time.perf_counter() - started

            with self._metrics_lock:
                metrics = self._metrics[normalized]
                metrics.runs += 1
                metrics.failures += 1
                metrics.total_duration_seconds += duration
                metrics.last_execution_at = time.time()
                metrics.last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

            raise
        else:
            duration = time.perf_counter() - started

            with self._metrics_lock:
                metrics = self._metrics[normalized]
                metrics.runs += 1
                metrics.total_duration_seconds += duration
                metrics.last_execution_at = time.time()
                metrics.last_error = None

            return result
        finally:
            with self._metrics_lock:
                self._active_tasks -= 1

    def load_snapshot(self) -> NodeLoad:
        """Retorna a carga agregada atual do registry."""

        with self._metrics_lock:
            metrics = [
                item.snapshot()
                for item in self._metrics.values()
            ]

            active_tasks = self._active_tasks

        total_runs = sum(
            item.runs
            for item in metrics
        )

        failed_tasks = sum(
            item.failures
            for item in metrics
        )

        completed_tasks = (
            total_runs - failed_tasks
        )

        total_duration_seconds = sum(
            item.total_duration_seconds
            for item in metrics
        )

        average_duration_ms = 0.0

        if total_runs:
            average_duration_ms = (
                total_duration_seconds
                / total_runs
                * 1000.0
            )

        return NodeLoad(
            active_tasks=active_tasks,
            queued_tasks=0,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            average_duration_ms=average_duration_ms,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def metrics(self, name: str) -> TaskHandlerMetrics:
        normalized = self._normalize_name(name)

        if normalized not in self._handlers:
            raise KeyError(
                f"unknown task handler: {normalized}"
            )

        with self._metrics_lock:
            return self._metrics[normalized].snapshot()

    def metrics_snapshot(
        self,
    ) -> dict[str, TaskHandlerMetrics]:
        with self._metrics_lock:
            return {
                name: self._metrics[name].snapshot()
                for name in sorted(self._handlers)
            }


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
