from nexus import RuntimeClient
from nexus.runtime_lifecycle import RuntimeLifecycle


def test_runtime_client_exposes_lifecycle():
    client = RuntimeClient()

    assert isinstance(client.lifecycle, RuntimeLifecycle)
    assert client.lifecycle.runtime is client.runtime


def test_lifecycle_exposes_runtime_services():
    client = RuntimeClient()

    assert client.lifecycle.started == client.started
    assert client.lifecycle.status() == client.status()


def test_lifecycle_delegates_runtime_operations():
    client = RuntimeClient()

    assert client.lifecycle.start() is True
    assert client.lifecycle.started is True

    assert client.lifecycle.stop() is True
    assert client.lifecycle.started is False


def test_lifecycle_instance_is_stable():
    client = RuntimeClient()

    assert client.lifecycle is client.lifecycle
