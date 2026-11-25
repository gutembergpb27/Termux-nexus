# Nexus Runtime Platform V2700

## Recovery R2 and R3 — Process-kill recovery of persisted ComputeRuntime state (experimental)

**English** · [Português (Brasil)](NEXUS_V2700_RECOVERY_R2_R3_PT.md)

**Reference date:** November 24, 2026

**Classification:** public experimental documentation; raw evidence retained privately.

**Status:** both laboratories **executed and passed within the defined
experimental limits** (R2: 15/15 checks; R3: 15/15 checks). An independent
read-only auditor re-derived the R3 figures from the raw evidence.

> [!IMPORTANT]
> **Scope.** R2 and R3 show that the JSON state written by
> `TaskCompletionStore` for a real `ComputeRuntime` survives a forced kill of
> its process and can be loaded by a new runtime: on the same machine (R2), and
> on another device after a manual, verified transfer (R3). They do **not**
> demonstrate automatic or distributed failover, consensus, live process
> migration, exactly-once execution or production readiness. Nothing in these
> laboratories changes the runtime on `main`; they are **experimental
> laboratories**, not operational capabilities of the distributed runtime.

---

### 1. Evidence classes

| Class | Meaning |
|---|---|
| **Lab-measured** | Produced by the laboratory harness during the run and stored in the lab evidence files. |
| **Independently verified** | Recomputed from the raw evidence files (hashes, states, ledgers, timings) by a separate read-only auditor, without relying on the harness summary. |
| **Operator-declared** | Stated by the operator and not measured by the tooling (for example, the type of internet link). |
| **Not implemented** | Behavior the current runtime does not provide; recorded as a limitation, never simulated. |

---

### 2. Code under test

| Item | Value | Class |
|---|---|---|
| Commit | `08a0f7361dd08e6afdf8a90755250505cb750120` | Lab-measured |
| `nexus/` tree | `c6a29776b54f1827c3b3128cbe4404e046143e33` (identical on `main` at the time of writing) | Independently verified |
| Components | `ComputeRuntime`, `TaskCompletionStore`, `TaskCompletionRegistry` — real code, persistence not mocked | Lab-measured |
| Code delivery | `git archive` of the commit into each lab (repository never modified); R3 Android side received a SHA-256-verified snapshot (`2431a3d1…dd61`) because its local checkout did not contain the commit | Independently verified |

The only test doubles were **backends**: a `LocalBackend` subclass that appends
one fsync'd line per execution to an execution ledger (to detect duplicate
execution), and a backend that blocks forever (to create a genuinely in-flight
task at kill time).

Task classes used in both labs:

- **Really executed:** run through `ComputeRuntime.run`, which persisted
  `pending → running → completed`.
- **Prepared:** written through the registry API (`create`, `start`) plus
  `persist()`, never executed. Used only to check the recovery policy.
- **In flight:** `ComputeRuntime.run` persisted `running` and the backend was
  blocked when the process was killed.

---

### 3. Recovery R2 — single machine (Windows)

**Procedure.** A child process (instance A) ran one real task, prepared one
`pending` and one `running` task, and started one in-flight task. After the
harness confirmed the JSON store on disk, it terminated **only that child**,
through its own process handle (`TerminateProcess`, PID 8548, exit code 1). The
process stayed down for 5 s; a new process (instance B) then loaded the same
store.

| Task | Before kill | After recovery |
|---|---|---|
| real, completed | `completed` | `completed`, result identical field by field |
| prepared `pending` | `pending` | `pending` |
| prepared `running` | `running` | `failed` — "task interrupted by runtime restart" |
| real, in flight | `running` | `failed` — "task interrupted by runtime restart" |

**Checks (15/15 passed, lab-measured):** store present and valid before kill;
states as designed; no leftover `.tmp` before or after kill; store bytes
unchanged by the kill; killed PID not alive after the downtime; completed task
and its result preserved; `pending` kept; both `running` tasks recovered as
`failed` with the interruption message; no duplicate execution; re-run attempts
did not modify the store; health counters consistent
(`pending 1, running 0, completed 1, failed 2, total 4`); a new task ran after
recovery.

**Duplicate prevention.** Five re-run attempts were all rejected without
executing: non-idempotent re-run (`ValueError: task completion already exists`),
idempotent re-run of the completed task (`RuntimeError: completed task does not
contain a ComputeResult`), of the pending task (`task execution already in
progress`) and of both recovered tasks (`task interrupted by runtime restart`).
The ledger shows each really executed task once.

