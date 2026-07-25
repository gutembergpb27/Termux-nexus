from nexus import RuntimeClient


def test_runtime_client_exposes_cluster():
    client = RuntimeClient()

    assert client.cluster is client.runtime.cluster


def test_runtime_client_cluster_adds_nodes():
    client = RuntimeClient()

    client.cluster.add_node("NODE-01")
    client.cluster.add_node("NODE-02")

    assert client.cluster.count() == 2
    assert set(client.cluster.nodes()) == {"NODE-01", "NODE-02"}


def test_runtime_client_cluster_elects_leader():
    client = RuntimeClient()

    client.cluster.add_node("NODE-01")
    client.cluster.add_node("NODE-02")

    client.cluster.elect_leader("NODE-01")

    assert client.cluster.leader() == "NODE-01"
    assert client.cluster.followers() == ["NODE-02"]


def test_runtime_client_cluster_snapshot():
    client = RuntimeClient()

    client.cluster.add_node("NODE-01")
    client.cluster.elect_leader("NODE-01")

    snapshot = client.cluster.snapshot()

    assert isinstance(snapshot, dict)
    assert snapshot["version"] == 2
    assert snapshot["nodes"]["NODE-01"]["role"] == "MASTER"
    assert snapshot["nodes"]["NODE-01"]["status"] == "ONLINE"
