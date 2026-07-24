"""Tests for the Nexus Runtime API."""

from nexus import Runtime


def test_runtime_starts_stopped() -> None:
    runtime = Runtime()

    assert runtime.started is False


def test_runtime_start() -> None:
    runtime = Runtime()

    runtime.start()

    assert runtime.started is True


def test_runtime_stop() -> None:
    runtime = Runtime()
    runtime.start()

    runtime.stop()

    assert runtime.started is False