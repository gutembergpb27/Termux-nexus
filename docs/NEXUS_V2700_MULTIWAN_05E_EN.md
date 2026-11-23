# Nexus Runtime Platform V2700

## Multi-WAN 05E — Experimental physical cross-device pilot (Windows ↔ Android)

**English** · [Português (Brasil)](NEXUS_V2700_MULTIWAN_05E_PT.md)

**Reference date:** November 23, 2026

**Classification:** public experimental documentation; raw evidence retained privately.

**Status:** client-server pilot executed. Completed-task identifier sets were correlated, and the Windows client-side evidence was independently re-verified. Android server and journal figures are operator-reported. A full protocol audit has **not** been completed.

> **Scope:** these findings concern isolated MW05E laboratory tools. They do not demonstrate distributed consensus, majority-based election, leader fencing, distributed commit, exactly-once execution or production readiness.

### 1. Environment and method

The operator used two devices:

- a Windows computer on a connection described as fiber;
- a Motorola Edge 40 Neo running Android/Termux on a connection described as Starlink.

The devices communicated over Tailscale. Earlier diagnostics observed DERP-routed Tailscale control connectivity. The transport path of each pilot workload message was not independently instrumented.

An experimental Windows client sent compute tasks to a Python server on Android. The server used a shared HMAC secret and a persistent journal. Both isolated reference checkouts were reported at commit `d783a863d7b1ac5db88922726606e75c5d17c4fb`, with no repository modifications in the reported post-run checks.

### 2. Observed results

Evidence classes:

- **Independently verified**: recomputed from the Windows client evidence file while preparing the documentation.
- **Operator-reported**: taken from terminal output presented by the operator.

| Check | Result | Class |
|---|---:|---|
| Windows → Android connectivity | TCP reachable over the Tailscale interface | Operator-reported |
| MW05E client exit code | `0` | Operator-reported |
| Client JSONL records | 96 | Independently verified |
| Client `completed` occurrences | 67 | Independently verified |
| **Unique completed client task IDs** | **66** | Independently verified |
| Android server JSONL records | 161 valid / 161 | Operator-reported |
| Android journal JSONL records | 202 valid / 202 | Operator-reported |
| **Unique server / journal task IDs** | **66 / 66** | Operator-reported |
| Matching server × journal IDs | 66, none exclusive to either side | Operator-reported |
| Tasks with `output_sha` in both server and journal | 66 | Operator-reported |
| Tasks with no overlap between comparable output-hash sets | 0 | Operator-reported |
| Server `rejected_unauthenticated` events | 20 | Operator-reported |
| Server `status_answered` events | 2 | Operator-reported |
| Server `answered_from_journal` events | 1 | Operator-reported |

The client summary reported confirmed outcomes for the warmup, consecutive, spaced and latency categories. `CONFIRMED_CACHED` appeared on a duplicate, and again after an initial `UNKNOWN` timeout.

The client evidence, independently re-verified, contains 20 negative-control attempts (tampered, wrong secret, expired, identical resend), all classified `UNKNOWN`: no result was accepted. The server logged 20 unauthenticated rejections (operator-reported).

**The individual negative-control attempts have not been matched to those server rejections.** The server's rejection records carry no request or task identifier. This report does not attest that each attempted invalid operation caused no execution.

The journal records an `output_sha` for all 66 completed tasks. The output body of one task was not retained in the journal. The later audit reconstructed that output and found that its hash matched (operator-reported). See the consolidated [Multi-WAN 05 series report](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md).

### 3. Task identifier correlation

Completed `task_id` values were processed on each device:

1. deduplicated and sorted;
2. serialized as JSON (`ensure_ascii=True`, `separators=(',', ':')`, UTF-8);
3. hashed with SHA-256.

Both sides produced **66 distinct completed IDs** and the same fingerprint:

```text
dd2cb1d4672ec38fee4bfb279280757025a17497cd656c73c64cd6abfe797e5f
```

The Windows fingerprint was independently recomputed from the client evidence and matches. The Android fingerprint is operator-reported.

Matching fingerprints are strong evidence that the recorded completed-task ID sets are identical. They do not independently verify mathematical outputs or every network exchange.

The 67 `completed` client occurrences correspond to 66 distinct IDs. This is consistent with at least one duplicate occurrence, but the specific repeated event has not been traced individually.

### 4. Evidence integrity

- **Windows:** `listed=1 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` for the client-side evidence file. Independently re-verified: 1/1 file OK.
- **Android:** `listed=4 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` for server, journal and ancillary evidence. Operator-reported.
- **SHA-256 of the Android manifest:** `5d115a3b172760e8cf2a4aac70094b79d6567f3f31bf81628a8e0d4e1166c5d8`. Operator-reported.

Original evidence and detailed filenames are intentionally excluded from this public note.

The following client-side figures were independently re-verified from the Windows evidence file:

- 96 records;
- 67 `completed` occurrences / 66 unique IDs;
- the fingerprint;
- 20 `UNKNOWN` negative controls;
- the manifest (1/1).

The Android server and journal figures derive from operator-presented terminal output. Those files were not independently reopened or re-processed.

### 5. Limitations and remaining verification

- Private event-by-event comparison of client, server and journal data, including payloads and independent recomputation of `output_sha`. The operator has since reported this; see the series report.
- Individual matching of all negative controls and proof of no unintended execution.
- Detailed audit of HMAC, replay, TTL, caching, timeout and transactional recovery.
- Instrumented path verification for the actual workload traffic, and any controlled link-performance comparison.
- Quorum, consensus, failover and network-partition safety, which are **outside the scope of this pilot**.

**Bounded conclusion:** Multi-WAN 05E produced a completed experimental remote client flow and **66/66 correlation of completed-task identifiers across Windows, the Android server and its journal**. The client side was independently re-verified; the server and journal side is operator-reported. This is not certification of the distributed runtime, nor a claim of production-grade exactly-once execution or safety.

**Privacy:** no private addresses, HMAC secrets, individual task identifiers or raw JSONL files are published.

Related: [Multi-WAN 01–03](NEXUS_V2700_MULTIWAN_01_03_EN.md) · [Multi-WAN 04C](NEXUS_V2700_MULTIWAN_04C_EN.md) · [Multi-WAN 05 series](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md) · [Documentation index](README.md)
