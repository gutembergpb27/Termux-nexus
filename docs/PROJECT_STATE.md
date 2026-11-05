# Nexus Runtime Platform - Project State

## Current Release Line

- Architecture cycle: `v2700`
- Release candidate: `v2700.0.0-rc2`
- Python package version: `2700.0.0rc2`
- Release status: Release Candidate
- Canonical branch: `main`

V2700 RC2 was promoted to `main`. Subsequent validation and documentation
work, including the Axis 11 statistical resilience certification, has
also been integrated into `main`.

## V2700 Architecture

The four V2700 architecture axes are formally closed:

1. Durable Execution Semantics
2. Distributed Compute Coordination
3. Operational Readiness
4. Security and Transport Hardening

## Durable Execution

The Compute runtime includes durable completion persistence, explicit
retry semantics, basic idempotency, persistence failure semantics and
deterministic restart recovery.

## Distributed Coordination

Distributed execution includes leader re-evaluation, explicit ownership,
generation fencing, orphan reclamation, stale side-effect fencing and
terminal success/failure convergence.

## Operational Readiness

Runtime readiness is exposed as a public contract and integrated with
diagnostics.

The platform exposes health, readiness, cluster information and
aggregated runtime metrics.

Cluster membership views are eventually consistent with the Rendezvous
Hub.

## Security Boundary

Authenticated communication uses a configured shared secret with HMAC,
nonce, timestamp validation and replay protection.

Compute requests and responses are authenticated.

Framed TCP transport is not itself an authentication or confidentiality
layer.

The architecture does not claim TLS, PKI, mTLS or per-node
cryptographic identity.

## Post-RC2 Work: QS-C01 Fail-Closed and P1 Master Liveness

Status (updated 2026-11-04): merged to `main` via PR #101 (2026-11-04,
merge `df5e560`); not tagged; not physically revalidated.

Original status, before the merge: implemented on branch
`fix/v2700-qs-c01-master-liveness`; not yet released, not yet physically
revalidated.

### QS-C01 fail-closed distributed sync and writes

No quorum-commit protocol exists yet. When `NEXUS_CLUSTER_SIZE` is not
exactly the integer `1`, the runtime refuses:

- applying `SYNC_BATCH` (`handle_sync_batch`);
- serving blocks for `STATE_SUMMARY` (`handle_state_summary`);
- pulling state from the MASTER (`sync_from_peer`);
- persisting intake writes (`shell_intake_loop`), with an explicit
  terminal message stating that the payload was not persisted.

`NEXUS_CLUSTER_SIZE=1` keeps the legacy single-member behavior.

### P1 regression and fix

The first QS-C01 version made MASTER liveness depend on
`sync_from_peer`, which was now always blocked for N > 1. With a
three-member configuration, a FOLLOWER therefore never refreshed MASTER
liveness and promoted itself after 15 s while the legitimate MASTER was
alive.

The fix separates liveness from replication:

- N = 1: liveness still comes from successful sync (legacy path).
- N > 1: sync stays blocked; the FOLLOWER sends an authenticated
  `MASTER_PROBE` over TCP and refreshes liveness only after a
  `MASTER_PROBE_ACK` that passes HMAC, TTL and replay checks, comes from
  the advertised MASTER identity, is bound to the probe request and
  sender, and reports role `MASTER`.
- The probe never reads or writes persistent state.
- Hub advertisement alone still does not refresh liveness.

### Local validation (isolated copy, not CI, not physical)

- Behavioral reproduction with a real MASTER on loopback TCP:
  N = 3 with live MASTER ends `FOLLOWER` (pre-fix: `MASTER`);
  N = 3 with dead MASTER still fails over; N = 1 unchanged.
- 48 new tests (`tests/test_master_liveness_probe.py`,
  `tests/test_qs_c01_fail_closed.py`), stable across repeated runs.
- Full suite (versioned tests only): 858 passed, 1 xfailed, as in CI
  run 41560608327. An earlier local figure of 870 included 12 tests
  from a file that is not under version control.
- Current CI on `main` (updated 2026-11-04): workflow "Nexus Runtime
  CI", run 41912549086, SUCCESS. Required checks (ruleset
  `main-protection-v2700`):
  - `test-and-build` (`tests/`): 858 passed, 1 xfailed;
  - `W05/W06 S1-S5 harness tests`: 90 + 17 = 107 passed;
  - `W07 experimental hub hardening tests`: 60 passed;
  - total: 1,025 passed, 1 xfailed.

  CI runs only on `windows-latest` with Python 3.14. The xfail is
  `tests/test_integrity.py:411` (coordinated log + checkpoint rollback
  requires an external anchor) and is unrelated to consensus.

