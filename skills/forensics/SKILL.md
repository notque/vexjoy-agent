---
name: forensics
description: "Post-mortem diagnostic analysis of failed workflows."
version: 1.0.0
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
    - plan-checker
  complexity: Medium
  category: process
---

# Forensics Skill

Investigate failed or stuck workflows through post-mortem analysis of git history, plan files, and session artifacts. Forensics answers "what went wrong and why" -- it detects workflow-level failures that individual tool errors don't reveal.

**Key distinction**: A tool error is "ruff found 3 lint errors." A workflow failure is "the agent entered a fix/retry loop editing the same file 5 times and never progressed." The error-learner handles tool-level errors. Forensics handles workflow-level patterns.

## Instructions

This is a **read-only diagnostic**. The tool restriction to Read/Grep/Glob enforces this at the platform level. A diagnostic tool that modifies state destroys the evidence it needs to analyze -- forensics examines, it does not fix. Even when the user asks you to fix what you find, complete the report and recommend remediation instead. The wrong fix applied automatically can destroy work.

### Phase 1: GATHER

**Goal**: Collect the raw evidence needed for anomaly detection. Determine what branch, plan, and time range to analyze.

**Step 1: Identify the investigation target**

Accept the target from one of these sources (in priority order):
1. **Explicit branch**: User specifies a branch name to investigate
2. **Current branch**: Use the current git branch if no branch specified
3. **Explicit plan**: User points to a specific `task_plan.md`

Before analysis, read the repository's CLAUDE.md if present. Repository conventions inform what "normal" looks like (e.g., expected branch patterns, required artifacts).

**Step 2: Locate the plan file**

Search for the plan that governed the workflow:
- Check `task_plan.md` in the repository root
- Check `.feature/state/plan/` for feature plans
- Check `plan/active/` for workflow-orchestrator plans

Record whether a plan exists. If no plan is found, note this -- it limits scope drift and abandoned work detection but does not block the investigation. Three of the five detectors (stuck loop, crash/interruption, and degraded abandoned work) still function without a plan, so never skip analysis because no plan file was found.

**Step 3: Collect git history**

Read the git log for the target branch. Extract:
- Commit hashes, messages, timestamps, and files changed
- The branch's divergence point from main/master

Use Grep to search git log output for patterns. Focus on:
- Commits on this branch since divergence from the base branch
- File change frequency across commits
- Commit message patterns (similarity, repetition)

If the branch has hundreds of commits, focus on the most recent 50 and note the truncation in the final report.

**Step 4: Check working tree state**

Examine the current state:
- Are there uncommitted changes? (look for modified/untracked indicators)
- Are there orphaned `.claude/worktrees/` directories?
- Is there an active `task_plan.md` with incomplete phases?

**GATE**: Evidence collected. At minimum: git history available, branch identified. Proceed to DETECT only when evidence gathering is complete.

---

### Phase 2: DETECT

**Goal**: Run all 5 anomaly detectors against the collected evidence. Always run every detector -- anomalies are often correlated (a stuck loop causes missing artifacts causes abandoned work), so partial analysis misses the causal chain. Each detector produces zero or more findings, and every finding must include a confidence level (High/Medium/Low) because false positives erode trust. A "High" confidence stuck loop (5 identical commits) is qualitatively different from a "Low" confidence one (3 commits to the same file with different messages).

#### Detector 1: Stuck Loop

**Signal**: Same file appearing in 3+ consecutive commits.

Analyze the git history for files that appear in consecutive commits:
1. List files changed in each commit (ordered chronologically)
2. Identify files that appear in 3 or more consecutive commits
3. For each candidate, analyze commit message similarity

**Confidence scoring**:

| Pattern | Confidence | Rationale |
|---------|------------|-----------|
| Same file in 5+ consecutive commits, near-identical messages | **High** | Strong loop signal -- agent retrying the same fix |
| Same file in 4+ consecutive commits, varied messages | **Medium** | Possible loop, but varied messages suggest different approaches |
| Same file in 3 consecutive commits, different messages | **Low** | Could be legitimate iterative development |
| Same file in 3+ commits with messages containing "fix", "retry", "attempt" | **High** | Explicit retry language strengthens the signal regardless of count |

**False positive awareness**: Legitimate multi-pass refactoring (e.g., "extract method", "add tests", "clean up") touches the same file repeatedly with genuinely different messages. Check whether the file's changes are cumulative (refactoring) or oscillating (loop). Oscillating changes -- where content reverts and re-applies -- are the strongest stuck loop signal. When evidence is ambiguous, report it at Low confidence rather than suppressing the finding -- let the consumer decide.

