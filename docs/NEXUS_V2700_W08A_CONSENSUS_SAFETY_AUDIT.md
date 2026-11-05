# Nexus V2700 — W08-A Consensus Safety Audit

Date: 2026-11-04
Status: AUDIT RECORD (read-only)
Audited revision: `main` at `dc180e49aa418cac4cf97d104a4749201bc08325`
(merge of PR #102)

**Nothing in this document certifies distributed consensus.**

## 1. Scope and method

- Read-only code audit of `main` at `dc180e4`. The code was read; it was
  not executed for this audit.
- No tests were executed as part of this audit. Test results quoted below
  come from CI run `41912549086` ("Nexus Runtime CI") on `main`.
- Nothing is certified. The findings describe what the code does as read,
  and what it does not do.
- Line references (`file:line`) refer to the audited revision and may
  drift as the code changes.

Context at the audited revision:

- PR #101 "fix(v2700): prevent false master promotion under QS-C01" merged
  2026-11-04 20:51Z (merge `df5e560`).
- PR #102 "test(v2700): W05-W07 validation harness and experimental hub
  hardening" merged 2026-11-04 21:04Z (merge `dc180e4`).
- Neither is tagged. The latest tag is `v2700.0.0-rc2` (pre-release,
  2026-09-17). The GitHub "Latest" release is still `v2500.0.0`.
- CI run `41912549086` on `main`: SUCCESS. Required checks in ruleset
  `main-protection-v2700`:
  - `test-and-build` (`tests/`): 858 passed, 1 xfailed;
  - `W05/W06 S1-S5 harness tests`: 90 + 17 = 107 passed;
  - `W07 experimental hub hardening tests`: 60 passed;
  - total: 1,025 passed, 1 xfailed. The xfail is
    `tests/test_integrity.py:411` (coordinated log + checkpoint rollback
    requires an external anchor) and is unrelated to consensus.
  - CI runs only on `windows-latest` with Python 3.14.
- QS-C01 and the `MASTER_PROBE` liveness check are on `main` but have
  **not** been physically revalidated on three nodes.

## 2. Architecture as found

- **Rendezvous hub** (`nexus_rendezvous.py`): HTTP registry of peers.
  Registration and heartbeat use HMAC envelopes; `GET /peers` is
  unauthenticated and unsigned. Peers stay listed for up to 30 s after
  their last heartbeat (`PEER_TIMEOUT`).
- **Core node** (`nexus_distributed_core.py`): role (`MASTER` /
  `FOLLOWER`) comes from argv and is self-declared to the hub. A FOLLOWER
  promotes itself after 15 s without master contact. Concurrent MASTER
  roles are reconciled afterwards by lexicographic id.
- **Liveness** (PR #101): for `NEXUS_CLUSTER_SIZE` ≠ 1, an authenticated
  `MASTER_PROBE` / `MASTER_PROBE_ACK` over TCP refreshes master liveness.
  It proves liveness only; it is not a vote, a term or a commit.
- **QS-C01** (PR #101): for `NEXUS_CLUSTER_SIZE` ≠ 1, `SYNC_BATCH`
  application, `STATE_SUMMARY` block serving, follower state pull and
  intake writes are refused.
- **Persistence** (`persistence.py`): hash-chained append log with size
  rotation and a checkpoint.
- **Authentication**: one cluster-wide shared HMAC secret with TTL and
  replay protection. No TLS, no per-node identity.

There is no election protocol, no persistent term or vote, no leader
fencing and no majority commit in the runtime.

## 3. Findings

### F1 — `NEXUS_CLUSTER_SIZE` defaults to `1`

- `nexus_distributed_core.py:72-82`: `NEXUS_CLUSTER_SIZE` defaults to
  `"1"`.
- `nexus_distributed_core.py:404-411`: `_distributed_sync_enabled()`
  returns True only for size == 1.
- A multi-node deployment that omits the variable runs with
  `majority = 1`, local writes enabled and the legacy unauthenticated
  `STATE_SUMMARY` / `SYNC_BATCH` sync enabled. QS-C01 does not protect it.
- The variable is not present in `.env.example` nor in `setup_node.sh`.
- Remediation: an explicit fail-closed cluster mode is planned and in
  preparation as PR-B. It is not on `main`.

### F2 — Promotion is not an election

- `nexus_distributed_core.py:1054-1137`: a FOLLOWER with more than 15 s
  without master contact picks the maximum id among hub-listed FOLLOWERs
  plus itself.
- "Quorum" is the count of ids returned by hub `GET /peers` (plus self)
  compared with `majority`.
- `GET /peers` is unauthenticated and unsigned
  (`nexus_rendezvous.py:381-388`). A dead master stays listed for up to
  30 s.
- There are no votes and no term.

### F3 — Two concurrent MASTER roles are possible

- Under an asymmetric partition (all nodes reach the hub, a follower
  cannot reach the master) the follower promotes while the old master is
  still MASTER.
- The conflict is resolved afterwards by lexicographic id
  (`reconcile_master_role`, `nexus_distributed_core.py:29-64`). This can
  depose a healthy master or oscillate while the partition lasts.
- An old master restarted with role `MASTER` and a greater id retakes
  authority: the role comes from argv and the term is always `0`
  (`nexus_distributed_core.py:146`).
- Old-master rejoin real-process validation is PARKED / FAIL.

### F4 — No term, vote, fencing or majority commit

- The runtime has no persistent term or vote.
- No leader fencing; blocks carry no term.
- `apply_blocks` accepts any valid chain extension.
- No majority commit.
- A MASTER never steps down on quorum loss.
- A persistent term/vote component is being prototyped outside `main`; it
  is not part of the repository.

### F5 — Log rotation loses history; recovery is not robust

- `persistence.py:33-39`: each rotation deletes the previous `.1` file
  (`max_bytes=10240` by default), so older history is permanently lost.
- `recover_state` reads only the active file.
- `_recover_last_hash` silently falls back to genesis on a torn last line.
- The checkpoint write is not atomic.

### F6 — Unbounded network servers

- Core TCP server (`nexus_distributed_core.py:388-398`): no timeout on
  accepted sockets, one unbounded thread per connection, bare `except`.
- `web_panel.py`: binds `0.0.0.0`, unauthenticated,
  `Access-Control-Allow-Origin: *`, single-threaded `HTTPServer`.

### F7 — No per-node identity

- One cluster-wide HMAC secret: any holder can sign as any node.
- Roles are self-declared to the hub.

### F8 — Stale runtime copies without QS-C01

- Untracked local copies (not in the repository, found on the working
  machine): `axis8-transfer/` and
  `validation/old-master-rejoin/parked-candidate-20260903/`.
- Tracked `archived_patches/*.py` scripts rewrite
  `nexus_distributed_core.py` if run from the repository root.
- `chaos_runner.py:10` runs `rm -rf outputs/*`.

### F9 — Tests do not exercise distributed safety

- `tests/test_quorum_promotion_contract.py`,
  `tests/test_quorum_membership_contract.py`,
  `tests/test_concurrent_promotion_safety.py`,
  `tests/test_role_recoordination_polling.py` and most of
  `tests/test_multi_machine_failover_contract.py` inspect source text.
- `tests/test_quorum_behavior_contract.py` tests a re-implementation
  inside the test, not the runtime.
- No test runs two or more cores concurrently, simulates a partition,
  kills a node mid-write, or checks committed data across a leader change.
- `validation/hub-hardening/test_hub_hardening.py:123` pins the Git blob
  hashes of `nexus_distributed_core.py` and `nexus_rendezvous.py`, so any
  runtime change requires updating that test.

### F10 — Axis 10 / Axis 11 evidence predates QS-C01

- The Axis 11 statistical campaign and the Axis 10 timing experiment ran
  before QS-C01 and `MASTER_PROBE`.
- Their "0 split-brain" result is an operational observation in a
  controlled scenario, not a safety property.
- In Axis 10, "quorum" means the hub-visible peer count.

## 4. Invariants

| ID | Invariant | Status at `dc180e4` | Required tests |
|---|---|---|---|
| INV-01 | At most one authorized leader per term. | Does not hold (F2, F3, F4). No term exists. | Concurrent multi-core simulation with asymmetric partition; restart of old leader; two candidates in the same term. |
| INV-02 | Loss of quorum prevents new commits. | Does not hold (F1, F4). No majority commit; MASTER does not step down; with default size 1 local writes are accepted. | Leader isolated from majority attempts a write; write must not be reported committed. |
| INV-03 | Terms and votes never regress after restart. | Does not hold (F4). No persistent term or vote; term is always `0`. | Crash/restart at each persistence point; term and vote must be ≥ the last persisted values. |
| INV-04 | Stale leaders cannot write. | Does not hold (F3, F4). No fencing; blocks carry no term; `apply_blocks` accepts any valid chain extension. | Stale leader sends blocks after a newer term exists; followers must reject them. |
| INV-05 | Committed records are not lost on leader change. | Does not hold (F4, F5). No commit definition; rotation deletes history; recovery reads the active file only. | Kill leader after commit, elect new leader, verify every committed record on the majority, including across log rotation. |
| INV-06 | Node rejoin cannot reintroduce old authority. | Does not hold (F3). Restarted old master with greater id retakes authority; old-master rejoin validation is PARKED / FAIL. | Old master rejoins with role `MASTER` and greater id; it must not regain authority without a newer term. |
| INV-07 | No N > 1 block (QS-C01) is removed before INV-01..INV-06 are demonstrated. | Holds **conditionally**: true only when `NEXUS_CLUSTER_SIZE` is set to a value ≠ 1 (F1). With the default `1`, the block does not apply. | Startup without explicit cluster mode must fail closed (PR-B); regression test that QS-C01 refusals remain active for N ≠ 1. |

## 5. Planned W08-B sequence

Planned order. None of these items is implemented on `main` at the
audited revision.

1. **PR-A** — documentation: this audit and status corrections.
2. **PR-B** — explicit fail-closed cluster mode (F1). In preparation.
3. Persistence without history loss: rotation that keeps history, atomic
   checkpoint, explicit handling of torn records (F5).
4. Quarantine of stale runtime copies and destructive scripts (F8).
5. TCP server timeouts and bounded concurrency (F6).
6. Test hygiene (replace source-text tests with behavioral tests) and a
   Linux CI job (F9).
7. Persistent term and vote (F4).
8. Pure authority state machine plus a deterministic simulator
   (partitions, crashes, restarts).
9. Term in blocks and stale-leader rejection (INV-04).
10. Signed node-to-node messages, with the hub used for discovery only
    (F2, F7).
11. Experimental integration behind a flag that is off by default.

QS-C01 must stay active for N ≠ 1 throughout (INV-07).

## 6. Statement

This document records findings of a read-only audit. It does not certify
distributed consensus, split-brain prevention, partition safety, data
durability across leader change, or production readiness.

**Nothing in this document certifies distributed consensus.**

Related documents:

- [Project state](PROJECT_STATE.md)
- [Distributed commit contract](NEXUS_V2700_DISTRIBUTED_COMMIT_CONTRACT.md)
