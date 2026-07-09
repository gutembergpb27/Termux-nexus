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


def test_recover_state_accepts_rotation_anchor_chain(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(filepath=str(db_path), max_bytes=1)

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })
    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })

    persistence_after_rotation = NexusPersistence(filepath=str(db_path))
    state = persistence_after_rotation.recover_state()

    assert db_path.exists()
    assert Path(str(db_path) + ".1").exists()
    assert state["pending_jobs"] == ["J1"]


def test_recover_state_rejects_tampered_rotation_anchor(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(filepath=str(db_path), max_bytes=1)

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })
    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })

    lines = db_path.read_text(encoding="utf-8").splitlines()
    anchor = json.loads(lines[0])
    assert anchor["payload"] == "ROTATION_ANCHOR"

    anchor["prev_hash"] = "f" * 64
    lines[0] = json.dumps(anchor)
    db_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    persistence_after_tamper = NexusPersistence(filepath=str(db_path))

    with pytest.raises(ValueError):
        persistence_after_tamper.recover_state()


def test_recover_state_rejects_tampered_rotated_history(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    persistence = NexusPersistence(
        filepath=str(db_path),
        max_bytes=1
    )

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })

    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })

    rotated_path = Path(str(db_path) + ".1")
    lines = rotated_path.read_text(
        encoding="utf-8"
    ).splitlines()

    block = json.loads(lines[-1])
    block["payload"]["data"]["worker_id"] = "TAMPERED-C5"
    lines[-1] = json.dumps(block)

    rotated_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    persistence_after_tamper = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_tamper.recover_state()

def test_recover_state_rejects_truncated_tail(tmp_path):
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

    with open(db_path, "ab") as f:
        f.write(b'{"timestamp":123,"payload":')

    persistence_after_truncation = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_truncation.recover_state()

def test_recover_state_rejects_reordered_blocks(tmp_path):
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

    lines = db_path.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    lines[1], lines[2] = lines[2], lines[1]

    db_path.write_text(
        "".join(lines),
        encoding="utf-8"
    )

    persistence_after_reorder = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_reorder.recover_state()
