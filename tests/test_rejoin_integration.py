from nexus_distributed_core import NexusDistributedCore
from persistence import NexusPersistence


def make_core(node_id, store):
    core = object.__new__(NexusDistributedCore)
    core.node_id = node_id
    core.persistence = store
    return core


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

    # O nó antigo ficou para trás e possui apenas o primeiro bloco.
    rejoined_store.apply_blocks(
        master_store.blocks_from_height(0)[:1]
    )

    master = make_core("NO-MASTER", master_store)
    rejoined = make_core("NO-REJOIN", rejoined_store)

    class FakeSocket:
        def __init__(self):
            self.response = b""

        def recv(self, _size):
            summary = {
                "type": "STATE_SUMMARY",
                "payload": rejoined_store.state_summary(),
            }
            import json
            return json.dumps(summary).encode("utf-8")

        def sendall(self, data):
            self.response = data

        def close(self):
            pass

    request = FakeSocket()
    master.handle_client(request)

    import json
    batch = json.loads(request.response.decode("utf-8"))

    assert batch["type"] == "SYNC_BATCH"
    assert batch["from_height"] == 1
    assert len(batch["blocks"]) == 2

    applied = rejoined_store.apply_blocks(batch["blocks"])

    assert applied == 2
    assert rejoined_store.state_summary()["height"] == 3
    assert rejoined_store.last_hash == master_store.last_hash
