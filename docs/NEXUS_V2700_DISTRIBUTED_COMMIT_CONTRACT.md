# Nexus V2700 — Distributed Commit Contract

Status: PROPOSED
Scope: Distributed consensus and persistence
Runtime activation: DISABLED for `NEXUS_CLUSTER_SIZE` ≠ 1 (see §15)

## 1. Objective

Define the minimum safety requirements for distributed
transaction commitment in Nexus Runtime Platform V2700.

## 2. Membership

The cluster has a configured membership.

Majority is calculated as:

majority = floor(cluster_size / 2) + 1

Dynamic peer visibility must not redefine membership.

## 3. Leadership

A node must not become an authoritative leader solely
because other nodes are unreachable.

Leadership requires an election protocol with:

- Persistent election terms.
- One vote per member per term.
- Candidate log freshness checks.
- Majority authorization.
- Rejection of stale leaders.
- Recovery of election state after restart.

## 4. Transaction Proposal

Every proposed transaction must have:

- Unique transaction identifier.
- Leadership term.
- Log index.
- Previous log reference.
- Deterministic payload representation.

## 5. Durable Replication

Followers must:

- Authenticate the sender.
- Validate leadership term.
- Validate the previous log reference.
- Persist the proposed entry durably.
- Return an authenticated acknowledgement.

An acknowledgement is not a commit.

## 6. Commit Rule

A transaction may be committed only when:

- The leader is authorized for the current term.
- A majority of configured members durably stores the entry.
- The entry satisfies the protocol's commit-index and
  leader-term safety rules.
- The commit decision is persisted before success is reported.

## 7. Application Rule

Uncommitted proposals must never be exposed as committed
application state.

Only committed log entries may be applied.

## 8. Failure Handling

If quorum is unavailable:

- No distributed commit is reported.
- Pending proposals remain uncommitted.
- The system must reject unsafe writes.
- A later leader must reconcile pending entries safely.

## 9. Recovery

After restart, a node must recover:

- Current election term.
- Voting state.
- Replicated log.
- Commit index.
- Applied index.

Recovery must preserve committed entries.

## 10. Security

All consensus messages require:

- Authenticated node identity.
- Message integrity.
- Replay protection.
- Term validation.
- Membership authorization.

## 11. Required Tests

- Three-node majority commit.
- Loss of quorum.
- Leader crash before commit.
- Leader crash after commit.
- Stale leader rejection.
- Conflicting proposals.
- Follower restart.
- Leader replacement.
- Network partition.
- Recovery without committed-data loss.

## 12. Activation Policy

Distributed writes and synchronization remain disabled
until the implementation passes the required safety tests.

Existing fail-closed protections must remain active.

## 13. Current Status

The contract is a specification only.

It does not certify that Nexus currently implements
distributed consensus or quorum-based commitment.

## 14. Liveness Is Not Commitment

MASTER liveness detection and replication are separate
mechanisms and must stay separate.

- A liveness proof shows only that the advertised MASTER
  is reachable and still reports the MASTER role.
- A liveness proof must never be counted as an
  acknowledgement, a vote or a commit.
- Blocking replication must not block liveness detection.
  Coupling them caused the P1 regression: with sync
  blocked for N > 1, followers promoted themselves while
  the legitimate MASTER was alive.

Current implementation (merged to `main` via PR #101 on
2026-11-04; not tagged; not physically revalidated on three
nodes). Originally recorded as: branch
`fix/v2700-qs-c01-master-liveness`, not yet released.

- N > 1: authenticated `MASTER_PROBE` / `MASTER_PROBE_ACK`
  exchange (HMAC, TTL, replay protection, identity check,
  request binding, role check). No state is transferred.
- N = 1: legacy liveness through successful sync.

## 15. Fail-Closed Enforcement (QS-C01)

Until Sections 3 to 11 are implemented and tested,
any value of `NEXUS_CLUSTER_SIZE` other than the integer
`1` blocks:

- `SYNC_BATCH` application;
- `STATE_SUMMARY` block serving;
- follower state pull (`sync_from_peer`);
- intake writes.

The behavior is covered by automated tests
(`tests/test_qs_c01_fail_closed.py`) and has not yet been
revalidated on a physical three-node deployment.

Note (2026-11-04, W08-A finding F1): `NEXUS_CLUSTER_SIZE`
defaults to `1` when the variable is not set. A multi-node
deployment that omits it therefore runs with majority 1,
local intake writes enabled and the legacy unauthenticated
`STATE_SUMMARY` / `SYNC_BATCH` sync path enabled; this
section does not protect it. An explicit fail-closed
cluster mode is planned (PR-B, in preparation) and is not
on `main`. See
[NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md).
