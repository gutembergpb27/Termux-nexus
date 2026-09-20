# Nexus Runtime Platform V2700
## Technical Positioning and Distributed-Systems Context

### Purpose

This document positions Nexus Runtime Platform V2700 within the broader
distributed-systems landscape.

It is not a claim that Nexus is a replacement for etcd, Consul, or the
Raft consensus algorithm.

Those technologies operate at different abstraction layers and solve
different primary problems.

The useful comparison is therefore based on architectural properties,
responsibilities and demonstrated behavior rather than a direct
product-performance ranking.

## Nexus V2700

Nexus V2700 is an experimental distributed runtime platform centered on
durable execution and coordinated Compute work.

Its implemented and tested areas include:

- durable execution semantics;
- persistence and restart recovery;
- retry and idempotency contracts;
- distributed Compute ownership;
- generation fencing;
- stale side-effect protection;
- orphan reclamation;
- cluster role recoordination;
- health, readiness and cluster diagnostics;
- authenticated transport using a shared secret and HMAC;
- controlled physical resilience experiments.

Nexus currently uses MASTER/FOLLOWER coordination.

This terminology must not be interpreted as a claim that Nexus
implements the Raft consensus algorithm.

## etcd

etcd is a distributed key-value store designed around strongly
consistent replicated state.

Its documented consistency model includes linearizable operations by
default for operations other than specific categories such as watches.
Linearized operations rely on the Raft consensus process.

Clients may request serializable reads when lower latency or higher read
throughput is preferred over the most current quorum-backed state.

The primary abstraction is therefore replicated key-value state, not
distributed execution of application jobs.

Official references:

- https://etcd.io/docs/v3.4/learning/api_guarantees/
- https://etcd.io/

## Consul

Consul is a service-networking and service-discovery platform.

Its architecture separates a control plane from the workload data
plane. Server agents maintain authoritative cluster information and use
Raft for consensus.

Within the Consul server peer set:

- followers can participate in leader elections;
- a candidate requires quorum to become leader;
- the leader maintains the authoritative Raft log;
- log entries are replicated to peers;
- an entry is committed after durable storage on quorum;
- loss of quorum prevents new log entries from being committed.

HashiCorp documents that a three-server Raft cluster can tolerate one
server failure while retaining quorum.

The primary abstraction is service/network control-plane state rather
than execution of arbitrary Compute jobs.

Official references:

- https://developer.hashicorp.com/consul/docs/architecture
- https://developer.hashicorp.com/consul/docs/concept/consensus
- https://developer.hashicorp.com/consul/docs/architecture/backend

## Raft

Raft is a consensus algorithm for managing a replicated log.

Its conceptual roles include leader, follower and candidate, and its
design separates areas such as leader election, log replication and
safety.

Raft is therefore not a directly comparable runtime product.

Nexus must not claim Raft's formal safety or quorum properties unless
those properties are separately implemented and demonstrated.

Official reference:

- https://raft.github.io/

## Property Matrix

| Property | Nexus V2700 | etcd | Consul | Raft |
|---|---|---|---|---|
| Primary abstraction | Distributed execution runtime | Distributed KV store | Service networking and discovery | Consensus algorithm |
| Leader-based coordination | Yes | Yes, through Raft | Yes, through Raft servers | Yes |
| Formal Raft implementation claimed | No | Yes | Yes | Defines it |
| Quorum-backed replicated log | Not claimed as Raft | Yes | Yes | Core mechanism |
| Durable state | Nexus persistence model | Replicated KV state | Persistent Raft state | Defines replicated-log semantics |
| Distributed job execution | Core Nexus concern | Not primary abstraction | Not primary abstraction | Outside scope |
| Retry/idempotency execution contracts | Implemented for Nexus Compute semantics | Different API semantics | Different operational semantics | Outside scope |
| Compute ownership/fencing | Nexus execution concern | Not equivalent | Not equivalent | Outside scope |
| Service discovery | Limited Nexus cluster/rendezvous mechanisms | Not primary abstraction | Core capability | Outside scope |
| Leader-loss handling | Physically demonstrated in controlled Nexus campaign | Raft mechanism | Raft mechanism | Defined by algorithm |
| Formal consensus safety claim | No | Raft-backed | Raft-backed | Yes, within model and assumptions |
| Current Nexus-equivalent physical benchmark | 29-sample campaign | Not performed | Not performed | Not applicable |

## What Nexus Has Demonstrated

The V2700 Axis 11 campaign exercised one controlled physical topology:

