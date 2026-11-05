# Nexus Runtime Platform v2700.0.0-rc2

## Release candidate 2

This is the second release candidate of the Nexus Runtime Platform V2700 architecture cycle.

RC2 preserves the architecture contracts established by RC1 and incorporates the validation, coordination, failover, quorum-safety, degraded-state, and certification work integrated into `v2700-dev` after the frozen RC1 baseline.

## Package identity

Python package version:

    2700.0.0rc2

Git release tag planned after release certification:

    v2700.0.0-rc2

## RC1 continuity

The original RC1 remains frozen and historically preserved as:

    v2700.0.0-rc1

RC2 does not rewrite or replace the RC1 release record.

## Post-RC1 validation and hardening

The V2700 development line after RC1 includes additional work covering:

- independent reproduction and validation protocols;
- real-process and multi-node convergence validation;
- deterministic master-role recoordination;
- old-master rejoin liveness;
- concurrent-promotion safety;
- physical multi-machine failover;
- quorum and split-brain safety;
- degraded-state contracts;
- quorum failover timing measurement and certification.

## Axis 10 certified evidence

The controlled three-node master-loss experiment recorded:

    T0 -> T4: 24209.728 ms

Final convergence:

    NODE-C = MASTER
    NODE-B = FOLLOWER
    active split-brain observed = false

The Axis 10 certification chain is preserved in:

    docs/validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md

## Regression baseline

The RC2 preparation baseline passes the complete automated regression suite:

    645 passed, 1 xfailed

The expected failure remains explicitly documented and is not converted into an artificial pass.

## Release status

RC2 is a pre-release candidate intended for technical validation and release certification.

The `v2700.0.0-rc2` tag must only be created after the RC2 preparation changes are reviewed, integrated into `v2700-dev`, and the post-merge CI succeeds.

## Erratum (2026-11-04)

The statements above are preserved as the original release record. This
erratum clarifies them; it does not change the release.

- The tag `v2700.0.0-rc2` was created on 2026-09-17 and is published as a
  pre-release. The GitHub "Latest" release is still `v2500.0.0`.
- "Concurrent-promotion safety" and "quorum and split-brain safety" refer
  to deterministic candidate selection (highest eligible id) and a
  promotion gate based on the number of peers visible at the rendezvous
  hub, as observed in controlled runs. They are not distributed
  consensus: there is no election term, no vote, no leader fencing and no
  majority commit.
- The Axis 10 timing result and the Axis 11 statistical campaign were
  measured before the QS-C01 fail-closed change and the `MASTER_PROBE`
  liveness check (PR #101, merged 2026-11-04). "Active split-brain
  observed = false" is an operational observation in the controlled
  scenario, not a safety property.
- See
  [docs/NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md](docs/NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md)
  for the W08-A audit findings.