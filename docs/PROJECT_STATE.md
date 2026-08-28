# Nexus Runtime Platform — Project State

## Current Release Line

- Architecture cycle: `v2700`
- Development branch: `v2700-dev`
- Release candidate: `v2700.0.0-rc1`
- Python package version: `2700.0.0rc1`
- Status: Release Candidate
- Production status: Pre-release

## V2700 Architecture

All four V2700 architecture axes are formally closed:

1. Durable Execution Semantics
2. Distributed Compute Coordination
3. Operational Readiness
4. Security and Transport Hardening

## Durable Execution

The Compute runtime includes durable completion persistence, explicit retry
semantics, basic idempotency, persistence failure semantics and deterministic
restart recovery.

## Distributed Coordination

Distributed execution includes leader re-evaluation, explicit ownership,
generation fencing, orphan reclamation, stale side-effect fencing and terminal
success/failure convergence.

## Operational Readiness

Runtime readiness is exposed as a stable public contract and is integrated with
diagnostics.

The platform exposes health, readiness, cluster information and aggregated
runtime metrics.

Cluster membership views are eventually consistent with the Rendezvous Hub.

## Security Boundary

Authenticated communication uses a configured shared secret with HMAC, nonce,
timestamp validation and replay protection.

Compute requests and responses are authenticated.

Framed TCP transport is not itself an authentication or confidentiality layer.

The current architecture does not claim TLS, PKI, mTLS or per-node
cryptographic identity.

## Multi-Node Release Gate

A real multi-process release smoke demonstrated:

- authenticated Hub startup;
- MASTER and FOLLOWER operation;
- two-node discovery;
- real TCP listeners;
- cluster convergence;
- controlled MASTER failure;
- automatic FOLLOWER promotion;
- post-failover Hub convergence;
- post-failover `/cluster` convergence;
- clean process and port cleanup.

The multi-node release criterion is satisfied.

## Automated Validation

Integrated development baseline:

    586 passed, 1 xfailed

The expected failure documents the coordinated log-and-checkpoint rollback
boundary requiring an authenticated external anchor outside the restorable
state set.

## RC1 Release Process

Planned package version:

    2700.0.0rc1

Planned tag:

    v2700.0.0-rc1

The tag must only be created after:

1. local release validation;
2. package build validation;
3. release PR review;
4. PR CI success;
5. merge into `v2700-dev`;
6. post-merge CI success;
7. exact merged-SHA certification.

## Source of Truth

The engineering source of truth is:

1. versioned source code;
2. automated tests;
3. continuous integration results;
4. Git history and release tags;
5. architecture and release documentation.