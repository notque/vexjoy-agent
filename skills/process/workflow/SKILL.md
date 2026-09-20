---
name: workflow
description: "Repository workflow contracts: feature state, saved plans, objective loops, metric hill climbs, and workflow dispatch."
user-invocable: true
context: fork
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Skill, Agent, Task]
routing:
  force_route: true
  not_for: "code review (use review), testing (use testing), security (use security)"
  triggers: ["workflow", "multi-phase task", "feature lifecycle", "create plan", "keep working until", "iterate until done", "hill climb", "profile and optimize", "structured pipeline"]
  category: process
  pairs_with: [review, testing, security, pr-workflow]
---

# Workflow

Choose one mode. Load only its named reference; do not preload the catalog.

## Feature lifecycle

For DESIGN → PLAN → IMPLEMENT → VALIDATE → RELEASE, use
`references/fl-pipeline.md`. Existing `.feature/` state is authoritative and is
read or changed only through `python3 ~/.claude/scripts/feature-state.py`; never
edit its state files directly. A later phase requires the preceding phase's
artifact and gate.

## Saved planning

Load the one matching contract:

| Need | Reference |
|---|---|
| specification | `references/pl-spec.md` |
| ambiguity triage | `references/pl-ambiguity-triage.md` |
| depth-first interview | `references/pl-depth-first-interview.md` |
| empirical choice | `references/pl-empirical-prototype.md` |
| file-backed plan | `references/pl-plan-files.md` |
| plan validation | `references/pl-check.md` |
| pause / resume | `references/pl-pause.md` / `references/pl-resume.md` |

Batch independent interview questions; ask dependent ones after their evidence
exists. Another person's facts or approval are obtained with
`references/pl-human-source-elicitation.md`.

## Objective loop

Use `references/ol-SPEC.md` and `references/ol-state-file.md`. Freeze objective,
budget, forbidden shortcuts, and deterministic done commands before iteration.
State lives at `.objective/<slug>/state.md`; wakeups resume from it, not chat
memory. Workers route through `/do`; they do not edit inline. Re-run every done
criterion yourself after each iteration. A criterion cannot be met by weakening
a test, hook, gate, or safety control. Stop on success, exhausted budget, or an
irreconcilable guardrail and report every criterion's status.

## Hill climb

Use `references/hc-SPEC.md`, `references/hc-ledger.md`, and the applicable entry
in `references/hc-domain-playbooks.md`. Freeze one metric, a pinned fixture, a
deterministic measurement command, correctness floors, target, repeat count,
variance tolerance, and budget. Profile before changing. Make one hypothesis
and one change per iteration; revert on a failed floor. Accept only a repeatable
improvement beyond baseline spread. Stop when the target, budget, or plateau
rule fires.

## Other multi-stage work

Use `references/pipeline-index.json` to select an existing workflow. Preserve
its gates and output schema. Skip workflow dispatch for lookup/status work, a
single mechanical edit, or work one agent can finish and verify. Multi-agent
dispatch is justified by independent subtasks, orthogonal verification, or an
explicit comprehensive/adversarial request.

`workflow` is the prose term. `pipeline` remains a compatibility identifier in
existing routing keys, exports, filenames, and the index; do not rename it.

On missing state or artifacts, stop or route to the producing phase. On noisy
measurements, stabilize the harness before optimizing. On exhausted budget,
report NOT DONE rather than relaxing the gate.
