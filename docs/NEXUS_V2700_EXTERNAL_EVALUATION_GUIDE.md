# Nexus V2700 - External Evaluation Guide

This guide provides a short evaluation path for an external reviewer of Nexus Runtime Platform V2700.

It uses the public repository, CLI, test suite and existing certified evidence. It does not create a new resilience experiment, statistical sample or certification result.

## 1. Clone

```bash
git clone https://github.com/gutembergpb27/Termux-nexus.git
cd Termux-nexus
```

The current tagged V2700 release candidate is `v2700.0.0-rc2`.

## 2. Create an isolated environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux or Termux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Python 3.14 or newer is required by the documented V2700 development path.

## 3. Install

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

## 4. Inspect the public interface

```bash
nexus version
nexus --help
nexus doctor
```

The CLI exposes `version`, `status`, `peers`, `cluster` and `doctor`. Diagnostic commands also support machine-readable JSON where documented.

## 5. Verify the repository baseline

```bash
python -m pytest -q
```

The V2700 certification baseline recorded `810 passed, 1 xfailed`. A later execution should be treated as a new local verification result rather than silently substituted for that recorded baseline.

## 6. Inspect distributed-runtime interfaces

With a Nexus runtime and Hub already running, the public CLI can inspect them without modifying cluster state:

```bash
nexus status --url http://127.0.0.1:8081/status
nexus cluster --url http://127.0.0.1:8081/cluster
nexus peers --url http://127.0.0.1:8500/peers
```

These commands are inspection interfaces. This guide does not start a new physical failover campaign.

## 7. Review the certified resilience evidence

Recommended order:

1. [Executive Technical Brief](NEXUS_V2700_EXECUTIVE_TECHNICAL_BRIEF.md)
2. [External Resilience Demonstration](NEXUS_V2700_EXTERNAL_RESILIENCE_DEMO.md)
3. [Resilience Case Study](NEXUS_V2700_RESILIENCE_CASE_STUDY.md)
4. [Technical Positioning](NEXUS_V2700_TECHNICAL_POSITIONING.md)
5. [Axis 11 Statistical Resilience](validation/NEXUS-V2700-AXIS-11-STATISTICAL-RESILIENCE.md)
6. [Axis 11 aggregate certification](../validation/statistical-resilience/axis11-statistical-campaign.json)

The certified Axis 11 population contains 29 physical samples (`run011` through `run039`): 29 valid, 29 converged, 0 operational split-brain observations and 29 NODE-C promotions under the documented experiment contract.


`run010` is preserved as incomplete and is not counted as a physical sample. No `run040` was created.
un040 was created.

## 8. Reproduction boundary

The repository contains the Axis 11 methodology and runners under `validation/statistical-resilience/`, including `physical_runner.py`, `campaign_runner.py` and `statistical_resilience.py`.

They are available for methodological inspection and independent reproduction. This evaluation guide intentionally does not execute them automatically because a physical resilience run is a new observation and must not be confused with the existing certified population.

An independent reproduction should preserve its own environment identity, source commit, configuration, raw evidence and result boundaries.

## 9. Interpretation boundary

The documented evidence demonstrates behavior under the stated Nexus V2700 experiment contracts. It is not a production certification, a proof of universal fault tolerance, a formal equivalence claim with Raft, or a direct performance comparison with etcd, Consul or other distributed systems.

## Evaluation outcome

A reviewer can use this path to independently inspect the source, install the package, exercise the public CLI, run the repository test suite, inspect runtime diagnostics and trace the published resilience claims back to their certification records and aggregate evidence.
