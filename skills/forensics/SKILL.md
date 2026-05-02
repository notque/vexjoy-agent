---
name: forensics
description: "Post-mortem diagnostic analysis of failed workflows."
user-invocable: false
command: /forensics
allowed-tools:
  - Read
  - Grep
  - Glob
routing:
  triggers:
    - forensics
    - what went wrong
    - why did this fail
    - stuck loop
    - diagnose workflow
    - post-mortem
    - workflow failure
    - session crashed
    - why is this stuck
    - investigate failure
    - "why did this break"
    - "incident review"
  pairs_with:
    - workflow
    - planning
  complexity: Medium
  category: process
---

# Forensics Skill

Investigate failed or stuck workflows through post-mortem analysis of git history, plan files, and session artifacts. Answers "what went wrong and why" -- detects workflow-level failures that individual tool errors don't reveal.

**Key distinction**: A tool error is "ruff found 3 lint errors." A workflow failure is "the agent entered a fix/retry loop editing the same file 5 times and never progressed." Error-learner handles tool-level errors. Forensics handles workflow-level patterns.

## Reference Loading

| Task | Load |
|------|------|
| Git evidence collection, git log commands, credential scrubbing | `references/evidence-collection.md` |
| Failure type identification, causal chain analysis | `references/failure-signatures.md` |
| Running anomaly detectors, scoring confidence | `references/detectors.md` |

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `detectors.md` | Loads detailed guidance from `detectors.md`. |
| tasks related to this reference | `evidence-collection.md` | Loads detailed guidance from `evidence-collection.md`. |
| tasks related to this reference | `failure-signatures.md` | Loads detailed guidance from `failure-signatures.md`. |

## Instructions

This is a **read-only diagnostic**. Tool restriction to Read/Grep/Glob enforces this at the platform level. A diagnostic that modifies state destroys the evidence it needs. Complete the report and recommend remediation -- never execute fixes.

### Phase 1: GATHER

**Goal**: Collect raw evidence for anomaly detection.

**Step 1: Identify the investigation target**

Priority order:
1. **Explicit branch**: User specifies a branch name
2. **Current branch**: Default if none specified
3. **Explicit plan**: User points to a specific `task_plan.md`

Read CLAUDE.md if present -- repository conventions inform what "normal" looks like.

**Step 2: Locate the plan file**

Search:
- `task_plan.md` in repository root
- `.feature/state/plan/` for feature plans
- `plan/active/` for workflow-orchestrator plans

If no plan found, note this. Three of five detectors (stuck loop, crash/interruption, degraded abandoned work) still function without a plan.

**Step 3: Collect git history**

Extract from target branch: commit hashes, messages, timestamps, files changed, divergence point from main/master. Focus on:
- Commits since divergence from base branch
- File change frequency across commits
- Commit message patterns (similarity, repetition)

If branch has hundreds of commits, focus on most recent 50 and note truncation.

**Step 4: Check working tree state**

- Uncommitted changes?
- Orphaned `.claude/worktrees/` directories?
- Active `task_plan.md` with incomplete phases?

> See `references/evidence-collection.md` for concrete git commands, loop detection queries, timestamp analysis, and credential scrubbing patterns.

**GATE**: Evidence collected. At minimum: git history available, branch identified.

---

### Phase 2: DETECT

**Goal**: Run all 5 anomaly detectors. Always run every detector -- anomalies are often correlated (stuck loop causes missing artifacts causes abandoned work). Each finding must include confidence (High/Medium/Low).

> See `references/detectors.md` for full specifications, confidence scoring, false positive guidance, and skip conditions.
> See `references/failure-signatures.md` for observable patterns, detection commands, and causal chain analysis.

Run detectors 1-5 in order: Stuck Loop, Missing Artifacts, Abandoned Work, Scope Drift, Crash/Interruption.

**GATE**: All 5 detectors run. Each produced zero or more findings with confidence levels.

---

### Phase 3: REPORT

**Goal**: Compile findings into structured diagnostic with root cause hypothesis and remediation. Every claim must trace to specific evidence.

