from pathlib import Path


def test_failover_does_not_mutate_node_identity():
    source = Path("nexus_distributed_core.py").read_text(encoding="utf-8")

    assert 'self.node_id = f"MASTER-PROMOTE-{self.node_id}"' not in source, (
        "Failover must change only the node role. "
        "A stable node identity must survive leadership changes."
    )