### Known limitations

- The probe proves liveness only. It is not an election term, vote or
  quorum commit. Concurrent MASTER roles are **not** guaranteed to
  converge:
  - Quorum is counted from hub visibility, and the advertised MASTER
    counts toward it even when its probe has just failed.
  - Asymmetric partition (a MASTER still heartbeating the hub but
    unreachable from the followers): the highest-id eligible follower
    promotes while the old MASTER is still advertised, so two MASTER
    roles coexist.
  - If the isolated MASTER has the lower id, it yields once it sees the
    new MASTER (`reconcile_master_role`), provided it can still reach
    the hub.
  - If the isolated MASTER has the highest id, the promoted follower
    oscillates for as long as the partition lasts: every 5 s polling
    cycle it yields to the old MASTER and promotes again, because the
    15 s liveness window has already expired. Each promotion starts a
    new intake thread. In a review simulation of the real polling loop,
    the follower was promoted 13 times and demoted 12 times in 16
    cycles. The same behavior exists on `main` before this change.
  - Impact with N > 1 is limited to role instability and thread
    accumulation, because distributed writes and sync stay blocked
    (QS-C01). It becomes a safety issue as soon as writes are enabled;
    terms, votes and fencing are required first.
- Authentication is a cluster-wide shared secret: any holder of the
  secret can sign an ACK. There is no per-node identity and no TLS.
- The Axis 10/11 timing results were measured before this change and do
  not characterize it. A new three-node physical validation is required.
- With `NEXUS_CLUSTER_SIZE=1`, `SYNC_BATCH` and `STATE_SUMMARY` remain
  unauthenticated (pre-existing, tracked separately).

This work is not a production-readiness certification.

## W05–W07 Validation Harness and Experimental Hub Hardening (PR #102)

Status (2026-11-04): merged to `main` via PR #102 (2026-11-04, merge
`dc180e4`); not tagged. Both components are experimental.

- `validation/s1-s5-harness/` (W05/W06): harness for the S1 (no false
  promotion with a live MASTER, N = 3) and S5 (MASTER loss) scenarios
  against the unmodified runtime. It is validated locally only in its
  logic, gates, I/O and orchestration, using stub processes. No S1/S5
  execution of the Nexus runtime has been performed; the versioned
  evidence is BLOCKED at the preflight gates. A PASS would not certify
  distributed consensus.
- `validation/hub-hardening/` (W07): an isolated `HardenedHub` prototype
  (bounded concurrency, timeouts, per-client limit, allowlist, state
  lock, controlled shutdown). It does **not** change the runtime hub
  (`nexus_rendezvous.py`). `INTEGRATION_PROPOSAL.md` is a proposal that
  has not been applied. Its scope is HTTP availability and robustness of
  the hub; it does not validate consensus, replication or fencing.
- Their tests run in CI as separate required checks (see the CI figures
  above).

## Capability Status

Status as of `main` at `dc180e4` (2026-11-04).

