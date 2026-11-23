# Nexus Runtime Platform V2700

## Multi-WAN 05E — Experimental physical cross-device pilot (Windows ↔ Android)

**Reference date:** November 23, 2026

**Classification:** public experimental documentation; raw evidence retained privately.

**Status:** client-server pilot executed, SHA-256 manifests verified on both devices, completed-task identifier sets correlated. Full protocol audit **not** completed.

> **Scope:** these findings concern isolated MW05E laboratory tools. They do not demonstrate distributed consensus, majority-based election, leader fencing, distributed commit, or production readiness.

### 1. Environment and method

The operator used a Windows computer on a connection described as fiber and a Motorola Edge 40 Neo running Android/Termux on a connection described as Starlink. Devices communicated over Tailscale. Earlier diagnostics observed DERP-routed Tailscale control connectivity; the transport path of each pilot workload message was not independently instrumented.

An experimental Windows client sent compute tasks to a Python server on Android using a shared HMAC secret and a persistent journal. Both isolated reference checkouts were reported at commit `d783a863d7b1ac5db88922726606e75c5d17c4fb` with no repository modifications in the reported post-run checks.

### 2. Observed results

| Check | Operator-reported result |
|---|---:|
| Windows → Android connectivity | TCP reachable over the Tailscale interface |
| MW05E client exit code | `0` |
| Client JSONL records | 96 |
| Client `completed` occurrences | 67 |
| **Unique completed client task IDs** | **66** |
| Android server JSONL records | 161 valid / 161 |
| Android journal JSONL records | 202 valid / 202 |
| **Unique server / journal task IDs** | **66 / 66** |
| Matching server × journal IDs | 66, none exclusive to either side |
| Tasks with `output_sha` in both server and journal | 66 |
| Tasks with no overlap between comparable output-hash sets | 0 |
| Server `rejected_unauthenticated` events | 20 |
| Server `status_answered` events | 2 |
| Server `answered_from_journal` events | 1 |

The client summary reported confirmed outcomes for warmup, consecutive, spaced, and latency categories; `CONFIRMED_CACHED` appeared on a duplicate and after an initial `UNKNOWN` timeout. The client also reported 20 `UNKNOWN` negative controls, while the server logged 20 unauthenticated rejections. **The individual negative-control attempts have not been matched to those server rejections**; this report does not attest that each attempted invalid operation caused no execution.

### 3. Task identifier correlation

Completed `task_id` values were deduplicated, sorted, JSON-serialized (`ensure_ascii=True`, `separators=(',', ':')`, UTF-8), and SHA-256 hashed on each device. Both sides produced **66 distinct completed IDs** and the same fingerprint:

```text
dd2cb1d4672ec38fee4bfb279280757025a17497cd656c73c64cd6abfe797e5f
```

Matching fingerprints provide strong evidence that the recorded completed-task ID sets are identical; they do not independently verify mathematical outputs or every network exchange. The 67 `completed` client occurrences correspond to 66 distinct IDs, consistent with at least one duplicate occurrence, but the specific repeated event has not been traced individually.

### 4. Evidence integrity

The operator provided the following manifest verification results:

- **Windows:** `listed=1 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` for the client-side evidence file.
- **Android:** `listed=4 mismatched=[] missing=[] invalid_entries=[] unlisted=[]` for server, journal, and ancillary evidence.
- **SHA-256 of Android manifest:** `5d115a3b172760e8cf2a4aac70094b79d6567f3f31bf81628a8e0d4e1166c5d8`.

Original evidence and detailed filenames are intentionally excluded from this public note. The measurements and checks above are derived from the terminal output presented by the operator; the original files were not independently reopened or reprocessed in preparing this documentation.

### 5. Limitations and remaining verification

- Private event-by-event comparison of client, server, and journal data, including payloads and independent recomputation of `output_sha`.
- Individual matching of all negative controls and proof of no unintended execution.
- Detailed HMAC, replay, TTL, caching, timeout, and transactional recovery audit.
- Instrumented path verification for the actual workload traffic, and any controlled link-performance comparison.
- Quorum, consensus, failover, and network-partition safety — **outside the scope of this pilot**.

**Bounded conclusion:** Multi-WAN 05E produced a completed experimental remote client flow and **66/66 correlation of completed-task identifiers across Windows, the Android server, and its journal**. This is not certification of the distributed runtime or a claim of production-grade exactly-once execution or safety.

**Privacy:** no private addresses, HMAC secrets, individual task identifiers, or raw JSONL files are published.
