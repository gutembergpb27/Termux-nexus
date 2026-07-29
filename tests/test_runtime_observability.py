from nexus import RuntimeClient
from nexus.runtime_observability import RuntimeObservability


def test_runtime_client_exposes_observability():
    client = RuntimeClient()

    assert isinstance(client.observability, RuntimeObservability)
    assert client.observability.runtime is client.runtime


def test_observability_exposes_runtime_services():
    client = RuntimeClient()

    assert client.observability.health() == client.health()
    assert client.observability.metrics() == client.metrics()
    assert client.observability.diagnostics() == client.diagnostics()
    assert client.observability.telemetry() == client.telemetry()


def test_observability_snapshot_is_consolidated():
    client = RuntimeClient()

    snapshot = client.observability.snapshot()

    assert snapshot == {
        "health": client.health(),
        "metrics": client.metrics(),
        "diagnostics": client.diagnostics(),
        "telemetry": client.telemetry(),
    }


def test_observability_instance_is_stable():
    client = RuntimeClient()

    assert client.observability is client.observability
