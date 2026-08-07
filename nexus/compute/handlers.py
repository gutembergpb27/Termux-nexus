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

        handler = self.get(name)
        return handler(payload)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


def echo_handler(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Handler seguro padrão que ecoa o payload recebido."""

    return dict(payload)


def build_default_task_registry() -> TaskHandlerRegistry:
    """Cria o registry padrão do runtime distribuído."""

    registry = TaskHandlerRegistry()
    registry.register("echo", echo_handler)
    return registry
