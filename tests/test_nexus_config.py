import pytest

from nexus_config import NexusConfig


def valid_env():
    return {
        "NEXUS_NODE_ID": "NO-ARM-01",
        "NEXUS_ROLE": "FOLLOWER",
        "NEXUS_BIND_HOST": "0.0.0.0",
        "NEXUS_WEB_PORT": "8082",
        "NEXUS_TCP_PORT": "9092",
        "NEXUS_HUB_URL": "http://192.168.1.5:8500",
        "NEXUS_DB_PATH": "./data/node.db",
        "NEXUS_ANCHOR_PATH": "./data/node.anchor",
        "NEXUS_SECRET_KEY": "test-secret",
        "NEXUS_HEARTBEAT_INTERVAL": "5",
        "NEXUS_PEER_TIMEOUT": "30",
        "NEXUS_MESSAGE_TTL": "60",
    }


def test_loads_canonical_configuration():
    config = NexusConfig.from_mapping(valid_env())

    assert config.node_id == "NO-ARM-01"
    assert config.role == "FOLLOWER"
    assert config.web_port == 8082
    assert config.tcp_port == 9092
    assert config.heartbeat_interval == 5.0
    assert config.peer_timeout == 30.0
    assert config.message_ttl == 60.0


def test_rejects_invalid_role():
    env = valid_env()
    env["NEXUS_ROLE"] = "LEADER"

    with pytest.raises(ValueError, match="role"):
        NexusConfig.from_mapping(env)


def test_rejects_missing_secret():
    env = valid_env()
    env["NEXUS_SECRET_KEY"] = ""

    with pytest.raises(ValueError, match="secret"):
        NexusConfig.from_mapping(env)


def test_rejects_invalid_port():
    env = valid_env()
    env["NEXUS_TCP_PORT"] = "70000"

    with pytest.raises(ValueError, match="port"):
        NexusConfig.from_mapping(env)


def test_rejects_peer_timeout_not_greater_than_heartbeat():
    env = valid_env()
    env["NEXUS_HEARTBEAT_INTERVAL"] = "30"
    env["NEXUS_PEER_TIMEOUT"] = "10"

    with pytest.raises(ValueError, match="timeout"):
        NexusConfig.from_mapping(env)
