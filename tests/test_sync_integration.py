"""Legacy STATE_SUMMARY / SYNC_BATCH path after W08-B.

Scope, stated explicitly:
- the TCP handlers are now expected to refuse sync in every cluster mode;
- the store-level test only checks that NexusPersistence can apply a block
  delta between two local stores in one process.

Nothing here validates network replication, node rejoin, quorum commit or
durability across a leader change. Those remain unimplemented.
"""

from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message
from persistence import NexusPersistence


class FakeConnection:
    def __init__(self, incoming):
        self._incoming = encode_message(incoming)
        self.sent = b""
        self.closed = False

    def recv(self, size):
        chunk = self._incoming[:size]
        self._incoming = self._incoming[size:]
        return chunk

    def sendall(self, data):
        self.sent += data

    def close(self):
        self.closed = True


def make_core(store):
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NO-TEST"
    # W08-B: even an explicit single-node deployment keeps the legacy,
    # unauthenticated TCP sync path disabled.
    core.cluster_mode = "single"
    core.configured_cluster_size = 1
    core.persistence = store
    return core


def test_local_store_block_delta_applies(tmp_path):
    """Local persistence API only; not network replication."""
    leader_store = NexusPersistence(
        filepath=str(tmp_path / "leader.db")
    )
    follower_store = NexusPersistence(
        filepath=str(tmp_path / "follower.db")
    )

    for event in ("A", "B", "C"):
        leader_store.append_transaction({"event": event})

    follower_store.apply_blocks(
        leader_store.blocks_from_height(0)[:1]
    )

    remote_height = follower_store.state_summary()["height"]
    blocks = leader_store.blocks_from_height(remote_height)

    assert remote_height == 1
    assert len(blocks) == 2
    assert follower_store.apply_blocks(blocks) == 2
    assert follower_store.state_summary()["height"] == 3
    assert follower_store.last_hash == leader_store.last_hash


def test_legacy_tcp_sync_is_blocked_in_single_mode(tmp_path):
    leader_store = NexusPersistence(
        filepath=str(tmp_path / "leader.db")
    )
    follower_store = NexusPersistence(
        filepath=str(tmp_path / "follower.db")
    )
    leader_store.append_transaction({"event": "A"})
    leader_tip = leader_store.last_hash
    follower_tip = follower_store.last_hash

    leader = make_core(leader_store)
    follower = make_core(follower_store)

    request_conn = FakeConnection(
        {
            "type": "STATE_SUMMARY",
            "payload": follower_store.state_summary(),
        }
    )
    leader.handle_client(request_conn)  # logs the block, never raises

    assert request_conn.sent == b""
    assert request_conn.closed is True

    apply_conn = FakeConnection(
        {
            "type": "SYNC_BATCH",
            "from_height": 0,
            "blocks": leader_store.blocks_from_height(0),
        }
    )
    follower.handle_client(apply_conn)

    assert apply_conn.closed is True
    assert follower_store.last_hash == follower_tip
    assert follower_store.state_summary()["height"] == 0
    assert leader_store.last_hash == leader_tip
