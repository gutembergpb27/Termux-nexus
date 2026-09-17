# NIRT-02 — Real Process Failover Test

## Status

Pre-execution experimental protocol.

The PASS, FAIL, and ABORTED criteria in this document are defined
before the first NIRT-02 experimental run.

## Objective

NIRT-02 evaluates whether the frozen Nexus Runtime Platform RC1 can
demonstrate a predefined real-process failover scenario using its own
runtime, rendezvous Hub, heartbeat, peer discovery, persistence, HTTP
observability, and automatic leadership-promotion mechanisms.

NIRT-02 is not a pytest-only reproduction exercise.

The experiment starts real operating-system processes.

## Frozen product

Release candidate:

v2700.0.0-rc1

Frozen product commit:

c8516db7b1fb694af647c80e1f1b9bc828a60d77

The product under test must execute from a detached Git worktree at
that exact commit.

The frozen product source must not be modified during execution.

## Instrumentation separation

The NIRT-02 protocol and runner are versioned separately from the
frozen product.

The evidence must record:

- instrumentation commit;
- instrumentation branch;
- instrumentation Git status;
- frozen product commit;
- frozen product tag.

## Topology

The predefined topology is:

Hub:

- process: nexus_rendezvous.py
- HTTP port: 8500

Node A:

- node_id: NO-NIRT02-A
- web_port: 8081
- tcp_port: 9091
- initial role: MASTER

Node B:

- node_id: NO-NIRT02-B
- web_port: 8082
- tcp_port: 9092
- initial role: FOLLOWER

## Environment

The runner must record at least:

- UTC timestamp;
- operating system;
- PowerShell version;
- Git version;
- Python version;
- pytest version;
- Nexus CLI version;
- Nexus module CLI version from the frozen worktree when available.

The experiment requires:

- Git with worktree support;
- Python 3.10 or newer;
- pytest available to the selected Python interpreter;
- PowerShell;
- TCP ports 8500, 8081, 8082, 9091, and 9092 available.

## Security configuration

The experiment uses an isolated per-run secret supplied to the Hub
and both runtime nodes through NEXUS_SECRET_KEY.

The Hub URL is:

http://127.0.0.1:8500

## Initial persistent state

Before starting the runtime nodes, the runner creates one predefined
persistent transaction in Node A storage using NexusPersistence from
the exact frozen product worktree.

Event:

NIRT02_SEED

Payload:

pre-failover-state

This guarantees that the persistence state being compared is
non-genesis.

Node B begins with separate storage and must obtain the state through
the runtime synchronization mechanism.

## Required HTTP observations

Runtime observations use the product endpoints:

- /liveness
- /readiness
- /health
- /status
- /cluster
- /metrics

Hub observations use:

- /peers

## Pre-failover PASS conditions

Before the failure event, all of the following are mandatory:

1. Hub is alive.
2. Node A process is alive.
3. Node B process is alive.
4. Hub reports Node A as MASTER.
5. Hub reports Node B as FOLLOWER.
6. Node A /liveness reports alive=true.
7. Node B /liveness reports alive=true.
8. Node A /health reports healthy=true.
9. Node B /health reports healthy=true.
10. Node A storage reports valid=true.
11. Node B storage reports valid=true.
12. Node A /readiness reports ready=true.
13. Node B /readiness reports ready=true.
14. Node A /status reports role=MASTER.
15. Node B /status reports role=FOLLOWER.
16. Node A height is greater than zero.
17. Node B height equals Node A height.
18. Node B tip_hash equals Node A tip_hash.
19. The converged tip_hash is not the genesis zero hash.

No expected application hash is predefined.

Equality and preservation are the properties under observation.

## Failure event

The experimental failure event is:

abrupt termination of the Node A operating-system process.

Only Node A is terminated.

The Hub remains alive.

Node B remains alive.

No source file is changed.

No manual role mutation is allowed.

No external leadership command is allowed.

## Post-failover timeout

The maximum observation window after termination of Node A is:

70 seconds.

This window accommodates the frozen runtime heartbeat, peer expiry,
and leadership-promotion timing.

## Post-failover PASS conditions

Within the timeout, all of the following are mandatory:

1. Node A is absent from the Hub active peer set.
2. Node B is reported as MASTER by the Hub.
3. Node B node_id remains exactly NO-NIRT02-B.
4. Node B process remains alive.
5. Node B /liveness reports alive=true.
6. Node B /health reports healthy=true.
7. Node B storage reports valid=true.
8. Node B /readiness reports ready=true.
9. Node B /status reports role=MASTER.
10. Node B height equals its pre-failover height.
11. Node B tip_hash equals its pre-failover tip_hash.
12. Node B tip_hash is not the genesis zero hash.

Because no post-failure workload is introduced in NIRT-02, exact
height and tip_hash preservation is required.

## Result classification

### PASS

PASS requires every mandatory pre-failover and post-failover property
to be observed.

### FAIL

FAIL applies when the product execution has begun and any mandatory
property fails, including:

- incorrect role;
- failed health/readiness/liveness;
- failed state convergence;
- state regression;
- identity mutation;
- failover timeout;
- unexpected termination of an essential process;
- manual intervention becoming necessary.

A FAIL run must be preserved.

The runner must not repair the product during the run.

### ABORTED

ABORTED applies when an environmental or instrumentation prerequisite
prevents product execution from beginning.

Examples:

- required port already occupied;
- required command unavailable;
- dirty instrumentation repository;
- product tag resolves to an unexpected commit;
- temporary worktree cannot be created.

ABORTED is not PASS and is not FAIL.

## Evidence

Each run must create a dedicated timestamped evidence directory.

The evidence package should include, when available:

- environment.txt
- instrument.txt
- contract.txt
- seed.txt
- timeline.txt
- result.txt
- sha256.txt
- hub.stdout.log
- hub.stderr.log
- node-a.stdout.log
- node-a.stderr.log
- node-b.stdout.log
- node-b.stderr.log
- pre-peers.json
- pre-a-liveness.json
- pre-a-readiness.json
- pre-a-health.json
- pre-a-status.json
- pre-a-cluster.json
- pre-a-metrics.json
- pre-b-liveness.json
- pre-b-readiness.json
- pre-b-health.json
- pre-b-status.json
- pre-b-cluster.json
- pre-b-metrics.json
- post-peers.json
- post-b-liveness.json
- post-b-readiness.json
- post-b-health.json
- post-b-status.json
- post-b-cluster.json
- post-b-metrics.json
- Node A persistence files when produced;
- Node B persistence files when produced.

Evidence files must not be rewritten to hide a failed observation.

SHA-256 hashes are generated after process shutdown and evidence
finalization.

The sha256.txt manifest does not hash itself.

## Scope limitation

A successful NIRT-02 run demonstrates only the behavior explicitly
observed in this predefined scenario and environment.

It does not by itself demonstrate:

- absence of defects;
- complete security;
- arbitrary fault tolerance;
- Byzantine fault tolerance;
- formal distributed consensus;
- correctness under network partitions;
- multi-machine behavior;
- production readiness;
- independent certification.

An internally executed PASS is internal experimental evidence.

Independent reproduction requires execution by a third party who did
not participate in development of the evaluated instrumentation.