**Step 1: Scrub sensitive content**

Scan evidence for:
- API keys, tokens, passwords (`sk-`, `ghp_`, `token=`, `password=`, `secret=`, `key=`, bearer tokens, base64 credentials)
- Absolute home directory paths

Replace sensitive values with `[REDACTED]`, home paths with `~/`. Treat all credential-shaped strings as real.

**Step 2: Compile anomaly table**

Order by confidence (High first), then detector number:

```
## Forensics Report: [branch name or session identifier]

### Anomalies Detected
| # | Type | Confidence | Description |
|---|------|------------|-------------|
| 1 | [type] | [High/Medium/Low] | [description with evidence] |
```

If no anomalies: "No anomalies detected. The workflow appears to have executed normally."

**Step 3: Synthesize root cause hypothesis**

Connect anomalies into causal chains:
- Stuck loop + scope drift = agent drifted into unrelated files seeking root cause
- Missing artifacts + abandoned work = session crashed before producing outputs
- Crash/interruption + stuck loop = agent exhausted retries and was terminated

Hypothesis must be specific, testable, grounded in evidence:
- BAD: "Something went wrong during execution"
- GOOD: "Agent entered a lint fix loop on server.go (4 consecutive 'fix lint' commits), consuming context budget before Phase 3 VERIFY could execute"

**Step 4: Recommend remediation**

Specific, actionable, referencing the anomaly. Never execute fixes.

| Anomaly Type | Typical Remediation |
|--------------|-------------------|
| Stuck loop | Identify root cause (often unresolvable lint/type error). Fix manually, resume from last successful phase. |
| Missing artifacts | Re-run the phase that failed. Check phase definition clarity. |
| Abandoned work | Resume from last completed phase. Check `.debug-session.md` or plan status. |
| Scope drift | Review out-of-scope changes. Revert unrelated changes. Re-scope if drift was needed. |
| Crash/interruption | Check uncommitted changes. Clean orphaned worktrees. Resume from last committed state. |

**Step 5: Format final report**

Include git log excerpts, file snippets, and timestamps as evidence.

```
================================================================
 FORENSICS REPORT: [branch/session identifier]
================================================================

 Scan completed: [timestamp]
 Branch: [branch name]
 Commits analyzed: [count]
 Plan file: [path or "not found"]

================================================================
 ANOMALIES
================================================================

 | # | Type | Confidence | Description |
 |---|------|------------|-------------|

================================================================
 ROOT CAUSE HYPOTHESIS
================================================================

 [Narrative connecting anomalies]

================================================================
 RECOMMENDED REMEDIATION
================================================================

 1. [Action referencing anomaly #N]

================================================================
 EVIDENCE
================================================================

 [Git log excerpts, file snippets, timestamps]
 [All paths redacted, credentials scrubbed]

================================================================
```

**GATE**: Report complete, scrubbed, formatted. Deliver to user.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No git history | Zero commits or just forked | Report "insufficient evidence" |
| No plan file | Workflow ran without plan | Note limitation. Detectors 1 (stuck loop) and 5 (crash) still function. Detectors 2-4 operate in degraded mode or skip. |
| Worktree access fails | Orphaned worktree with broken symlinks | Report as crash/interruption evidence. Do not attempt cleanup. |
| Git log too large | Long-lived branch | Focus on most recent 50 commits. Note truncation. |
| Ambiguous branch | User request unclear | Ask: "Which branch should I investigate? Current branch is [X]." |

## References

- [ADR-073: Forensics Meta-Workflow Diagnostics](/adr/073-forensics-meta-workflow-diagnostics.md)
- [Systematic Debugging](skills/workflow/references/systematic-debugging.md) -- for code-level bugs (not workflow-level)
- [Workflow Orchestrator](skills/workflow/references/workflow-orchestrator.md) -- produces the plans forensics analyzes
- [Planning umbrella — check intent](/skills/planning/references/check.md) -- validates plans pre-execution (forensics analyzes post-execution)
- [Error Learner Hook](/hooks/error-learner.py) -- handles tool-level errors (forensics handles workflow-level patterns)
