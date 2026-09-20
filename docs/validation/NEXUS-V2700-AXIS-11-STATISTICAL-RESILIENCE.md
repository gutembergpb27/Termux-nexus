# Nexus V2700 - Axis 11 Statistical Resilience

## Certification scope

This document records the controlled physical statistical campaign for the three-node master-loss failover experiment.

The statistical population in this certification contains 29 physical samples: `run-011` through `run-039`.

`run-010` is preserved as an incomplete historical run directory. It has no benchmark summary and is not included in the statistical population.

## Frozen provenance

- Methodology Git SHA: `17d3329cb4ccaea19167e36a9dfdfcc63a19afdb`
- Campaign Git SHA: `a030dbe03fa287c1653d9ea22598bcf6f1ec5c82`
- Cluster size: 3 nodes
- Initial master: `NODE-A`
- Followers: `NODE-B`, `NODE-C`
- Failure: controlled termination of `NODE-A`

## Campaign outcome

- Physical samples: **29**
- Valid: **29**
- Invalid: **0**
- Converged: **29**
- Operational split-brain observations: **0**
- Promotion result: `NODE-C` in **29** samples

These results describe this controlled campaign only.
They are not a claim about every deployment, network,
failure mode, workload, or distributed system.

## Timing statistics

| Metric | n | Min (ms) | Max (ms) | Mean (ms) | Median (ms) | Stdev (ms) | P50 (ms) | P90 (ms) | P95 (ms) | P99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| t0_to_t1 | 29 | 21458.885 | 21670.404 | 21585.598 | 21585.418 | 53.210 | 21585.418 | 21651.777 | 21652.395 | 21665.460 |
| t1_to_t3 | 29 | 0.060 | 0.133 | 0.076 | 0.070 | 0.015 | 0.070 | 0.092 | 0.101 | 0.125 |
| t3_to_t4 | 29 | 9820.210 | 9967.737 | 9906.596 | 9902.135 | 37.426 | 9902.135 | 9958.424 | 9962.400 | 9966.853 |
| t0_to_t4 | 29 | 31367.022 | 31614.804 | 31492.270 | 31491.374 | 64.575 | 31491.374 | 31567.792 | 31584.133 | 31607.337 |

## Interpretation

All 29 analyzed physical samples were classified as valid and reached the convergence criterion.

No operational split-brain was observed by the campaign's operational-liveness semantics.

The registry may transiently contain stale role information during failover; the Axis 11 methodology distinguishes registry overlap from simultaneous live operational masters.

Across this campaign, `NODE-C` was the promoted node in all 29 samples.

## Evidence integrity

The aggregate JSON contains the SHA-256 digest of every benchmark summary included in the statistical population.

Raw evidence directories are intentionally preserved outside this certification commit.

Aggregate artifact:

`validation/statistical-resilience/axis11-statistical-campaign.json`

## Reproducibility boundary

The results are tied to the frozen source, methodology, topology, runtime environment and measurement semantics recorded by the evidence.

Reproduction means repeating the same class of controlled experiment under the documented methodology; it does not imply identical timing values on different hardware or environments.
