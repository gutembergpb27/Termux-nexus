# Nexus V2700 - External Reproduction Protocol

## Purpose

This protocol defines how an independent evaluator can report an external evaluation or reproduction attempt of Nexus V2700 in a form that is technically reviewable and attributable to a specific environment and source revision.

A repository clone, page view, download, CI execution, or informal statement is not by itself classified as an independent reproduction.

This protocol does not modify the Nexus runtime, the certified V2700 evidence, or the closed Axis 11 statistical campaign.

## Evaluation basis

Evaluators should begin with the [External Evaluation Guide](NEXUS_V2700_EXTERNAL_EVALUATION_GUIDE.md).

The current public V2700 release candidate is `v2700.0.0-rc2`.

An evaluator may also evaluate a later commit, but the exact commit SHA must be recorded so that the result is not silently attributed to a different revision.

## Required report metadata

A reproduction report should record:

- evaluator name, organization, or stable public identity when the evaluator chooses to provide one;
- evaluation date;
- operating system and version;
- Python version;
- Nexus tag and exact commit SHA;
- installation method;
- commands executed;
- test-suite result;
- CLI checks performed;
- distributed-runtime checks performed, when applicable;
- whether a physical resilience experiment was independently executed;
- observed result;
- deviations from the documented procedure;
- errors, limitations, or unexpected behavior;
- links or hashes for independently generated evidence, when available.

## Result classes

### 1. External evaluation

The evaluator cloned or obtained the repository and performed one or more documented inspection, installation, CLI, test, or runtime-validation steps.

This classification does not imply reproduction of the physical resilience experiment.

### 2. Test-suite reproduction

The evaluator independently installed the selected revision and executed the documented regression suite, preserving the observed result and environment metadata.

The result should be reported exactly as observed, including failures or xfails.

### 3. Physical resilience reproduction

The evaluator independently executes the documented physical resilience methodology using a separately created environment and preserves enough raw evidence to review the observation.

A physical reproduction report must identify the experiment contract, participating nodes, relevant configuration, source revision, timestamps, observed topology transitions, final convergence state, and raw evidence location.

### 4. Non-reproduction or divergent result

A failed, incomplete, or divergent attempt is still valuable evidence and should be preserved rather than discarded or repeatedly rerun until a favorable result appears.

The report should identify where the procedure diverged and preserve the observed failure when practical.

## Independence boundary

A result is described as external only when it was executed outside the project's own certification campaign.

Project-maintainer CI, maintainer-operated local runs, repository traffic metrics, clones, views, and automated infrastructure activity are not classified as independent reproduction.

External does not necessarily mean formally audited. The evaluator's relationship to the project should be disclosed when relevant.

## Evidence integrity

Independent evidence should be preserved without rewriting unsuccessful observations.

When practical, a report should include cryptographic hashes for evidence artifacts and identify the source commit before execution.

Evidence generated against one source revision must not be represented as evidence for another revision without an explicit compatibility analysis.

## Suggested report format

```text
Nexus V2700 External Reproduction Report

Evaluator:
Date:
Operating system:
Python:
Nexus tag:
Commit SHA:

Evaluation class:
Commands executed:
Test result:
CLI result:
Distributed runtime result:
Physical resilience experiment: executed / not executed

Observed result:
Deviations:
Errors or limitations:
Evidence location:
Evidence SHA-256:
Additional notes:
```

## Submission

A report may be submitted publicly through the Nexus repository issue or discussion mechanism when one is available, or referenced from an independently controlled public repository or archive.

The project should preserve the evaluator's reported result without changing a failure into a success classification.

A maintainer may verify that the report contains the required metadata and evidence references, but that verification must not be described as independent certification of the evaluator or environment.

## Interpretation boundary

An independent reproduction increases the external evidence available for the documented scenario. It does not by itself establish production certification, universal fault tolerance, formal equivalence to another distributed consensus system, or performance superiority.

Multiple independent reproductions should remain separately attributable rather than being collapsed into the project's original certification population.

## Current project boundary

The certified Axis 11 project population remains 29 physical samples (`run011` through `run039`).

`run010` remains preserved as incomplete and is not counted. No `run040` was created as part of the project certification campaign.

An independently executed external reproduction is a new external observation and must not be silently inserted into the closed Axis 11 population.
