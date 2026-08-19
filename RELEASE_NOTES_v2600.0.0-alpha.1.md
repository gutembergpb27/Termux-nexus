# Nexus Runtime Platform v2600.0.0-alpha.1

## Status

Audited release candidate.

Tag: `v2600.0.0-alpha.1`

Frozen commit:

`c238311dd8185eb69c00a718a09846d9ba64a1b0`

## Overview

Nexus Runtime Platform v2600 extends the runtime with a Compute execution lifecycle focused on cooperative control, observability, durable completion state and restart recovery.

## Compute lifecycle

The v2600 cycle consolidates:

- cooperative task cancellation;
- cancellation tokens exposed by the runtime;
- cooperative task deadlines;
- relative timeout support;
- preservation of cancelled terminal state;
- operational Compute runtime health.

## Durable completion state

Task completion state can be exported and restored through a versioned logical state contract.

Recovery preserves:

- pending tasks;
- completed tasks and results;
- failed tasks and errors;
- cancelled tasks.

Running tasks are recovered as failed after restart because the previous execution context no longer exists.

## Atomic persistence

v2600 introduces `TaskCompletionStore` for atomic persistence of task completion state.

This separates:

- logical completion-state representation;
- atomic persistent storage;
- runtime startup recovery.

## Startup recovery

ComputeRuntime can restore persisted completion state during initialization when a `TaskCompletionStore` is configured.

Persistent recovery remains opt-in and existing runtime construction without persistent storage remains supported.

## Validation

Final post-merge validation of the frozen release candidate:

```text
534 passed, 1 xfailed
```

The final ComputeRuntime restart-recovery smoke validation also completed successfully.

## Integrated development sequence

- PR #51 — cooperative task deadlines;
- PR #52 — relative task timeout;
- PR #53 — Compute runtime operational health;
- PR #54 — durable task completion state;
- PR #55 — atomic completion-state storage;
- PR #56 — ComputeRuntime startup recovery.

## Release boundary

The frozen release candidate is:

- tag: `v2600.0.0-alpha.1`;
- commit: `c238311dd8185eb69c00a718a09846d9ba64a1b0`.

Changes made after this tag do not alter the historical contents of the tagged release candidate.

The next architecture cycle is v2700.

## Production status

v2600.0.0-alpha.1 is an Alpha release candidate intended for technical evaluation and engineering validation.

It must not be represented as a production-stable release.