#### Detector 2: Missing Artifacts

**Signal**: Pipeline phase ran but produced no expected output.

If a plan file exists, check each phase for expected artifacts:

| Phase Type | Expected Artifacts |
|------------|-------------------|
| PLAN / UNDERSTAND | `task_plan.md`, design documents |
| IMPLEMENT / EXECUTE | New or modified source files matching plan scope |
| TEST / VERIFY | Test files, test results, verification output |
| REVIEW | Review comments, approval artifacts |

For each phase marked complete (or partially complete) in the plan:
1. Check whether the expected artifacts exist
2. If missing, check git history for whether they were created then deleted

**Confidence scoring**:

| Pattern | Confidence |
|---------|------------|
| Phase marked complete, zero artifacts found, no git evidence of creation | **High** |
| Phase marked complete, partial artifacts found | **Medium** |
| Phase marked in-progress, artifacts missing | **Low** (may still be generating) |

If no plan file exists, skip this detector and note: "No plan file found -- missing artifact detection requires a plan to define expected outputs."

#### Detector 3: Abandoned Work

**Signal**: Active plan with incomplete phases and a significant timestamp gap.

Requirements: plan file must exist with timestamp-trackable phases.

1. Read the plan file for phase completion status
2. Extract the last commit timestamp on the branch
3. Calculate the gap between last commit and current time
4. Calculate the branch's average commit interval (total time span / number of commits)

**Confidence scoring**:

| Pattern | Confidence |
|---------|------------|
| Plan shows "Currently in Phase X", last commit >24h ago, phases incomplete | **High** |
| Last commit gap exceeds 3x the branch's average commit interval | **Medium** |
| Plan has incomplete phases but last commit is recent (less than 1h ago) | **Low** (session may be active) |

If no plan file exists, fall back to git-only analysis: a branch with incomplete work (no merge, no PR) and a large timestamp gap from last commit is a weaker abandoned work signal.

#### Detector 4: Scope Drift

**Signal**: Files modified outside the plan's expected domain.

Requirements: plan file must exist with identifiable scope (file paths, package names, or domain descriptions).

1. Extract the plan's expected scope (file paths, directories, packages mentioned)
2. List all files actually modified on the branch (from git history)
3. Compare: which modified files fall outside the expected scope?

**Drift severity**:

| Drift Type | Severity | Example |
|------------|----------|---------|
| Adjacent package | Minor | Plan targets `pkg/auth/`, also modified `pkg/auth/testutil/` |
| Different domain | Moderate | Plan targets `pkg/auth/`, also modified `pkg/billing/` |
| Infrastructure/config not in plan | Major | Plan targets feature code, also modified `.github/workflows/`, `Makefile`, or config files |
| Unrelated files | Major | Plan targets Go code, also modified `docs/README.md` or JavaScript files |

**Confidence scoring**:

| Pattern | Confidence |
|---------|------------|
| Multiple major-severity drifts | **High** |
| Single major or multiple moderate drifts | **Medium** |
| Minor drifts only | **Low** |

If no plan file exists, skip this detector and note: "No plan file found -- scope drift detection requires a plan to define expected scope."

#### Detector 5: Crash/Interruption

**Signal**: Evidence of abnormal session termination.

Check for the combination of these indicators:

| Indicator | How to Check |
|-----------|-------------|
| Uncommitted changes | Look for modified/untracked files in working tree |
| Active plan with incomplete phases | Read `task_plan.md` for "Currently in Phase" with unchecked items |
| Orphaned worktrees | Check `.claude/worktrees/` for directories that reference non-existent branches or stale sessions |
| Debug session file | Check for `.debug-session.md` with a "Next Action" that was never executed |

**Confidence scoring**:

| Indicators Present | Confidence |
|-------------------|------------|
| 3+ indicators simultaneously | **High** |
| 2 indicators | **Medium** |
| 1 indicator alone | **Low** (may be normal state) |

**GATE**: All 5 detectors have run. Each produced zero or more findings with confidence levels. Proceed to REPORT.

---

### Phase 3: REPORT

**Goal**: Compile findings into a structured diagnostic report with root cause hypothesis and remediation recommendations. Every claim in the report must trace to specific evidence -- a forensics report without evidence is an opinion piece, not a diagnostic.

**Step 1: Scrub sensitive content**

Before assembling the report, scan all evidence strings for:
- API keys, tokens, passwords (patterns: `sk-`, `ghp_`, `token=`, `password=`, `secret=`, `key=`, bearer tokens, base64-encoded credentials)
- Absolute home directory paths

