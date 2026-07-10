from pathlib import Path


def test_failover_does_not_mutate_node_identity():
    source = Path("nexus_distributed_core.py").read_text(encoding="utf-8")

    assert 'self.node_id = f"MASTER-PROMOTE-{self.node_id}"' not in source, (
        "Failover must change only the node role. "
        "A stable node identity must survive leadership changes."
    )


def test_failover_keeps_mesh_monitoring_active():
    source = Path("nexus_distributed_core.py").read_text(encoding="utf-8")

    promotion = source.index('self.role = "MASTER"')
    shell_loop = source.index("def shell_intake_loop", promotion)
    failover_block = source[promotion:shell_loop]

    assert "\n                        break\n" not in failover_block, (
        "A promoted node must keep the polling loop active so it can "
        "continue registering heartbeats and observing the mesh."
    )
