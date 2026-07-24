from nexus import Runtime
from nexus.runtime.metrics import RuntimeMetrics


def test_runtime_metrics_starts_empty():
    runtime = Runtime()
    metrics = RuntimeMetrics(runtime)

    assert metrics.summary() == {
        "runtime": {
            "started": False,
            "state": "stopped",
        },
        "cluster": {
            "nodes": 0,
            "leader": None,
            "online": 0,
            "offline": 0,
        },
    }


def test_runtime_metrics_tracks_runtime_state():
    runtime = Runtime()
    metrics = RuntimeMetrics(runtime)

    runtime.start()

    summary = metrics.summary()

    assert summary["runtime"] == {
        "started": True,
        "state": "running",
    }


def test_runtime_metrics_tracks_cluster_state():
    runtime = Runtime()
    metrics = RuntimeMetrics(runtime)

    runtime.cluster.add_node("NODE-A")
    runtime.cluster.add_node("NODE-B")
    runtime.cluster.elect_leader("NODE-A")

    summary = metrics.summary()

    assert summary["cluster"] == {
        "nodes": 2,
        "leader": "NODE-A",
        "online": 2,
        "offline": 0,
    }


def test_runtime_metrics_tracks_offline_nodes():
    runtime = Runtime()
    metrics = RuntimeMetrics(runtime)

    runtime.cluster.add_node("NODE-A")
    runtime.cluster.check_timeouts(-1)

    summary = metrics.summary()

    assert summary["cluster"] == {
        "nodes": 1,
        "leader": None,
        "online": 0,
        "offline": 1,
    }