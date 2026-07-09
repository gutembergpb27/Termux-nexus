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

def test_recover_state_rejects_deleted_intermediate_block(tmp_path):
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

    del lines[1]

    db_path.write_text(
        "".join(lines),
        encoding="utf-8"
    )

    persistence_after_deletion = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_deletion.recover_state()

def test_recover_state_rejects_forged_inserted_block(tmp_path):
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

    forged_block = {
        "timestamp": 123,
        "payload": {
            "event": "FORGED_EVENT",
            "data": {"source": "C9"}
        },
        "prev_hash": "0" * 64,
        "hash": "f" * 64
    }

    lines.insert(
        1,
        json.dumps(forged_block) + "\n"
    )

    db_path.write_text(
        "".join(lines),
        encoding="utf-8"
    )

    persistence_after_insertion = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_insertion.recover_state()

def test_recover_state_rejects_replayed_valid_block(tmp_path):
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

    lines.insert(2, lines[1])

    db_path.write_text(
        "".join(lines),
        encoding="utf-8"
    )

    persistence_after_replay = NexusPersistence(
        filepath=str(db_path)
    )

    with pytest.raises(ValueError):
        persistence_after_replay.recover_state()

def test_recover_state_rejects_valid_old_snapshot_rollback(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    snapshot_path = tmp_path / "snapshot_old.db"

    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({
        "event": "WORKER_SPAWN",
        "data": {"worker_id": "W1", "pid": 123}
    })

    persistence.append_transaction({
        "event": "JOB_SUBMIT",
        "data": {"job_id": "J1"}
    })

    snapshot_path.write_bytes(db_path.read_bytes())

    persistence.append_transaction({
        "event": "JOB_COMMIT",
        "data": {"job_id": "J1"}
    })

    db_path.write_bytes(snapshot_path.read_bytes())

    persistence_after_rollback = NexusPersistence(filepath=str(db_path))

    with pytest.raises(ValueError):
        persistence_after_rollback.recover_state()

def test_recover_state_rejects_tampered_checkpoint_height(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    checkpoint_path = Path(str(db_path) + ".checkpoint.json")
    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["height"] = 999
    checkpoint_path.write_text(json.dumps(checkpoint) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        NexusPersistence(filepath=str(db_path)).recover_state()


def test_recover_state_rejects_tampered_checkpoint_tip_hash(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    checkpoint_path = Path(str(db_path) + ".checkpoint.json")
    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["tip_hash"] = "f" * 64
    checkpoint_path.write_text(json.dumps(checkpoint) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        NexusPersistence(filepath=str(db_path)).recover_state()

@pytest.mark.xfail(reason="Rollback coordenado de log + checkpoint exige âncora externa/autenticação fora do conjunto restaurável.")
def test_recover_state_does_not_yet_reject_coordinated_log_and_checkpoint_rollback(tmp_path):
    db_path = tmp_path / "nexus_store.db"
    checkpoint_path = Path(str(db_path) + ".checkpoint.json")
    snapshot_db_path = tmp_path / "snapshot_old.db"
    snapshot_checkpoint_path = tmp_path / "snapshot_old.checkpoint.json"

    persistence = NexusPersistence(filepath=str(db_path))

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    snapshot_db_path.write_bytes(db_path.read_bytes())
    snapshot_checkpoint_path.write_bytes(checkpoint_path.read_bytes())

    persistence.append_transaction({"event": "JOB_COMMIT", "data": {"job_id": "J1"}})

    db_path.write_bytes(snapshot_db_path.read_bytes())
    checkpoint_path.write_bytes(snapshot_checkpoint_path.read_bytes())

    with pytest.raises(ValueError):
        NexusPersistence(filepath=str(db_path)).recover_state()

def test_recover_state_rejects_coordinated_rollback_when_external_anchor_is_preserved(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"
    checkpoint_path = Path(str(db_path) + ".checkpoint.json")

    snapshot_db_path = tmp_path / "snapshot_old.db"
    snapshot_checkpoint_path = tmp_path / "snapshot_old.checkpoint.json"

    persistence = NexusPersistence(
        filepath=str(db_path),
        anchor_path=str(anchor_path)
    )

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    snapshot_db_path.write_bytes(db_path.read_bytes())
    snapshot_checkpoint_path.write_bytes(checkpoint_path.read_bytes())

    persistence.append_transaction({"event": "JOB_COMMIT", "data": {"job_id": "J1"}})

    db_path.write_bytes(snapshot_db_path.read_bytes())
    checkpoint_path.write_bytes(snapshot_checkpoint_path.read_bytes())

    with pytest.raises(ValueError):
        NexusPersistence(
            filepath=str(db_path),
            anchor_path=str(anchor_path)
        ).recover_state()

def test_recover_state_rejects_missing_external_anchor(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"

    persistence = NexusPersistence(
        filepath=str(db_path),
        anchor_path=str(anchor_path)
    )

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    anchor_path.unlink()

    with pytest.raises(ValueError):
        NexusPersistence(
            filepath=str(db_path),
            anchor_path=str(anchor_path)
        ).recover_state()

def test_recover_state_rejects_tampered_external_anchor_height(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"

    persistence = NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path))
    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    anchor["height"] = 999
    anchor_path.write_text(json.dumps(anchor) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path)).recover_state()


def test_recover_state_rejects_tampered_external_anchor_tip_hash(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"

    persistence = NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path))
    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    anchor["tip_hash"] = "f" * 64
    anchor_path.write_text(json.dumps(anchor) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path)).recover_state()


def test_recover_state_rejects_corrupted_external_anchor_json(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"

    persistence = NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path))
    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})
    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    anchor_path.write_text('{"height":', encoding="utf-8")

    with pytest.raises(Exception):
        NexusPersistence(filepath=str(db_path), anchor_path=str(anchor_path)).recover_state()

