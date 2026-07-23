# Nexus Runtime — Canonical Integrity Baseline C20

## Status

- Branch: `canonical-evidence`
- Baseline commit: `680b03c`
- Tag: `integrity-baseline-c20`
- Final integrity suite: `23 passed, 1 xfailed`
- Environment: Android / Termux / Python 3.14.6 / pytest 9.1.1

## Purpose

This document records the reproducible integrity evidence established by the canonical C1–C20 control sequence.

The baseline demonstrates detection of multiple classes of persisted-state tampering, rollback and partial-update inconsistency.

It does not claim absolute security, formal verification, hardware-backed trust or immunity against an attacker controlling every trust component.

## Demonstrated controls

The test suite demonstrates rejection or detection of:

- tampered transaction payload;
- tampered `prev_hash`;
- tampered rotation anchor;
- tampered rotated history;
- truncated persisted tail;
- reordered blocks;
- deleted intermediate blocks;
- forged inserted blocks;
- replayed valid blocks;
- valid old-snapshot rollback through checkpoint comparison;
- tampered checkpoint height;
- tampered checkpoint tip hash;
- coordinated log + checkpoint rollback when an external anchor is preserved;
- missing configured external anchor;
- tampered external-anchor height;
- tampered external-anchor tip hash;
- corrupted external-anchor JSON;
- log ahead of checkpoint and anchor;
- checkpoint ahead of external anchor;
- partially written checkpoint.

The suite also demonstrates successful recovery of:

- an intact chain;
- a valid rotation-anchor chain;
- a consistent logical state after restart.

## Integrity layers

The baseline contains three distinct verification layers:

1. Hash-linked persisted transaction chain.
2. Local checkpoint containing chain height and tip hash.
3. Optional external anchor configured through `anchor_path`.

These layers have different trust boundaries and must not be treated as equivalent.

## Known limitation

One test remains deliberately marked `xfail`:

`test_recover_state_does_not_yet_reject_coordinated_log_and_checkpoint_rollback`

Without a preserved external anchor, a coordinated restoration of an older valid log and its matching checkpoint remains internally coherent and may be accepted.

This is a documented architectural limit, not a hidden test failure.

When an external anchor is configured and preserved outside the restored set, the corresponding coordinated rollback is detected.

## Trust-boundary statement

The current external anchor is a configurable file outside the database directory.

It is not equivalent to:

- secure hardware;
- TPM-backed monotonic state;
- a trusted remote witness;
- a cryptographically authenticated external service;
- an append-only transparency log.

The demonstrated guarantee therefore depends on the external anchor remaining outside the attacker-controlled rollback set.

## Crash-consistency evidence

The C18 controls demonstrate fail-closed behavior for tested inconsistent states:

- log advanced while checkpoint and anchor remain old;
- log and checkpoint advanced while external anchor remains old;
- checkpoint left partially written.

The C19 control demonstrates correct logical-state recovery after restart when persistence completed consistently.

## Reproducibility

Run:

    python -m py_compile persistence.py tests/test_integrity.py
    python -m pytest tests/test_integrity.py -v

Expected baseline result:

    23 passed, 1 xfailed

## Evidence chain

Recent canonical commits include:

- `5441c1a` — detect coordinated rollback with external anchor
- `39c6728` — reject missing external anchor
- `b7380fa` — reject tampered external anchor
- `11310f0` — reject log ahead of checkpoint and anchor
- `cec368d` — reject checkpoint ahead of external anchor
- `c779b5a` — reject partially written checkpoint
- `680b03c` — recover consistent state after restart

Canonical baseline tag:

`integrity-baseline-c20`

## Conclusion

The C20 baseline establishes a reproducible body of integrity evidence for the Nexus Runtime persistence path.

The demonstrated result is narrower and stronger than a generic security claim: the implementation has been tested against explicitly enumerated tampering, rollback, partial-update and restart scenarios, with one known trust-boundary limitation preserved visibly as an expected failure.
