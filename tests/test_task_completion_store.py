from __future__ import annotations

import json

import pytest

from nexus.compute.completion_store import TaskCompletionStore
from nexus.compute.task_completion import TaskCompletionRegistry


def test_store_loads_empty_registry_when_file_is_missing(
    tmp_path,
) -> None:
    store = TaskCompletionStore(
        tmp_path / "missing.json"
    )

    registry = store.load()

    assert registry.snapshot().total == 0


def test_store_saves_and_loads_registry(
    tmp_path,
) -> None:
    path = tmp_path / "completion-state.json"

    store = TaskCompletionStore(path)

    registry = TaskCompletionRegistry()

    registry.create("pending")

    registry.create("completed")
    registry.complete(
        "completed",
        {"value": 42},
    )

    registry.create("failed")
    registry.fail(
        "failed",
        "boom",
    )

    registry.create("cancelled")
    registry.cancel("cancelled")

    store.save(registry)

    assert path.exists()

    restored = store.load()

    assert restored.get("pending").status == "pending"
    assert restored.get("completed").status == "completed"
    assert restored.get("completed").result == {"value": 42}
    assert restored.get("failed").status == "failed"
    assert restored.get("failed").error == "boom"
    assert restored.get("cancelled").status == "cancelled"


def test_store_recovers_running_as_failed(
    tmp_path,
) -> None:
    store = TaskCompletionStore(
        tmp_path / "running.json"
    )

    registry = TaskCompletionRegistry()

    registry.create("running")
    registry.start("running")

    store.save(registry)

    restored = store.load()

    completion = restored.get("running")

    assert completion is not None
    assert completion.status == "failed"
    assert completion.error == (
        "task interrupted by runtime restart"
    )


def test_store_writes_versioned_json(
    tmp_path,
) -> None:
    path = tmp_path / "state.json"

    registry = TaskCompletionRegistry()
    registry.create("task")

    TaskCompletionStore(path).save(
        registry
    )

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert data["schema_version"] == 1
    assert data["items"][0]["task_id"] == "task"


def test_store_rejects_corrupt_json(
    tmp_path,
) -> None:
    path = tmp_path / "corrupt.json"

    path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    store = TaskCompletionStore(path)

    with pytest.raises(
        ValueError,
        match="invalid task completion state JSON",
    ):
        store.load()


def test_store_rejects_invalid_schema(
    tmp_path,
) -> None:
    path = tmp_path / "schema.json"

    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "items": [],
            }
        ),
        encoding="utf-8",
    )

    store = TaskCompletionStore(path)

    with pytest.raises(
        ValueError,
        match="unsupported completion state schema",
    ):
        store.load()


def test_store_atomic_replace_preserves_previous_file_on_failure(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "atomic.json"

    store = TaskCompletionStore(path)

    first = TaskCompletionRegistry()
    first.create("first")

    store.save(first)

    original = path.read_text(
        encoding="utf-8"
    )

    second = TaskCompletionRegistry()
    second.create("second")

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(
        "nexus.compute.completion_store.os.replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="replace failed",
    ):
        store.save(second)

    assert (
        path.read_text(
            encoding="utf-8"
        )
        == original
    )

    assert not (
        tmp_path / "atomic.json.tmp"
    ).exists()


def test_store_replaces_existing_state_atomically(
    tmp_path,
) -> None:
    path = tmp_path / "replace.json"

    store = TaskCompletionStore(path)

    first = TaskCompletionRegistry()
    first.create("first")

    store.save(first)

    second = TaskCompletionRegistry()
    second.create("second")

    store.save(second)

    restored = store.load()

    assert restored.get("first") is None
    assert restored.get("second") is not None


def test_store_creates_parent_directory(
    tmp_path,
) -> None:
    path = (
        tmp_path
        / "nested"
        / "state"
        / "completion.json"
    )

    registry = TaskCompletionRegistry()
    registry.create("nested")

    TaskCompletionStore(path).save(
        registry
    )

    assert path.exists()


def test_store_leaves_no_temp_file_after_success(
    tmp_path,
) -> None:
    path = tmp_path / "clean.json"

    registry = TaskCompletionRegistry()
    registry.create("clean")

    TaskCompletionStore(path).save(
        registry
    )

    assert not (
        tmp_path / "clean.json.tmp"
    ).exists()