**Timing (lab-measured, n = 1):** store load → `health()` **0.57 ms**; process
spawn → runtime ready **312 ms**; downtime between kill and restart 5.0 s (set
by the harness).

Evidence hashes: R2 report `2869b7c9…5f4d6f`; R2 manifest `dc543184…779908`
(15/15 entries verified again for this document).

---

### 4. Recovery R3 — cross-device (Motorola/Termux → Windows)

#### 4.1 Environment

| Item | Value | Class |
|---|---|---|
| Origin | Motorola Edge 40 Neo, Android 15, aarch64, Termux, Python 3.14.10 | Lab-measured (preflight) |
| Destination | Windows 11 computer, Python 3.14.6 | Lab-measured |
| Origin internet link | Described as Starlink | Operator-declared |
| Destination internet link | Described as fiber | Operator-declared |
| Overlay network | Tailscale tailnet; the path at transfer time was not recorded. A post-run check showed a DERP relay path (no direct connection) | Lab-measured (post-run only) |
| Lab locations | Outside both repositories and, on Android, outside `HOME` | Lab-measured |

#### 4.2 Procedure

1. **Origin run.** On the Motorola, a child process ran a real task (sum of
   squares 1..10 = 385), prepared a `pending` task and started an in-flight
   task. The store was confirmed on disk.
2. **Controlled interruption.** The harness sent `SIGKILL` to **its own child
   only** (PID 6002), after checking that the PID reported by the child matched
   the PID it had spawned. Exit status −9; `/proc/6002` absent after reaping.
   The store bytes were unchanged by the kill.
3. **Handoff.** The origin store was frozen read-only and a handoff marker
   (epoch 1) recorded its SHA-256. A fixed list of nine experimental files was
   bundled. No keys, tokens, credentials or production files were included.
4. **Transfer.** HTTP PUT inside the Tailscale tailnet to a single-use receiver
   on Windows. The receiver listened only on the tailnet interface, accepted
   only the origin's tailnet address plus a temporary token (renewed after a
   security review, never written to evidence), and verified SHA-256 and the
   exact list of bundle members before accepting.
5. **Recovery.** On Windows, a new process loaded a copy of the transferred
   store, after checking its hash against the handoff marker.
6. **Persistence check.** A new task ran on Windows; a second, independent
   process reloaded the store from disk.

#### 4.3 Integrity (independently verified)

| Item | Origin | Destination |
|---|---|---|
| Store SHA-256 | `b9c98733…a469a9b` (585 bytes) | same |
| Bundle SHA-256 | `3caf32e3…0a8516d3` (2,483 bytes) | same |
| Code snapshot SHA-256 | `2431a3d1…eefcdd61` | same |

#### 4.4 Task states

| Task | Before kill (Motorola) | After recovery (Windows) |
|---|---|---|
| real, completed (sum of squares = 385) | `completed` | `completed`, result identical field by field |
| prepared `pending` | `pending` | `pending` |
| real, in flight | `running` | `failed` — "task interrupted by runtime restart" |
| new task on Windows | — | `completed`, persisted and reloaded by a separate process |

Health on recovery: `pending 1, running 0, completed 1, failed 1, total 3`;
after the new task: `completed 2, total 4`.

**Checks (15/15 passed):** bundle hash matches the origin claim; destination
code snapshot hash; store hash origin = destination; valid store schema;
handoff marker present; completed task present; result preserved field by
field; computed value (385) preserved; `pending` kept; in-flight task recovered
as `failed` with the interruption message; no duplicate execution across
devices; re-run attempts did not modify the store; health counters consistent;
new task executed on Windows; new result persisted and reloaded by a fresh
process.

#### 4.5 Duplicate prevention in the tested scenario

The execution ledgers of both devices, combined, show each task **started at
most once**: the completed task ran once on the Motorola; the in-flight task
started once and never finished or restarted; the `pending` task never ran;
the only execution on Windows was the new task. Four re-run attempts on Windows
were rejected without executing and without changing the store hash. This is
evidence for this scenario only, **not** an exactly-once guarantee.

#### 4.6 Timing (lab-measured, n = 1; recomputed by the auditor)

