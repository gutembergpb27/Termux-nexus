# Nexus Runtime Platform V2700 — Multi-WAN 04C: experimental remote Compute execution

**Status:** PASS (bounded experiment)<br>
**Date:** November 22, 2026<br>
**Git base:** `d783a863d7b1ac5db88922726606e75c5d17c4fb`<br>
**Repository:** `gutembergpb27/Termux-nexus`

## Overview

A physical Windows-to-Motorola Edge 40 Neo (Android 15 / Termux) experiment evaluated interoperability of existing Nexus Runtime Platform V2700 components. The client used `TransportNodeExecutor` and `NexusProtocol` to submit authenticated `COMPUTE_TASK` messages over TCP through Tailscale. The Android-side experimental server verified and executed requests using `NexusDistributedCore.handle_compute_task`, `TaskWorker`, and explicitly registered handlers; the client verified authenticated `COMPUTE_RESULT` responses.

Both isolated labs checked out the stated Git commit and reported clean worktrees after execution. The full distributed runtime was not started.

## Observed results

| Criterion | Result |
| --- | --- |
| Remote Compute tasks passed (`echo`, `data_transform`, `matrix_multiply`, additional `echo`) | 4/4 |
| Negative control: tampered signature | Rejected |
| Negative control: message replay | Rejected |
| Android server summary | 4 accepted; 2 rejected; 0 errors; server stopped |
| Client-observed median RTT | 165.659 ms (n=4) |
| Repository integrity | CLEAN on both devices |
| Distributed writes | Not used |

Prerequisites also passed: 33 focused offline tests on Windows, 33 on Android, and a real loopback TCP trial between two Windows Python processes (4 successful Compute requests, 2 negative controls).

## Scope and limitations

This is evidence of **authenticated remote Compute between two physical devices**, not distributed consensus. It does not establish majority commit, durable replication, leader fencing, split-brain safety, or production readiness. Direct versus DERP-routed Tailscale transport was not recorded. RTT observations include network and computation, and four samples are not a statistical benchmark. The protocol uses a cluster-wide HMAC secret, not per-node cryptographic identity. Raw file SHA-256 values differed across platforms despite a matching Git commit and clean worktrees; the reason was not independently determined.

**Privacy:** raw terminal logs, private Tailscale addresses, and temporary credentials are not included in this public report.
