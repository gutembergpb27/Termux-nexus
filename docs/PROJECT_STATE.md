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
