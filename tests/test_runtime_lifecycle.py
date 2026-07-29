from unittest.mock import Mock

from nexus import RuntimeClient
from nexus.runtime_lifecycle import RuntimeLifecycle


def test_runtime_client_exposes_lifecycle():
    client = RuntimeClient()

    assert isinstance(client.lifecycle, RuntimeLifecycle)
    assert client.lifecycle.runtime is client.runtime


def test_lifecycle_exposes_runtime_state():
    client = RuntimeClient()

    assert client.lifecycle.started == client.started
    assert client.lifecycle.status() == client.status()


def test_lifecycle_controls_runtime():
    client = RuntimeClient()

    assert client.lifecycle.start() is True
    assert client.lifecycle.started is True

    assert client.lifecycle.restart() is True
    assert client.lifecycle.started is True

    assert client.lifecycle.stop() is True
    assert client.lifecycle.started is False


def test_runtime_client_delegates_to_lifecycle():
    client = RuntimeClient()
    lifecycle = Mock(spec=RuntimeLifecycle)

    lifecycle.started = True
    lifecycle.start.return_value = True
    lifecycle.stop.return_value = True
    lifecycle.restart.return_value = True
    lifecycle.status.return_value = {"started": True}

    client._lifecycle = lifecycle

    assert client.started is True
    assert client.start() is True
    assert client.stop() is True
    assert client.restart() is True
    assert client.status() == {"started": True}

    lifecycle.start.assert_called_once_with()
    lifecycle.stop.assert_called_once_with()
    lifecycle.restart.assert_called_once_with()
    lifecycle.status.assert_called_once_with()


def test_lifecycle_instance_is_stable():
    client = RuntimeClient()

    assert client.lifecycle is client.lifecycle
