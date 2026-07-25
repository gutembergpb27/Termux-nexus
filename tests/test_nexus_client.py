from nexus import RuntimeClient
from nexus import RuntimeConfig


def test_client_default_configuration():
    client = RuntimeClient()

    assert client.started is False
    assert client.config.node_id == "NODE-001"


def test_client_custom_configuration():
    config = RuntimeConfig(node_id="EDGE-01")

    client = RuntimeClient(config)

    assert client.config.node_id == "EDGE-01"


def test_client_lifecycle():
    client = RuntimeClient()

    assert client.start() is True
    assert client.started is True

    status = client.status()

    assert status["started"] is True
    assert status["state"] == "running"

    assert client.stop() is True
    assert client.started is False


def test_client_services():
    client = RuntimeClient()

    health = client.health()
    metrics = client.metrics()
    diagnostics = client.diagnostics()
    telemetry = client.telemetry()

    assert isinstance(health, dict)
    assert isinstance(metrics, dict)
    assert isinstance(diagnostics, dict)
    assert isinstance(telemetry, dict)
