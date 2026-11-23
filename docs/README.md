# Nexus Runtime Platform — Documentation index

**English** · [Português (Brasil)](README.pt-BR.md) · [Back to the project README](../README.md)

Every document in this repository falls into one of four groups. Read the
group label before using a figure from a document: only the first group
describes the current state of `main`.

| Group | Meaning |
|---|---|
| **A · Current state of `main`** | Describes code, tests and CI on `main` today. |
| **B · Validation evidence** | Recorded experiments with a fixed scope and date. Figures apply to that experiment only. |
| **C · Experimental laboratories** | Tools and results outside the runtime on `main`. |
| **D · Historical and release records** | Preserved for traceability. Do not use them as statements about the current project. |

---

## Start here

1. [Project README](../README.md): overview, status, capabilities and limitations.
2. [Project State](PROJECT_STATE.md): detailed current state, integration history and open findings.
3. [W08-A Consensus Safety Audit](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md): why the runtime does not implement consensus.
4. [External Evaluation Guide](NEXUS_V2700_EXTERNAL_EVALUATION_GUIDE.md): a guided path for external reviewers.

---

## A · Current state of `main`

| Document | Purpose |
|---|---|
| [Project State](PROJECT_STATE.md) | Current state, CI figures, integration history (PR #101–#108) |
| [W08-A Consensus Safety Audit](NEXUS_V2700_W08A_CONSENSUS_SAFETY_AUDIT.md) | Read-only audit of authority, quorum and fencing code (F1–F10, INV-01..INV-07) |
| [W08-B Cluster Mode Migration](NEXUS_V2700_W08B_CLUSTER_MODE_MIGRATION.md) | `NEXUS_CLUSTER_MODE` behavior, limits of `single`, migration |
| [Security Trust Boundary](NEXUS_V2700_SECURITY_TRUST_BOUNDARY.md) | Security and trust boundaries |
| [Distributed Commit Contract](NEXUS_V2700_DISTRIBUTED_COMMIT_CONTRACT.md) | Contract a future distributed commit must satisfy |
| [V2700 Architecture Plan](NEXUS_V2700_ARCHITECTURE_PLAN.md) | Architecture and development axes |
| [Technical Positioning](NEXUS_V2700_TECHNICAL_POSITIONING.md) | Scope and neutral technology positioning |
| [Executive Technical Brief](NEXUS_V2700_EXECUTIVE_TECHNICAL_BRIEF.md) | External overview. Written before PR #101/#104: read it together with the README limitations |

## B · Validation evidence

| Document | Scope |
|---|---|
| [Resilience Case Study](NEXUS_V2700_RESILIENCE_CASE_STUDY.md) | Controlled three-node MASTER-loss scenario |
| [Axis 10 Quorum Timing](validation/NEXUS-V2700-AXIS-10-QUORUM-TIMING.md) | Quorum timing; measured before QS-C01 |
| [Axis 11 Statistical Resilience](validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md) | 29 physical samples; measured before QS-C01 |
| [External Resilience Demonstration](NEXUS_V2700_EXTERNAL_RESILIENCE_DEMO.md) | Navigation over the resilience evidence |
| [External Reproduction Protocol](NEXUS_V2700_EXTERNAL_REPRODUCTION_PROTOCOL.md) | How to reproduce the recorded results |
| [Windows + Android validation](windows_android_validation.md) | Earlier physical multi-device validation |
| [Axis 7 physical evidence](../validation/axis7-physical/README.md) | Physical validation records |
| [Multi-node convergence](../validation/multi-node-convergence/REAL-PROCESS-PASS.md) | Real-process convergence record |
| [Role re-coordination protocol](../validation/role-recoordination/PROTOCOL.md) | Re-coordination test protocol |

## C · Experimental laboratories

### Multi-WAN cross-device experiments

| Milestone | Status | Report |
|---|---|---|
| Multi-WAN 01–03: authenticated messaging, Windows ↔ Android | Documented, with erratum (section 8) | [EN](NEXUS_V2700_MULTIWAN_01_03_EN.md) · [PT](NEXUS_V2700_MULTIWAN_01_03_PT.md) |
| Multi-WAN 04C: authenticated remote compute | Documented; operator-reported, Android side from an operator transcript | [EN](NEXUS_V2700_MULTIWAN_04C_EN.md) · [PT](NEXUS_V2700_MULTIWAN_04C_PT.md) |
| Multi-WAN 05E: physical remote compute pilot | Documented; client side independently re-verified; Android server/journal operator-reported | [EN](NEXUS_V2700_MULTIWAN_05E_EN.md) · [PT](NEXUS_V2700_MULTIWAN_05E_PT.md) |
| MW05E–MW05K-2 consolidated series: audit and local negative controls | Consolidated report; figures largely operator-reported | [EN](NEXUS_V2700_MULTIWAN_05_SERIES_EN.md) · [PT](NEXUS_V2700_MULTIWAN_05_SERIES_PT.md) |
| Physical Windows–Motorola pilot of the MW05K-2 controls | Pending Starlink connectivity | — |

### Validation tooling not wired into the runtime

| Document | Purpose |
|---|---|
| [S1–S5 harness](../validation/s1-s5-harness/README.md) | W05/W06 validation harness |
| [Hub hardening](../validation/hub-hardening/README.md) | W07 hardened hub prototype |
| [Hub hardening integration proposal](../validation/hub-hardening/INTEGRATION_PROPOSAL.md) | Proposal; not integrated |
| [NIRT-01](../nirt/NIRT-01.md) · [NIRT-02](../nirt/NIRT-02.md) | External-candidate and audited-integration records |

## D · Historical and release records

### Release notes

[v2700.0.0-rc2](../RELEASE_NOTES_v2700.0.0-rc2.md) ·
[v2700.0.0-rc1](../RELEASE_NOTES_v2700.0.0-rc1.md) ·
[v2600.0.0-alpha.1](../RELEASE_NOTES_v2600.0.0-alpha.1.md) ·
[v2500.0.0-rc1](../RELEASE_NOTES_v2500.0.0-rc1.md) ·
[runtime-v1-beta](../RUNTIME_V1_BETA_RELEASE.md)

### Earlier architecture and specifications

| Document | Note |
|---|---|
| [v2500 Architecture Map](NEXUS_V2500_ARCHITECTURE_MAP.md) | Historical architecture reference |
| [Architecture Reality Map](../NEXUS_ARCHITECTURE_REALITY_MAP.md) | Pre-V2700 map of claims and evidence |
| [Mesh Protocol V1](../NEXUS_MESH_PROTOCOL_V1.md) | Protocol specification. Not every capability in it is implemented |
| [Canonical baseline](canonical/BASELINE.md) · [limitations](canonical/LIMITATIONS.md) | `canonical-evidence` branch era (C20) |
| [C20 dossier](../DOSSIE_TECNICO_C20.md) · [integrity baseline](../INTEGRITY_BASELINE_C20.md) · [manifest](../MANIFESTO_CRIPTOGRAFICO_C20.md) · [final record](../REGISTRO_FINAL_C20.md) | C20 integrity cycle |
| [Legacy README](legacy/README_legacy.md) | Earlier project README |
| [Product Bridge](../NEXUS_PRODUCT_BRIDGE.md) | Product vision text. It makes no technical claims |

### Early v500/v600 material, superseded

These documents date from the v500/v600 period. They contain statements that
current evidence **does not support**, such as zero data loss, production
readiness, availability percentages, valuation figures and "consensus" based on
presence. They are kept unchanged as historical records and each carries a
notice at the top.

[White paper](../WHITE_PAPER.md) ·
[Executive dashboard](../EXECUTIVE_DASHBOARD.md) ·
[Financial pitch](../FINANCIAL_PITCH.md) ·
[Validation protocol v500](../VALIDATION.md)

---

## Documentation conventions

- English is the primary language. Documents with a Portuguese version link to it on their first lines.
- Every figure states the commit, run or experiment it comes from.
- Results reported by an operator, and not independently re-processed, are labelled **operator-reported**.
- Raw logs, private addresses, secrets and device identifiers are never published.
