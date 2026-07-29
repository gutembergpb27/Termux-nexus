from nexus.runtime import Runtime
from nexus.runtime import RuntimeConfig


def test_default_runtime_config():
    config = RuntimeConfig()

    assert config.node_id == "NODE-001"
    assert config.environment == "development"
    assert config.log_level == "INFO"
    assert config.metrics_enabled is True
    assert config.tracing_enabled is True
    assert config.cluster_enabled is True
    assert config.metadata == {}


def test_custom_runtime_config():
    config = RuntimeConfig(
        node_id="EDGE-01",
        environment="production",
        log_level="DEBUG",
        metrics_enabled=False,
        tracing_enabled=False,
        cluster_enabled=False,
        metadata={"site": "lab"}
    )

    assert config.node_id == "EDGE-01"
    assert config.environment == "production"
    assert config.log_level == "DEBUG"
    assert config.metrics_enabled is False
    assert config.tracing_enabled is False
    assert config.cluster_enabled is False
    assert config.metadata["site"] == "lab"


def test_runtime_accepts_config():
    config = RuntimeConfig(node_id="NODE-A")

    runtime = Runtime(config=config)

    assert runtime.config is config
    assert runtime.config.node_id == "NODE-A"