| Capability | Status |
|---|---|
| Hash-chained append log | Implemented |
| HMAC envelopes with TTL and replay protection (shared secret) | Implemented |
| QS-C01 block of distributed sync and writes for `NEXUS_CLUSTER_SIZE` ≠ 1 | Implemented (not physically revalidated) |
| Explicit fail-closed cluster mode (`NEXUS_CLUSTER_MODE`, W08-B, PR #104) | Implemented (not physically revalidated) |
| Authenticated MASTER liveness probe (`MASTER_PROBE`) | Implemented (not physically revalidated) |
| Compute task worker | Implemented |
| S1–S5 validation harness | Experimental |
| Hardened rendezvous hub | Experimental (not wired into the runtime) |
| Distributed compute dispatcher | Experimental (not wired to the live runtime) |
| In-memory cluster manager | Experimental |
| Distributed consensus | Not proven / absent |
| Persistent election term and vote | Not proven / absent |
| Leader fencing | Not proven / absent |
| Majority commit | Not proven / absent |
| Partition safety | Not proven / absent |
| Per-node cryptographic identity | Not proven / absent |
| Data durability across leader change | Not proven / absent |

## Known Risks (W08-A)

Findings of the W08-A read-only code audit of `main` at `dc180e4`. See
[NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md)
for file and line references.

- **F1:** `NEXUS_CLUSTER_SIZE` defaults to `1`. A multi-node deployment
  that omits it runs with majority 1, local writes enabled and the legacy
  unauthenticated sync enabled; QS-C01 does not apply. An explicit
  fail-closed cluster mode is planned (PR-B, in preparation).
  **Resolved (2026-11-05) by PR #104** (merge `9218889`): `NEXUS_CLUSTER_MODE`
  is now explicit; a missing mode blocks writes, peer sync and promotion;
  legacy sync is disabled in every mode; invalid configuration refuses to
  start. `single` remains an operator assertion. See
  [NEXUS_V2700_W08B_CLUSTER_MODE_MIGRATION.md](NEXUS_V2700_W08B_CLUSTER_MODE_MIGRATION.md).
- **F2:** promotion is not an election. "Quorum" is the hub-visible peer
  count from an unauthenticated `GET /peers`; no votes, no term.
- **F3:** two MASTER roles can coexist under asymmetric partition and are
  resolved afterwards by lexicographic id; a restarted old master with a
  greater id retakes authority.
- **F5:** log rotation deletes the previous rotated file, so older
  history is lost; recovery reads only the active file; the checkpoint
  write is not atomic.
- **F6:** the core TCP server has no socket timeout and starts one
  unbounded thread per connection; the web panel binds `0.0.0.0`
  without authentication, with CORS `*`.
- **F7:** one cluster-wide HMAC secret; no per-node identity; roles are
  self-declared to the hub.
- **F8:** stale runtime copies without QS-C01 exist outside the tracked
  runtime; tracked `archived_patches/*.py` rewrite
  `nexus_distributed_core.py` if run from the repository root;
  `chaos_runner.py` runs `rm -rf outputs/*`.

## Physical Multi-Node Validation

The V2700 validation history includes physical and real-process cluster
experiments covering discovery, convergence, leadership recoordination,
master loss and post-failure convergence.

Axis 10 established a controlled three-node master-loss timing
experiment.

Axis 11 extended that scenario into a frozen statistical campaign.

## Axis 11 Statistical Resilience

The certified Axis 11 population contains 29 physical samples,
`run-011` through `run-039`.

Observed campaign outcome:

- 29 physical samples;
- 29 valid;
- 29 converged;
- 0 operational split-brain observations;
- NODE-C promoted in all 29 samples.

`run-010` remains preserved as an incomplete historical harness
artifact and is not included in the statistical population.

Mean measured complete failover interval, T0 to T4:

    31492.270 ms

P95 measured complete failover interval:

    31584.133 ms

The results characterize the controlled campaign and must not be
generalized to every topology, network, workload or failure mode.

Note (2026-11-04): the Axis 10 and Axis 11 runs predate QS-C01 and
`MASTER_PROBE`. "0 operational split-brain observations" is an
operational observation in the controlled scenario, not a safety
property; in Axis 10, "quorum" means the hub-visible peer count (W08-A
finding F10).

## Automated Validation

The repository contains automated contracts covering runtime,
persistence, cluster coordination, distributed Compute, security,
transport, degraded states, quorum behavior and the Axis 11 statistical
resilience methodology.

The authoritative current regression count is the result of the current
CI/test execution. Historical test counts in older release records remain
historical evidence and are not used here as a current baseline.

## Known Integrity Boundary

The integrity suite documents coordinated rollback of log and checkpoint
as requiring an authenticated external anchor outside the restorable
state set.

This remains an explicit architectural boundary.

## Release and Integration State

V2700 RC2 tag:

    v2700.0.0-rc2

RC2 was promoted to `main` through the controlled release process.

Axis 11 certification was subsequently integrated through PR #91.

Axis 11 canonical merge:

    f1d779699760b522d6e1b67355bd5f0bbf03ca98

QS-C01 fail-closed and P1 master liveness were integrated through PR #101
(2026-11-04, merge `df5e560`).

The W05–W07 validation harness and experimental hub hardening were
integrated through PR #102 (2026-11-04, merge
`dc180e49aa418cac4cf97d104a4749201bc08325`).

Neither PR is tagged. The latest tag remains `v2700.0.0-rc2`
(pre-release). The GitHub "Latest" release is still `v2500.0.0`.

## Public Technical Evidence

Primary public technical case study:

    docs/NEXUS_V2700_RESILIENCE_CASE_STUDY.md

Axis 10 certification:

    docs/validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md

Axis 11 certification:

    docs/validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md

Axis 11 aggregate:

    validation/statistical-resilience/axis11-statistical-campaign.json

## Source of Truth

Engineering claims should be grounded in:

1. versioned source code;
2. automated tests;
3. continuous-integration results;
4. Git history and release tags;
5. preserved validation evidence;
6. architecture and certification documentation.

Experimental evidence must be interpreted within the topology,
environment and measurement boundaries under which it was collected.
