# Nexus Runtime Platform V2700 — Multi-WAN 04C: experimental remote Compute execution

**English** · [Português (Brasil)](NEXUS_V2700_MULTIWAN_04C_PT.md)

**Status:** PASS (bounded experiment; operator-reported, see the evidence note)<br>
**Date:** November 22, 2026<br>
**Git base:** `d783a863d7b1ac5db88922726606e75c5d17c4fb`<br>
**Repository:** `gutembergpb27/Termux-nexus`<br>
**Evidence class:** operator-reported. The Windows client figures come from terminal output presented by the operator. The Android figures are an **operator transcript** of terminal output, not a raw log captured and hashed on the device. Raw logs are retained privately and were not independently re-processed for this report.

## Overview

A physical experiment between Windows and a Motorola Edge 40 Neo (Android 15 / Termux) evaluated the interoperability of existing Nexus Runtime Platform V2700 components. The client used `TransportNodeExecutor` and `NexusProtocol` to submit authenticated `COMPUTE_TASK` messages over TCP through Tailscale. The experimental Android server verified and executed requests using `NexusDistributedCore.handle_compute_task`, `TaskWorker` and explicitly registered handlers. The client verified the authenticated `COMPUTE_RESULT` responses.

Both isolated labs checked out the stated Git commit and reported clean worktrees after execution. The Android report comes from the operator transcript. The full distributed runtime was not started.

## Observed results

| Criterion | Operator-reported result | Source |
| --- | --- | --- |
| Remote Compute tasks passed (`echo`, `data_transform`, `matrix_multiply`, additional `echo`) | 4/4 | Windows client output |
| Negative control: tampered signature | Rejected | Windows client output |
| Negative control: message replay | Rejected | Windows client output |
| Android server summary | 4 accepted; 2 rejected; 0 errors; server stopped | Android operator transcript |
| Client-observed median RTT | 165.659 ms (n=4) | Windows client output |
| Repository integrity | Reported clean worktrees on both devices | Windows output; Android operator transcript |
| Distributed writes | Not used | Experiment design |

Prerequisites were also reported as passed:
- 33 focused offline tests on Windows;
- 33 focused offline tests on Android (operator transcript);
- a real loopback TCP trial between two Windows Python processes: 4 successful Compute requests and 2 negative controls.

The earlier 04A and 04B preparation steps have no archived evidence files.

## Evidence note

- **Android-side figures.** The 4 accepted, 2 rejected, 0 errors, server stopped, clean worktree and 33 tests all come from an operator transcript of terminal output. They are not from a raw log captured and hashed on the device.
- **Hash differences.** Raw file SHA-256 values differed across platforms, although the Git commit matched and both worktrees were reported clean. On Windows, the difference matches line-ending conversion at checkout (`core.autocrlf=true`, CRLF in the working tree, LF in the Git index). This has not been confirmed on Android.
- **Temporary secret.** The temporary HMAC secret used in this test was disclosed outside the devices during the experiment. It is treated as compromised and is not reused.
- **RTT.** The 165.659 ms median (n=4) includes TCP connection setup and server processing. The first sample was markedly slower than the others. The Tailscale path was not observed.

## Scope and limitations

This is evidence of **authenticated remote Compute between two physical devices**, not distributed consensus. It does not establish majority commit, durable replication, leader fencing, split-brain safety, exactly-once execution or production readiness.

- Whether Tailscale used direct or DERP-relayed transport was not recorded.
- RTT observations include network and computation, and four samples are not a statistical benchmark.
- The protocol uses a cluster-wide HMAC secret, not per-node cryptographic identity.

**Privacy:** raw terminal logs, private Tailscale addresses and temporary credentials are not included in this public report.

Related: [Multi-WAN 01–03](NEXUS_V2700_MULTIWAN_01_03_EN.md)
