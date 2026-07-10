from pathlib import Path


def test_setup_node_does_not_delete_existing_databases():
    script = Path("setup_node.sh").read_text(encoding="utf-8")

    destructive_patterns = (
        'rm -f "$NEXUS_DIR"/nexus_*.db',
        'rm -f "$NEXUS_DIR"/nexus_*.db-wal',
        'rm -f "$NEXUS_DIR"/nexus_*.db-shm',
    )

    detected = [pattern for pattern in destructive_patterns if pattern in script]

    assert not detected, (
        "Provisioning must preserve existing node state. "
        f"Destructive database cleanup detected: {detected}"
    )