- three Nexus nodes;
- NODE-A initially acting as MASTER;
- NODE-B and NODE-C acting as FOLLOWER nodes;
- deliberate loss of NODE-A;
- observation of failure detection;
- leadership recoordination;
- observation of external convergence.

The certified campaign population contains 29 physical samples,
run-011 through run-039.

Results:

| Measurement | Result |
|---|---:|
| Physical samples | 29 |
| Valid samples | 29 |
| Converged samples | 29 |
| Operational split-brain observations | 0 |
| NODE-C promotions | 29 |
| Mean T0-to-T4 | 31492.270 ms |
| P95 T0-to-T4 | 31584.133 ms |
| P99 T0-to-T4 | 31607.337 ms |

These are Nexus measurements from the controlled campaign.

They are not etcd, Consul or Raft performance comparisons.

## What Nexus Has Not Demonstrated

The current evidence does not establish:

- equivalence to Raft consensus;
- formal consensus safety;
- Byzantine fault tolerance;
- arbitrary network-partition safety;
- universal split-brain prevention;
- linearizable distributed storage equivalent to etcd;
- Consul-equivalent service discovery or service mesh behavior;
- identical behavior across arbitrary hardware and networks;
- production suitability for every environment;
- performance superiority over established distributed systems.

These boundaries are intentional.

A narrower claim supported by reproducible evidence is stronger than an
unsupported broader claim.

## Why Direct Timing Comparison Would Be Invalid Today

The approximately 31.49-second mean Nexus T0-to-T4 measurement uses a
specific Nexus event model and controlled environment.

A published etcd leader-election time or Consul recovery time would not
automatically represent the same measurement.

A defensible comparative benchmark would require, at minimum:

1. equivalent hardware and operating environment;
2. equivalent cluster size;
3. an explicitly equivalent failure injection;
4. equivalent definitions of start and completion;
5. comparable workload and persistence conditions;
6. repeated samples;
7. preservation of unsuccessful runs;
8. common statistical treatment.

Until such a benchmark exists, this project does not use unrelated
published latency figures to rank Nexus against those systems.

## Current Nexus Differentiation

The technically relevant Nexus characteristic is not that it
reimplements etcd or Consul.

Its current direction combines several concerns inside one experimental
runtime:

    execution
        +
    durable persistence
        +
    retry/idempotency semantics
        +
    ownership and fencing
        +
    restart recovery
        +
    cluster recoordination
        +
    authenticated node communication
        +
    reproducible physical evidence

This combination is the useful subject for further evaluation.

Whether that combination provides an advantage for a particular
production workload requires workload-specific comparative testing.

## Evidence Chain

The current public evidence chain includes:

- automated contracts;
- continuous integration;
- architecture documentation;
- physical multi-process validation;
- Axis 10 quorum/failover timing evidence;
- Axis 11 statistical resilience certification;
- a 29-sample physical campaign;
- a public resilience case study.

Primary Nexus documents:

- `docs/NEXUS_V2700_ARCHITECTURE_PLAN.md`
- `docs/PROJECT_STATE.md`
- `docs/NEXUS_V2700_RESILIENCE_CASE_STUDY.md`
- `docs/validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md`
- `docs/validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md`
- `validation/statistical-resilience/axis11-statistical-campaign.json`

## Security Comparison Boundary

Nexus currently authenticates distributed communication using a
configured shared secret, HMAC, nonce/timestamp validation and replay
protection.

It does not currently claim TLS confidentiality, PKI, mTLS or per-node
cryptographic identity.

Security comparisons with mature distributed systems must therefore
separate authentication, confidentiality, authorization and identity
instead of treating "secure transport" as one undifferentiated
property.

## Integrity Boundary

Nexus persistence testing documents an important boundary around
coordinated rollback of both log and checkpoint.

Detecting that class of rollback across a restorable state boundary
requires an authenticated external anchor outside the state being
restored.

The existence of the physical resilience campaign does not remove this
integrity boundary.

## Interpretation

The strongest current positioning for Nexus V2700 is:

> An experimental distributed runtime that combines durable Compute
> execution semantics, recovery, coordination and authenticated
> communication, with a growing body of reproducible physical
> resilience evidence.

This description intentionally avoids claiming that Nexus is a
consensus-system replacement or that its current evidence establishes
production equivalence with etcd or Consul.

## Next Comparative Step

A future comparative experiment can test equivalent failure-recovery
properties across Nexus and selected established systems.

That experiment should define the common measurement contract before
collecting results.

Until then, architectural comparison and Nexus's own measured evidence
remain separate evidence classes.
