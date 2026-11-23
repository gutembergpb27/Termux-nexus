# Nexus Runtime Platform V2700

## Experimental Multi-WAN 01–03 Report

**Reference date:** November 22–23, 2026

**Classification:** Experimental cross-device validation.

**Status:** Evidence consolidated.
This does not constitute production certification.

---

## 1. Objective

Investigate communication between real devices
using transport and authentication components
from Nexus Runtime Platform V2700.

Experimental environment:

- Windows, using a connection identified as fiber.
- Motorola Edge 40 Neo running Android/Termux,
  using a connection identified as Starlink.
- Cross-device transport over Tailscale.

The experiments were conducted separately
from the main runtime.

## 2. Multi-WAN 01 — External connectivity

Five TCP/TLS connection tests were recorded
on each device.

Observed median TLS times:

- Windows/fiber: 57.6 ms.
- Android/Starlink: 101.0 ms.

Result: external connectivity demonstrated
in both experimental environments.

These measurements are not a controlled
comparison of provider performance.

## 3. Multi-WAN 02 — Cross-device communication

Application-level TCP communication was demonstrated
between Windows and Android over Tailscale.

Results:

- Five application messages sent.
- Five ACK responses verified.
- Result: 5/5 messages confirmed.
- Median RTT: 76.74 ms.

This experiment used an independent Python protocol,
not the Nexus distributed consensus protocol.

The actual direct or DERP route of each TCP message
was not individually recorded.

## 4. Multi-WAN 03 — Authenticated messaging

Real Nexus components were evaluated:

- NexusProtocol.
- ReplayCache.
- NexusTransport.

### Local functional validation

- 13 tests executed.
- 13 tests passed.
- No reported failures.

### Windows/Android communication

Consolidated results:

- Windows: 5/5 authenticated messages passed.
- Windows: 2/2 negative controls passed.
- Android: 5/5 expected connections accepted.
- Android: 2/2 negative controls rejected.

Recorded median RTT: 153.998 ms.

Cross-device audit classification:

**CROSS-DEVICE EVIDENCE PASS**

These results describe the specific experiment.
They do not establish complete integration
with the distributed runtime.

## 5. Evidence integrity

### Multi-WAN 01/02 archive

File:

`NEXUS-MULTIWAN-20261122T191044-e0a0252d.zip`

SHA-256:

`f630a50e2fd703a784de500f719f315f4ee50891929b9d615817cb3deacb6ee9`

### Multi-WAN 03 archive

File:

`NEXUS-MW03-EVIDENCE-20261123T001842Z-853db823.zip`

SHA-256:

`9e9dda7e86f50598359a5365d231c21ddd6a34cad49589c773075461da8d489f`

### Cross-device audit report

File:

`REPORT-MULTIWAN03.json`

SHA-256:

`9016f3a629726884bb7343412e8b9d04b40102b685a3592d1afdd797ea9a5cd4`

The archives were validated locally.

Raw evidence files are not included
in this GitHub documentation update.

## 6. Limitations

The experiments do not demonstrate:

- Operational distributed consensus.
- Operational majority-based leader election.
- Persistent cross-node replication.
- Distributed fencing.
- Network partition safety.
- Arbitrary fault tolerance.
- Production readiness.
- Controlled provider performance comparison.

Authenticated laboratory communication is not
equivalent to certification of the main runtime.

## 7. Preservation

Documentation was prepared in an isolated Git worktree.

W17-A/B/C/D laboratories and original evidence
remain outside the scope of these changes.

No private network addresses, authentication tokens
or secret keys are published in this report.