def test_recover_state_rejects_log_ahead_of_checkpoint_and_anchor(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"
    checkpoint_path = Path(str(db_path) + ".checkpoint.json")

    snapshot_checkpoint_path = tmp_path / "checkpoint_before.json"
    snapshot_anchor_path = tmp_path / "anchor_before.json"

    persistence = NexusPersistence(
        filepath=str(db_path),
        anchor_path=str(anchor_path)
    )

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})

    snapshot_checkpoint_path.write_bytes(checkpoint_path.read_bytes())
    snapshot_anchor_path.write_bytes(anchor_path.read_bytes())

    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    checkpoint_path.write_bytes(snapshot_checkpoint_path.read_bytes())
    anchor_path.write_bytes(snapshot_anchor_path.read_bytes())

    with pytest.raises(ValueError):
        NexusPersistence(
            filepath=str(db_path),
            anchor_path=str(anchor_path)
        ).recover_state()

def test_recover_state_rejects_checkpoint_ahead_of_external_anchor(tmp_path):
    db_dir = tmp_path / "db"
    anchor_dir = tmp_path / "anchor"
    db_dir.mkdir()
    anchor_dir.mkdir()

    db_path = db_dir / "nexus_store.db"
    anchor_path = anchor_dir / "nexus.anchor.json"
    snapshot_anchor_path = tmp_path / "anchor_before.json"

    persistence = NexusPersistence(
        filepath=str(db_path),
        anchor_path=str(anchor_path)
    )

    persistence.append_transaction({"event": "WORKER_SPAWN", "data": {"worker_id": "W1", "pid": 123}})

    snapshot_anchor_path.write_bytes(anchor_path.read_bytes())

    persistence.append_transaction({"event": "JOB_SUBMIT", "data": {"job_id": "J1"}})

    anchor_path.write_bytes(snapshot_anchor_path.read_bytes())

    with pytest.raises(ValueError):
        NexusPersistence(
            filepath=str(db_path),
            anchor_path=str(anchor_path)
        ).recover_state()
