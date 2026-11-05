"""Rejoin over the legacy sync path after W08-B.

Real-process old-master rejoin is not validated (PARKED). These tests
only check that the legacy TCP sync handler refuses to serve a rejoining
node, and that two local stores can exchange blocks in-process. They are
not evidence of network replication or safe rejoin.
"""

from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message
from persistence import NexusPersistence


def make_core(node_id, store):
    core = object.__new__(NexusDistributedCore)
    core.node_id = node_id
    # W08-B: legacy TCP sync is disabled in every cluster mode,
    # including an explicit single-node deployment.
    core.cluster_mode = "single"
    core.configured_cluster_size = 1
    core.persistence = store
    return core


class FakeSocket:
    def __init__(self, incoming):
        self.incoming = encode_message(incoming)
        self.sent = b""
        self.closed = False

    def recv(self, size):
        chunk = self.incoming[:size]
        self.incoming = self.incoming[size:]
        return chunk

    def sendall(self, data):
        self.sent += data

    def close(self):
        self.closed = True


def make_stores(tmp_path):
    master_store = NexusPersistence(
        filepath=str(tmp_path / "master.db")
    )
    rejoined_store = NexusPersistence(
        filepath=str(tmp_path / "rejoined.db")
    )

    master_store.append_transaction({"event": "A"})
    master_store.append_transaction({"event": "B"})
    master_store.append_transaction({"event": "C"})

    rejoined_store.apply_blocks(
        master_store.blocks_from_height(0)[:1]
    )
    return master_store, rejoined_store


def test_local_store_catch_up_applies_missing_blocks(tmp_path):
    """Local persistence API only.

    This does not exercise a node rejoining a cluster: there is no
    network, no runtime and no leadership. It only checks that a
    lagging local store can apply the missing blocks of another one.
    """
    master_store, rejoined_store = make_stores(tmp_path)

    remote_height = rejoined_store.state_summary()["height"]
    blocks = master_store.blocks_from_height(remote_height)

    assert remote_height == 1
    assert len(blocks) == 2

    applied = rejoined_store.apply_blocks(blocks)

    assert applied == 2
    assert rejoined_store.state_summary()["height"] == 3
    assert rejoined_store.last_hash == master_store.last_hash


def test_rejoin_over_legacy_tcp_sync_is_blocked(tmp_path):
    master_store, rejoined_store = make_stores(tmp_path)
    rejoined_tip = rejoined_store.last_hash
    master = make_core("NO-MASTER", master_store)

    request = FakeSocket(
        {
            "type": "STATE_SUMMARY",
            "payload": rejoined_store.state_summary(),
        }
    )

    master.handle_client(request)  # logs the block, never raises

    assert request.sent == b""
    assert request.closed is True
    assert rejoined_store.last_hash == rejoined_tip
    assert rejoined_store.state_summary()["height"] == 1
