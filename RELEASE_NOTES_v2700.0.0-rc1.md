# Nexus Runtime Platform v2700.0.0-rc1

## Release Candidate 1

This is the first release candidate of the Nexus Runtime Platform v2700
architecture cycle.

V2700 closes four architecture axes:

1. Durable Execution Semantics
2. Distributed Compute Coordination
3. Operational Readiness
4. Security and Transport Hardening

## Durable Execution Semantics

V2700 formalizes contracts for:

- automatic completion persistence;
- explicit retry semantics;
- basic idempotency;
- persistence failure semantics;
- deterministic restart recovery.

## Distributed Compute Coordination

The distributed Compute layer includes:

- leader re-evaluation during recoordination;
- explicit task ownership;
- ownership generation fencing;
- orphan ownership reclamation;
- stale side-effect fencing;
- terminal-state convergence;
- terminal-failure convergence.

## Operational Readiness

The Runtime exposes a stable readiness contract integrated with diagnostics.

Operational state includes:

- runtime health;
- readiness;
- cluster state;
- aggregated metrics.

Cluster peer information is eventually consistent with the Rendezvous Hub
because each node refreshes its local peer view asynchronously.

## Security and Transport Hardening

The V2700 security boundary documents and validates:

- required shared-secret authentication;
- HMAC message integrity;
- nonce validation;
- timestamp validation;
- replay protection;
- authenticated Compute requests and responses;
- framed TCP transport;
- endpoint validation.

The current architecture does not claim TLS confidentiality, PKI, mTLS or
per-node cryptographic identities.

## Real Multi-Node Release Validation

The release gate executed a real multi-process smoke with:

- authenticated Rendezvous Hub;
- NO-WIN-A as initial MASTER;
- NO-WIN-B as FOLLOWER;
- independent HTTP endpoints;
- real TCP listeners;
- real peer registration;
- controlled MASTER termination;
- automatic FOLLOWER promotion;
- post-failover topology convergence.

The validation demonstrated successful convergence before and after failover.

The `/cluster` endpoint was also explicitly certified as eventually consistent
with the Hub peer view.

## Automated Validation

Integrated V2700 development baseline:

    586 passed, 1 xfailed

The expected-failure test remains intentionally documented:

    tests/test_integrity.py::test_recover_state_does_not_yet_reject_coordinated_log_and_checkpoint_rollback

This test documents the known integrity boundary where coordinated rollback of
both the log and checkpoint requires an authenticated external anchor outside
the restorable state set.

This limitation must not be represented as solved.

## CI Lineage Note

One historical post-merge CI execution for the stale side-effect fencing
contract was affected by a GitHub Actions scheduling anomaly and remained
queued without jobs.

Later integrated CI runs successfully exercised the merged implementation.
Those later runs do not retroactively change the historical anomalous run.

## Package Version

Python package version:

    2700.0.0rc1

Planned frozen Git tag:

    v2700.0.0-rc1

The tag must be created only after the release changeset is merged and the exact
merged commit passes post-merge and local release certification.

## Release Status

V2700.0.0 RC1 is a pre-release intended for technical evaluation,
interoperability validation and controlled external testing.

It must not be represented as a production-stable release.