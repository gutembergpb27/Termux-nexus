from nexus_distributed_core import NexusDistributedCore
from nexus_transport import encode_message, recv_message
from persistence import NexusPersistence


def make_core(node_id, store):
    core = object.__new__(NexusDistributedCore)
    core.node_id = node_id
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


def decode_sent(data):
    socket = FakeSocket.__new__(FakeSocket)
    socket.incoming = data
    socket.sent = b""
    socket.closed = False
    return recv_message(socket)


def test_rejoined_follower_converges_with_master(tmp_path):
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

    master = make_core("NO-MASTER", master_store)

    request = FakeSocket(
        {
            "type": "STATE_SUMMARY",
            "payload": rejoined_store.state_summary(),
        }
    )

    master.handle_client(request)
    batch = decode_sent(request.sent)

    assert batch["type"] == "SYNC_BATCH"
    assert batch["from_height"] == 1
    assert len(batch["blocks"]) == 2

    applied = rejoined_store.apply_blocks(batch["blocks"])

    assert applied == 2
    assert rejoined_store.state_summary()["height"] == 3
    assert rejoined_store.last_hash == master_store.last_hash
    assert request.closed is True
