from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message, recv_message
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


def decode_sent(data):
    conn = FakeConnection.__new__(FakeConnection)
    conn._incoming = data
    conn.sent = b""
    conn.closed = False
    return recv_message(conn)


def make_core(store):
    core = object.__new__(NexusDistributedCore)
    core.node_id = "NO-TEST"
    core.persistence = store
    return core


def test_state_summary_response_and_sync_batch_application(tmp_path):
    leader_store = NexusPersistence(
        filepath=str(tmp_path / "leader.db")
    )
    follower_store = NexusPersistence(
        filepath=str(tmp_path / "follower.db")
    )

    leader_store.append_transaction({"event": "A"})
    leader_store.append_transaction({"event": "B"})
    leader_store.append_transaction({"event": "C"})

    follower_store.apply_blocks(
        leader_store.blocks_from_height(0)[:1]
    )

    leader = make_core(leader_store)
    follower = make_core(follower_store)

    request_conn = FakeConnection(
        {
            "type": "STATE_SUMMARY",
            "payload": follower_store.state_summary(),
        }
    )

    leader.handle_client(request_conn)
    response = decode_sent(request_conn.sent)

    assert response["type"] == "SYNC_BATCH"
    assert response["from_height"] == 1
    assert len(response["blocks"]) == 2

    apply_conn = FakeConnection(response)
    follower.handle_client(apply_conn)

    assert follower_store.state_summary()["height"] == 3
    assert follower_store.last_hash == leader_store.last_hash
    assert request_conn.closed is True
    assert apply_conn.closed is True
