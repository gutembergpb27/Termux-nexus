import json
from pathlib import Path

import pytest

from persistence import NexusPersistence


def test_recover_state_rejects_tampered_payload(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })

    lines = db_path.read_text(encoding="utf-8").splitlines()
    block = json.loads(lines[0])
    block["payload"]["data"]["pid"] = 999
    db_path.write_text(json.dumps(block) + "\n", encoding="utf-8")

    persistence_after_tamper = NexusPersistence(filepath=str(db_path))

    with pytest.raises(ValueError):
        persistence_after_tamper.recover_state()


def test_recover_state_rejects_tampered_prev_hash(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })
    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })

    lines = db_path.read_text(encoding="utf-8").splitlines()
    second_block = json.loads(lines[1])
    second_block["prev_hash"] = "f" * 64
    lines[1] = json.dumps(second_block)
    db_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    persistence_after_tamper = NexusPersistence(filepath=str(db_path))

    with pytest.raises(ValueError):
        persistence_after_tamper.recover_state()


def test_recover_state_accepts_intact_chain(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })
    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })
    persistence.append_transaction({
        "event": "JOB_COMMIT",
        "data": {"job_id": "J1"}
    })

    persistence_after_restart = NexusPersistence(filepath=str(db_path))
    state = persistence_after_restart.recover_state()

    assert state["active_workers"] == {"W1": 123}
    assert state["pending_jobs"] == []
    assert state["completed_jobs"] == ["J1"]
