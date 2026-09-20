# Nexus V2700 - External Resilience Demonstration

## Objective

This page is a navigation layer over the existing certified V2700 evidence.
It does not create a new experiment, sample, benchmark, or certification.

## Scenario

Three-node cluster: NODE-A initially MASTER; NODE-B and NODE-C FOLLOWERs.
After controlled loss of the active MASTER, the survivors recoordinate and
the externally observed topology converges with NODE-C as MASTER.

## Certified observation

- Physical samples: 29 (run011 through run039)
- Valid samples: 29
- Converged samples: 29
- Operational split-brain observed: 0
- NODE-C promotions: 29
- T0-to-T4 mean: 31492.270 ms
- T0-to-T4 median: 31491.374 ms
- T0-to-T4 p95: 31584.133 ms
- T0-to-T4 p99: 31607.337 ms

run010 is preserved as incomplete and is not counted as a physical sample.

## Review path

1. Executive overview:
   `docs/NEXUS_V2700_EXECUTIVE_TECHNICAL_BRIEF.md`
2. Resilience case study:
   `docs/NEXUS_V2700_RESILIENCE_CASE_STUDY.md`
3. Axis 11 certification:
   `docs/validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md`
4. Derived campaign artifact:
   `validation/statistical-resilience/axis11-statistical-campaign.json`
5. Physical methodology:
   `validation/statistical-resilience/physical_runner.py`

## Interpretation boundary

These results belong to the documented Nexus V2700 experiment contract.
They do not establish production certification, universal fault tolerance,
formal Raft equivalence, or performance superiority over other systems.

The original evidence remains authoritative. This page does not regenerate,
replace, rewrite, or extend that evidence.

## Status

Axis 11 remains closed. No run040 is created. Runtime and certified evidence
remain unchanged.
