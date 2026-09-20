# Nexus Runtime Platform V2700
## Three-Node Master-Loss Resilience Case Study

### Status

This case study documents a controlled and reproducible resilience
experiment performed with Nexus Runtime Platform V2700.

It summarizes measured evidence. It does not claim that the observed
results generalize to every deployment, workload, network, hardware
configuration or failure mode.

## Scenario

The experiment uses a three-node Nexus cluster:

- NODE-A: initial MASTER
- NODE-B: FOLLOWER
- NODE-C: FOLLOWER

The experiment deliberately terminates NODE-A and observes the cluster
through detection, leadership recoordination and external convergence.

The controlled sequence is:

1. establish an exact three-node baseline;
2. verify NODE-A as the single initial MASTER;
3. terminate NODE-A;
4. observe master-loss detection;
5. observe leadership promotion;
6. verify final convergence;
7. classify and preserve the run evidence.

## What was measured

The physical measurement model uses the following events:

- T0: controlled loss of the original MASTER;
- T1: master absence detected;
- T3: replacement MASTER promoted;
- T4: converged replacement leadership externally observed.

The statistical campaign records:

- t0_to_t1: failure-to-detection interval;
- t1_to_t3: detection-to-promotion interval;
- t3_to_t4: promotion-to-external-convergence interval;
- t0_to_t4: complete measured failover interval.

The methodology distinguishes stale role information in the Rendezvous
Hub registry from simultaneous live operational masters.

## Frozen methodology

Methodology Git SHA:

    17d3329cb4ccaea19167e36a9dfdfcc63a19afdb

Campaign Git SHA:

    a030dbe03fa287c1653d9ea22598bcf6f1ec5c82

The campaign population contains the physical samples run-011 through
run-039.

run-010 is preserved as an incomplete historical harness artifact. It
contains no benchmark summary and is not part of the statistical
population.

No unsuccessful physical measurement was removed from the statistical
population: all 29 physical samples that produced campaign measurements
were classified as valid.

## Campaign results

| Result | Observed |
|---|---:|
| Physical samples | 29 |
| Valid samples | 29 |
| Invalid samples | 0 |
| Converged samples | 29 |
| Operational split-brain observations | 0 |
| NODE-C promotions | 29 |

All 29 analyzed physical samples reached the convergence criterion.

Under the campaign's operational-liveness semantics, no simultaneous
live operational masters were observed.

NODE-C was selected as the replacement MASTER in all 29 samples.

## Timing results

| Metric | n | Min ms | Max ms | Mean ms | Median ms | Stdev ms | P95 ms | P99 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t0_to_t1 | 29 | 21458.885 | 21670.404 | 21585.598 | 21585.418 | 53.210 | 21652.395 | 21665.460 |
| t1_to_t3 | 29 | 0.060 | 0.133 | 0.076 | 0.070 | 0.015 | 0.101 | 0.125 |
| t3_to_t4 | 29 | 9820.210 | 9967.737 | 9906.596 | 9902.135 | 37.426 | 9962.400 | 9966.853 |
| t0_to_t4 | 29 | 31367.022 | 31614.804 | 31492.270 | 31491.374 | 64.575 | 31584.133 | 31607.337 |

The mean complete T0-to-T4 interval in this campaign was approximately
31.49 seconds.

Most of that interval came from failure detection and subsequent
external convergence. Detection-to-promotion itself was very short in
the recorded event model.

These timings characterize this controlled environment only.

## Evidence and integrity

The canonical statistical aggregate is:

    validation/statistical-resilience/axis11-statistical-campaign.json

The aggregate contains the SHA-256 digest of every benchmark summary
included in the statistical population.

The Axis 11 certification is:

    docs/validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md

The preceding single-run quorum timing certification is:

    docs/validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md

Raw evidence directories are preserved separately from the certification
commit.

## Reproducibility

Reproduction means repeating the same class of experiment using the
documented topology, source, methodology and measurement semantics.

It does not mean that another machine must reproduce identical timing
values.

The frozen Axis 11 tooling includes:

    validation/statistical-resilience/physical_runner.py
    validation/statistical-resilience/statistical_resilience.py
    validation/statistical-resilience/campaign_runner.py

Associated automated contracts are located in:

    tests/test_statistical_resilience.py
    tests/test_statistical_resilience_runner.py
    tests/test_statistical_resilience_campaign.py

## Security boundary

Nexus distributed communication uses a configured shared secret with
HMAC authentication, nonce and timestamp validation, and replay
protection.

The current architecture does not claim TLS confidentiality, PKI, mTLS
or per-node cryptographic identity.

Framed TCP transport must not be interpreted as an authentication or
confidentiality mechanism by itself.

## Known integrity boundary

The persistence integrity model retains a documented limitation:
coordinated rollback of both log and checkpoint requires an authenticated
external anchor outside the restorable state to provide rollback
detection across that boundary.

This case study does not reclassify that limitation as solved.

## Interpretation boundary

This campaign demonstrates repeatable behavior for one controlled
three-node master-loss scenario.

It provides evidence for:

- controlled MASTER-loss detection;
- deterministic leadership recoordination in the observed topology;
- successful convergence in all measured campaign samples;
- absence of observed operational split-brain under the defined
  measurement semantics;
- reproducible evidence generation and statistical aggregation.

It does not establish universal fault tolerance, Byzantine fault
tolerance, arbitrary network-partition safety, deterministic timing on
different hardware, or production suitability for every environment.

## Canonical integration

The Axis 11 certification was integrated through PR #91.

Canonical merge commit:

    f1d779699760b522d6e1b67355bd5f0bbf03ca98

The post-merge Nexus Runtime CI completed successfully for that
integration.

## Further reading

- `README.md`
- `docs/PROJECT_STATE.md`
- `docs/NEXUS_V2700_ARCHITECTURE_PLAN.md`
- `docs/NEXUS_V2700_SECURITY_TRUST_BOUNDARY.md`
- `docs/validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md`
- `docs/validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md`
