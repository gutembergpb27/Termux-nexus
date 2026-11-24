# Nexus Runtime Platform V2700

## Multi-WAN 05K-2 — Physical negative-control pilot with per-request correlation (Windows ↔ Motorola, experimental)

**English** · [Português (Brasil)](NEXUS_V2700_MULTIWAN_05K2_PHYSICAL_PT.md)

**Reference date:** November 23, 2026

**Classification:** public experimental documentation; raw evidence retained privately.

**Status:** physical pilot **executed and passed within the defined experimental
limits**. The experimental verifier reported `CORRELATION=PASS`: each of the 20
invalid requests sent from Windows was individually matched to one server
rejection, and no task from those requests was admitted or completed.

> [!IMPORTANT]
> **Scope.** This pilot concerns an isolated, instrumented copy of the MW05E
> laboratory server. It does **not** demonstrate distributed consensus,
> universal security, partition tolerance, certified exactly-once execution or
> production readiness. Nothing in this pilot changes the runtime on `main`.

---

### 1. Evidence classes

| Class | Meaning |
|---|---|
| **Verifier-reported** | Output of the experimental `--mode verify` program, run by the operator on the Android lab and presented as terminal output. The Android server log and journal were **not** re-processed by the documentation author. |
| **Client-side re-checked** | Recomputed by the documentation author from the Windows client evidence file (hash, size, case counts). |
| **Operator-declared** | Environment details stated by the operator and not measured by the tooling. |

---

### 2. Environment

| Item | Value | Class |
|---|---|---|
| Client | Windows computer on a connection described as fiber | Operator-declared |
| Server | Motorola Edge 40 Neo, Android/Termux, on a connection described as Starlink | Operator-declared |
| Overlay network | Tailscale (private tailnet addresses only; no public listener, no wildcard bind) | Operator-declared |
| Server under test | Isolated, instrumented copy of the MW05E lab server, with its own state directory and journal | Verifier-reported |
| Repository use | Windows checkout used read-only, to load the protocol module | Client-side re-checked |
| HMAC secret | Fresh temporary secret, typed at a hidden prompt on both devices; not saved or published | Operator-declared |

The transport path of each pilot message (direct or DERP relay) was not
instrumented.

---

### 3. Method

1. **Instrumentation.** In an isolated copy of the lab server, a single line was
   added **before** envelope authentication: it records the SHA-256 of the
   received envelope (canonical JSON) in the server's connection event. The
   original lab files were not modified. The trace contains no request ID,
   nonce, signature, secret, payload or address.
2. **Client run (one round).** The Windows client sent 20 invalid requests to
   the Android server and stored, for each one, the SHA-256 of the same
   canonical envelope:

   | Case | Count | How the request was made invalid |
   |---|---:|---|
   | Invalid signature | 10 | Valid `COMPUTE_TASK` envelope with one character of the HMAC signature altered |
   | Replay | 5 | An authenticated `COMPUTE_STATUS` query was first accepted and its signed `unknown_task` response verified by the client (replay seed); the identical envelope was then sent again |
   | Expired | 5 | `COMPUTE_TASK` envelope signed with a timestamp 180 s in the past (server TTL 60 s) |

3. **Transfer.** The client JSONL was copied to the isolated Android lab over a
   private Tailscale channel, and its SHA-256 was checked on arrival.
4. **Verification.** With the server stopped, `--mode verify` compared the
   client trace hashes with the server rejection traces as multisets and
   checked the server journal for any task or completion record.

---

### 4. Results

**Client run — client-side re-checked.**

| Check | Result |
|---|---:|
| Negative attempts sent | **20** (10 invalid signature · 5 replay · 5 expired) |
| Replay seeds verified (authenticated status response) | **5** / 5 |
| Negative attempts that received response bytes | **0** (all 20 closed without a response) |
| Client evidence JSONL | 4,395 bytes |
| Client evidence SHA-256 | `40b8ab5dca0a705728c115ee68680d21949e4b77795a9ec398737edf82618ebd` |

**Verification — verifier-reported.**

| Control | Observed |
|---|---:|
| Negative client attempts | 20 |
| Negative server rejections (`rejected_unauthenticated`) | 20 |
| Per-request trace matches | **20** |
| Client traces missing on the server | 0 |
| Unexpected server rejections | 0 |
| Unique client traces / unique server traces | 20 / 20 |
| Replay seed failures | 0 |
| Negative attempts with response bytes | 0 |
| Negative task IDs submitted to the journal | **0** |
| Negative task IDs completed | **0** |
| Journal `task` rows / `done` rows | 0 / 0 |
| Server `task_done` events | 0 |
| Verdict | `CORRELATION=PASS` · `FRESH_INSTRUMENTED_PILOT_PASS_WITH_DEFINED_LIMITS` |

---

### 5. Relation to earlier results

- **MW05E (historical).** The 20 authentication rejections in the MW05E server
  log carry no request identifier. They remain matched **by count only** to the
  20 MW05E client negative controls; individual correlation is **not** shown for
  them, and this pilot does not change that.
- **MW05K-2 local suite.** The earlier 20/20 local negative controls ran on one
  machine with a simulated transport. They are preserved as reported in the
  [series report](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md#5-mw05k-2--local-negative-controls-with-simulated-transport).
- **This pilot** adds a cross-device run in which each invalid request is
  matched individually to a server rejection.

---

### 6. What this pilot shows — and what it does not

**Supported, within the defined limits:**

- Over a Windows ↔ Android Tailscale link, 20 invalid requests (invalid
  signature, replay, expired) were each rejected at authentication, and each
  rejection was matched to exactly one client request.
- None of those requests produced a response, a journal task record or a task
  completion in the isolated lab.

**Limitations:**

- The trace is the SHA-256 of an **unauthenticated** envelope. It correlates
  byte content within this experiment; it is not a trusted sender identity.
- One run, 20 requests. No repetition, benchmark or stress test.
- Absence of task records was observed in this isolated lab; it is not a formal
  proof that every server code path fails closed.
- Android-side figures come from the verifier output presented by the operator;
  the server log and journal were not independently re-processed.
- Network characteristics (fiber, Starlink) are operator-declared, and the
  transport path was not instrumented.

**Not shown:** distributed consensus, quorum election, leader fencing,
universal security, partition tolerance, exactly-once execution or production
readiness.

---

**Privacy:** no HMAC secret, private address, raw JSONL, individual request or
task identifier, or device path is published.

Related: [Multi-WAN 05 series report](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md) ·
[Multi-WAN 05E report](NEXUS_V2700_MULTIWAN_05E_EN.md) ·
[Documentation index](README.md)