Replace sensitive values with `[REDACTED]` and home paths with `~/`. Treat all credential-shaped strings as real -- you cannot determine whether a credential is live from its format alone. Reports may be shared or logged, so a leaked credential in a forensics report is worse than the original workflow failure. Redact paths in every report regardless of audience; it costs nothing and prevents future exposure.

**Step 2: Compile anomaly table**

Order findings by confidence (High first, then by detector number) so the reader gets the strongest signals first:

```
## Forensics Report: [branch name or session identifier]

### Anomalies Detected
| # | Type | Confidence | Description |
|---|------|------------|-------------|
| 1 | [type] | [High/Medium/Low] | [description with evidence] |
| 2 | [type] | [High/Medium/Low] | [description with evidence] |
```

If no anomalies detected:
```
### Anomalies Detected
No anomalies detected. The workflow appears to have executed normally.
```

**Step 3: Synthesize root cause hypothesis**

Connect the anomalies into a coherent narrative. Look for causal chains:
- Stuck loop + scope drift = agent tried to fix a problem, drifted into unrelated files looking for the root cause
- Missing artifacts + abandoned work = session crashed before producing outputs
- Crash/interruption + stuck loop = agent exhausted retries and was terminated

The hypothesis must be specific, testable, and grounded in evidence from the anomaly findings -- never speculate beyond what the data supports:
- BAD: "Something went wrong during execution"
- GOOD: "Agent entered a lint fix loop on server.go (4 consecutive commits with 'fix lint' messages), which consumed the session's context budget before Phase 3 VERIFY could execute, leaving test artifacts missing"

**Step 4: Recommend remediation**

Provide specific, actionable recommendations. Each recommendation should reference the anomaly it addresses. Remediation is advisory text only -- never execute fixes, even if the user asks. Remediation requires understanding intent, not just detecting anomalies.

| Anomaly Type | Typical Remediation |
|--------------|-------------------|
| Stuck loop | Identify the root cause of the loop (often a lint/type error the agent can't resolve). Fix manually, then resume from the last successful phase. |
| Missing artifacts | Re-run the phase that failed to produce artifacts. Check if the phase definition is clear enough for the executor. |
| Abandoned work | Resume from the last completed phase. Check `.debug-session.md` or plan status for where to pick up. |
| Scope drift | Review out-of-scope changes for necessity. Revert unrelated changes. Re-scope the plan if the drift was needed. |
| Crash/interruption | Check for uncommitted changes worth preserving. Clean up orphaned worktrees. Resume from last committed state. |

**Step 5: Format final report**

Include relevant git log excerpts, file snippets, and timestamps as evidence for every anomaly. Show git hashes, timestamps, and file paths rather than making unsupported assertions.

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
 | ... | ... | ... | ... |

================================================================
 ROOT CAUSE HYPOTHESIS
================================================================

 [Narrative connecting anomalies into causal explanation]

================================================================
 RECOMMENDED REMEDIATION
================================================================

 1. [Specific action referencing anomaly #N]
 2. [Specific action referencing anomaly #N]

================================================================
 EVIDENCE
================================================================

 [Relevant git log excerpts, file snippets, timestamps]
 [All paths redacted, credentials scrubbed]

================================================================
```

**GATE**: Report is complete, scrubbed, and formatted. Deliver to user.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No git history on branch | Branch has zero commits or just forked | Report "insufficient evidence" -- forensics needs commit history to analyze |
| No plan file found | Workflow ran without a plan | Note limitation in report. Detectors 2 (missing artifacts), 3 (abandoned work), and 4 (scope drift) operate in degraded mode or skip. Detectors 1 (stuck loop) and 5 (crash) still function. |
| Worktree access fails | Orphaned worktree with broken symlinks | Report the orphaned worktree as crash/interruption evidence. Do not attempt cleanup. |
| Git log too large | Long-lived branch with hundreds of commits | Focus analysis on the most recent 50 commits. Note truncation in report. |
| Ambiguous branch target | User request doesn't clearly identify which branch | Ask: "Which branch should I investigate? Current branch is [X]." |

## References

- [ADR-073: Forensics Meta-Workflow Diagnostics](/adr/073-forensics-meta-workflow-diagnostics.md)
- [Systematic Debugging](skills/workflow/references/systematic-debugging.md) -- for code-level bugs (not workflow-level)
- [Workflow Orchestrator](skills/workflow/references/workflow-orchestrator.md) -- produces the plans forensics analyzes
- [Plan Checker](/skills/plan-checker/SKILL.md) -- validates plans pre-execution (forensics analyzes post-execution)
- [Error Learner Hook](/hooks/error-learner.py) -- handles tool-level errors (forensics handles workflow-level patterns)
