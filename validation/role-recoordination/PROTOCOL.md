# Nexus Role Recoordination — Real-Process Validation Protocol

## Scope

This protocol validates the current uncommitted role-recoordination
candidate using real operating-system processes on one Windows host.

It is not NIRT and does not modify the frozen NIRT evidence.

## Candidate identity

Expected baseline:

    fa375b38b75bd91101d8b4594da3beed08fe6694

Expected candidate core SHA256:

    B24845F8E8480CEAB40791F1ED5C3CA379F181D8C39CA4D981BA6850643D25A3

## Topology

Hub:

    127.0.0.1:8500

Node A:

    node_id  = NO-9L-A
    web_port = 8081
    tcp_port = 9091
    role     = MASTER

Node Z:

    node_id  = NO-9L-Z
    web_port = 8082
    tcp_port = 9092
    role     = MASTER

Both nodes start as MASTER.

The deterministic rule under test is:

    lexicographically greatest stable node_id retains MASTER.

Therefore the expected stable result is:

    NO-9L-A = FOLLOWER
    NO-9L-Z = MASTER

## Mandatory preconditions

Before product execution:

1. exact Git branch and baseline;
2. exact candidate core SHA256;
3. candidate working tree contains the expected development changes;
4. ports 8500, 8081, 8082, 9091 and 9092 are free;
5. no related Nexus runtime process is active.

Failure of an environmental precondition is ABORTED, not product FAIL.

## Product execution

The runner starts:

1. the real nexus_rendezvous.py Hub;
2. real NO-9L-A as MASTER;
3. real NO-9L-Z as MASTER.

Separate persistence paths and empty stdin files are used.

No manual role mutation is permitted after process start.

## Mandatory conflict observation

The Hub must expose a snapshot in which both:

    NO-9L-A = MASTER
    NO-9L-Z = MASTER

are observed simultaneously.

If simultaneous MASTER state is never observed, the run is FAIL because
the intended conflict was not demonstrated.

## Mandatory convergence

After conflict observation, within 30 seconds:

    NO-9L-A = FOLLOWER
    NO-9L-Z = MASTER

must be observed through the real Hub peer registry.

No manual role change is allowed.

## Mandatory stability

After convergence, the exact stable assignment must be observed in at
least three subsequent Hub snapshots separated by at least 5 seconds:

    NO-9L-A = FOLLOWER
    NO-9L-Z = MASTER

A returns to MASTER during this window => FAIL.

Z ceases to be MASTER during this window => FAIL.

## Process requirements

Throughout mandatory convergence and stability observation:

- Hub must remain alive;
- A must remain alive;
- Z must remain alive.

Unexpected death of a required process => FAIL.

## Evidence

The runner preserves:

- result.txt
- timeline.txt
- environment.txt
- candidate.txt
- Hub stdout/stderr
- A stdout/stderr
- Z stdout/stderr
- conflict peers snapshot
- convergence peers snapshot
- stability peer snapshots
- SHA256 manifest

## Classification

PASS:

All mandatory conflict, convergence, process-liveness and stability
requirements pass.

FAIL:

Product execution started and any mandatory requirement fails.

ABORTED:

An environmental precondition prevents product execution from starting.

## Limitations

A PASS demonstrates only the scoped real-process behavior above on one
host.

It does not demonstrate:

- arbitrary network partitions;
- Byzantine fault tolerance;
- multi-machine correctness;
- production readiness;
- absence of defects;
- formal consensus correctness;
- independent third-party validation.

No automatic rerun is permitted after a FAIL.
