# NIRT-01 — Nexus Independent Reproduction Test

## Status

Experimental reproduction protocol.

This document does not constitute independent certification,
security certification, production-readiness certification,
or proof of superiority over other distributed systems.

## Product

Nexus Runtime Platform

## Frozen reference baseline

- Release candidate: v2700.0.0-rc1
- Git commit:
  c8516db7b1fb694af647c80e1f1b9bc828a60d77

The reference baseline must not be modified during execution.
## Execution model

The NIRT runner itself may be versioned after the frozen product
baseline.

To prevent the reproduction tooling from modifying the product under
test, the runner creates a temporary detached Git worktree at the exact
frozen commit:

c8516db7b1fb694af647c80e1f1b9bc828a60d77

All predefined product tests are executed inside that detached
worktree.

Therefore two Git identities are recorded separately:

- instrumentation commit: the revision containing the NIRT protocol
  and runner;
- frozen product commit: the exact Nexus Runtime Platform revision
  under evaluation.

The temporary product worktree must be clean before test execution.

## Objective

NIRT-01 evaluates whether selected distributed-runtime properties
already implemented in the frozen Nexus baseline can be reproduced
from a clean checkout using a predefined procedure.

The experiment intentionally defines PASS/FAIL criteria before
external execution.

## Internal reference contract

The following behaviors were selected before execution of the
reference run.

### C1 — Leader election

PASS when both existing tests pass:

- test_elect_leader_promotes_selected_node
- test_elect_leader_changes_previous_master

### C2 — Runtime recoordination

PASS when:

- test_runtime_retry_recoordinates_after_cluster_leader_change

passes.

### C3 — Rejoin convergence

PASS when:

- test_rejoined_follower_converges_with_master

passes.

### C4 — Failover identity continuity

PASS when both tests pass:

- test_failover_does_not_mutate_node_identity
- test_failover_keeps_mesh_monitoring_active

### C5 — Readiness contract

PASS when the runtime:

- accepts a healthy master;
- accepts a follower with a recent master;
- rejects a follower without a master;
- rejects a stale master heartbeat;
- rejects unhealthy persistence/storage.

### C6 — Persistence recovery

PASS when:

- test_recover_state_recovers_consistent_state_after_restart

passes.

## Overall result

NIRT-01 TEST CONTRACT PASS requires all 12 predefined reference
tests to pass.

Any failed test produces FAIL.

Failures must not be removed, reclassified, or ignored after the run.

## Evidence collected by the runner

The automated runner records:

- UTC timestamp;
- operating system;
- PowerShell version;
- Python version;
- pytest version;
- Git commit;
- Git branch;
- Git status;
- Nexus CLI version;
- individual pytest results;
- final PASS/FAIL result;
- SHA-256 hashes of the evidence files.

## Independence requirement

A future external reproduction should be performed by a person who
did not participate in development of the tested baseline.

The evaluator should receive:

1. repository URL;
2. exact commit;
3. this protocol;
4. execution command.

The evaluator should execute the protocol in their own environment
without source-code modification.

A successful external reproduction demonstrates reproducibility of
the tested behavior under the evaluator's environment.

It does not by itself prove:

- absence of defects;
- security against all adversaries;
- production readiness;
- distributed correctness under all network conditions;
- commercial superiority;
- legal or intellectual-property claims.

## Reference internal run

The pre-external internal reference run produced:

- 12 selected tests
- 12 PASS
- 0 FAIL

The repository remained at the frozen reference commit after execution.

External results must be reported independently of this reference result.