| Measurement | Value |
|---|---|
| Transfer (full HTTP PUT, measured at origin) | 168 ms |
| Initialization: process spawn → runtime ready (Windows) | 988 ms (of which imports 689 ms) |
| Recovery: store load → `health()` | 0.96 ms |
| New task: run + persist | 9.0 ms |
| Clock offset, Windows − Motorola | 894 ms ± 78 ms (14 HTTP samples) |
| **Total: kill on Motorola → runtime ready on Windows** | **2.95 s ± 0.08 s** |

The total is reported only because both clocks were related by measured
samples with a known uncertainty. It includes bundling, transfer, post-upload
clock sampling, a 0.5 s receiver polling window and initialization.

#### 4.7 Independent audit

A separate read-only agent re-verified: the R3 manifest (27/27) and R2 manifest
(15/15); the bundle → store → handoff hash chain; task states at origin and
destination; ledgers and PIDs; all timing figures (total 2.9509 s); the absence
of tokens in every lab file; the nine bundle members; and that the repository
was unchanged. Items 1–11 were confirmed. It also found four **documentation**
discrepancies in the first R3 report draft: a network-path statement and
destination resource figures without archived evidence, an "exactly once"
wording, and an unmentioned first receiver instance that never received origin
traffic. All four were corrected in the lab report before this document was
written; the corrections are reflected above.

---

### 5. Limitations

**Proven limitations of the current code (not implemented):**

1. **Serialization.** A recovered `completed` result is a plain `dict`, not a
   `ComputeResult`: `export_state` uses `dataclasses.asdict` and
   `restore_state` does not rebuild the type.
2. **Idempotency.** Because of (1), `run(idempotent=True)` on a recovered
   completed task raises `completed task does not contain a ComputeResult`
   instead of returning the stored result. It does not re-execute.
3. **Requeue.** A recovered `pending` task cannot be resumed or requeued by
   `ComputeRuntime`; it survives as state only.
4. **Interrupted tasks.** Every persisted `running` task becomes `failed` on
   load, with no automatic retry, and the runtime cannot tell a genuinely
   interrupted task from any other persisted `running` entry.
5. **Health.** `health()["healthy"]` is always `True`; it does not validate the
   recovered state. Consistency was checked through the counters.
6. **Single writer.** The store has no fencing token or lease. In R3,
   single-writer was enforced **procedurally** (origin killed, origin store
   frozen, handoff marker, single-upload receiver); the store itself cannot
   reject a stale writer.

**Limitations of the experiment:**

7. The R3 transfer and restart were performed by the harness and the operator:
   not automatic failover, not distributed consensus, not live process
   migration.
8. Only process kill was tested; operating-system crash and power-loss
   durability were not tested (the store fsyncs the temporary file but not the
   directory after the rename).
9. The "computation" is performed by the harness and carried in the payload;
   the real `LocalBackend` only echoes the task name and payload.
10. Internet link types are operator-declared; the Tailscale path was recorded
    only after the run.
11. Destination memory and disk figures were not archived in the preflight.
12. Each figure comes from a single run (n = 1); no statistics are implied.

---

### 6. What is retained privately

Raw logs, stores, ledgers, the bundle, the harness and SHA-256 manifests are
kept in the two laboratory directories on the operator's machine. Private
addresses, host names, temporary tokens and device identifiers are not
published. Published hashes allow the private evidence to be matched to this
report.

| Artifact | SHA-256 |
|---|---|
| R2 report | `2869b7c948db1a074ad1c5050917c476b6404c80a882e9fcd02075948c5f4d6f` |
| R2 manifest | `dc5431841db260ba59291b88272e3ce8988d4279ce9fb676df5a15b33e779908` |
| R3 report (after audit corrections) | `94c17d944a89b12a62fca1e8b2f5c838e75eb4e413c72b2447ff18a2a1e74b23` |
| R3 manifest | `5de7b738fad4ef91a6e0a87b84f5db8581d0bba0733f6589e6130fa326e3d0ad` |
| R3 harness | `026ad21cdb8eba57b8c21c7e5c864f1961da743d7a27edeef7a6123763dd4f05` |

---

### 7. Next step

A supervised-recovery laboratory (R4) is being specified outside the
repository: automatic detection of a stopped experimental process, integrity
verification, supervised restart on the **same** node, and an investigation of
writer fencing. It will not promote another node to writer without verifiable
proof that the previous instance lost its authority.

See the [documentation index](README.md) for related experiments.
