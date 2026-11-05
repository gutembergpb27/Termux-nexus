# Nexus V2700 — W08-B Cluster Mode Migration (`NEXUS_CLUSTER_MODE`)

Status: introduced by PR-B (W08-B). Date: 2026-11-04.
Scope: configuration and fail-closed behavior only.

Nothing in this change implements or certifies distributed consensus.
No configuration enables distributed writes.

## 1. Why this changed

Before W08-B the runtime read `NEXUS_CLUSTER_SIZE` with a default of `1`
and treated N = 1 as a trusted single-node deployment. A multi-node
deployment that omitted the variable therefore ran with majority 1, local
writes enabled and the legacy unauthenticated `STATE_SUMMARY` /
`SYNC_BATCH` sync enabled (W08-A finding F1). QS-C01 did not protect it.

## 2. New behavior

`nexus_cluster_mode.py` resolves the mode from `NEXUS_CLUSTER_MODE` and
`NEXUS_CLUSTER_SIZE`:

| Configuration | Mode | Local writes | Legacy peer sync | Promotion |
|---|---|---|---|---|
| neither variable set | unconfigured | blocked | blocked | blocked |
| only `NEXUS_CLUSTER_SIZE=1` (old default) | unconfigured | blocked | blocked | blocked |
| `NEXUS_CLUSTER_MODE=single` (size absent or 1) | single | allowed* | blocked | allowed if no other peer is visible |
| `NEXUS_CLUSTER_MODE=distributed` + size ≥ 2 | distributed | blocked | blocked | unchanged hub-visibility gate |
| only `NEXUS_CLUSTER_SIZE` ≥ 2 (legacy launch scripts) | distributed | blocked | blocked | unchanged hub-visibility gate |
| anything else | — | node refuses to start (`ValueError`) | | |

\* refused with `single_mode_peer_conflict` while the hub lists any other
node, and with `single_mode_hub_view_invalid` when the hub returns a
malformed peer list.

Invalid examples that refuse to start: `NEXUS_CLUSTER_MODE=solo`,
`single` with `NEXUS_CLUSTER_SIZE=3`, `distributed` without a size or with
size 1, `NEXUS_CLUSTER_SIZE=0`, `abc`, `3.0`, `+3`.

Legacy peer sync is disabled in **every** mode, including `single`.
Blocked writes are logged as `distributed_write_blocked node=… reason=…`
and the payload is not persisted.

## 3. What `single` does and does not mean

`single` is an operator assertion that this is the only node. It is not a
safety mechanism:

- the runtime cannot prove that no other node exists;
- the hub peer list is unauthenticated and may be empty because the hub is
  down, partitioned or not shared, so an empty list proves nothing;
- visible peers are only used to *refuse* writes and promotion;
- running `single` on two or more nodes creates independent writers whose
  logs diverge.

Hub visibility is never treated as proof of quorum, in any mode. A node
promoted to MASTER in distributed mode gains no write authority.

## 4. Migrating existing installations

| Existing setup | Impact after upgrade | Action |
|---|---|---|
| One node, no cluster variables (relied on the old default) | intake writes are refused (`cluster_mode_unconfigured`); a FOLLOWER never promotes | if, and only if, this is truly the only node, set `NEXUS_CLUSTER_MODE=single` |
| One node with `NEXUS_CLUSTER_SIZE=1` | same as above | same as above |
| Several nodes with `NEXUS_CLUSTER_SIZE=N` (N ≥ 2) | unchanged: writes and sync were already blocked by QS-C01 | optionally add `NEXUS_CLUSTER_MODE=distributed` to make it explicit |
| Several nodes without any cluster variable | before: unsafe (each node wrote locally and accepted unauthenticated sync); now: fail-closed | set `NEXUS_CLUSTER_MODE=distributed` and `NEXUS_CLUSTER_SIZE=N`; do **not** set `single` |
| Followers that relied on the legacy N = 1 sync to copy the master's log | log copying stops; liveness uses the authenticated `MASTER_PROBE` | none available yet; no safe replication exists |

Existing stores remain readable and are not modified: the hash-chained
log, checkpoint and SQLite file are opened exactly as before, health and
recovery work in every mode, and blocked operations do not touch the
store.

`setup_node.sh` deliberately does not set the mode. After provisioning,
set it explicitly, for example with `sudo systemctl edit nexus`:

```ini
[Service]
Environment=NEXUS_CLUSTER_MODE=distributed
Environment=NEXUS_CLUSTER_SIZE=3
```

`.env.example` documents the variables with every mode commented out; the
runtime does not load `.env` files. `nexus_config.env` (provisioned by
`setup_node.sh`) is only read for `NEXUS_SECRET_KEY` by
`nexus_security.py`; a cluster mode written there is ignored and the node
stays unconfigured (fail-closed). Set the mode in the process environment.

The S1–S5 harness now sets `NEXUS_CLUSTER_MODE=distributed` explicitly for
its child processes, so an operator shell variable cannot change the mode
under test.

### Known affected launchers (not changed by this PR)

These scripts start runtime nodes without any cluster variable. After this
change their nodes start unconfigured: writes are refused and followers
never promote, so demonstrations that expect a promotion will no longer
reach it. This is fail-closed behavior, not a safety regression; updating
them is a follow-up.

| Launcher | Sets today | Effect |
|---|---|---|
| `demo_cluster.py` | nothing | unconfigured; its follower-promotion step will not pass |
| `scripts/run-nirt02.ps1` | nothing | unconfigured |
| `validation/role-recoordination/run.ps1` | nothing | unconfigured |
| `validation/statistical-resilience/physical_runner.py` | `NEXUS_CLUSTER_SIZE=3` | resolves to distributed; behavior unchanged |

To run them as a multi-node experiment, set `NEXUS_CLUSTER_MODE=distributed`
and `NEXUS_CLUSTER_SIZE` to the node count. Do not set `single` on more than
one node.

## 5. Rollback

Reverting PR-B restores the previous behavior, including the unsafe
default described in §1. No data migration is involved in either
direction.

## 6. Validation status

Covered by `tests/test_cluster_mode_fail_closed.py` (behavioral, fakes
and patched constructor; no network) plus updated QS-C01, liveness,
recoordination, sync and rejoin tests. Not revalidated on physical nodes.
