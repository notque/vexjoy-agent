---
name: forensics
description: |
  Post-mortem diagnostic analysis of failed or stuck workflows. Detects stuck
  loops, missing artifacts, abandoned work, scope drift, and crash/interruption
  patterns through git history and plan file analysis. Produces a structured
  diagnostic report with anomaly confidence levels, root cause hypotheses, and
  recommended remediation. READ-ONLY: never modifies files. Use for "forensics",
  "what went wrong", "why did this fail", "stuck loop", "diagnose workflow",
  "post-mortem", "workflow failure", or "session crashed". Do NOT use for
  debugging code bugs (use systematic-debugging), reviewing code quality (use
  systematic-code-review), or fixing issues (forensics only diagnoses).
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
    - systematic-debugging
    - workflow-orchestrator
    - plan-checker
  complexity: Medium
  category: process
---

# Forensics Skill

## Purpose

Investigate failed or stuck workflows through post-mortem analysis of git history, plan files, and session artifacts. The forensics skill answers "what went wrong and why" -- it detects workflow-level failures that individual tool errors don't reveal.

**Key distinction**: A tool error is "ruff found 3 lint errors." A workflow failure is "the agent entered a fix/retry loop editing the same file 5 times and never progressed." The error-learner handles tool-level errors. Forensics handles workflow-level patterns.

## Operator Context

This skill operates as a read-only diagnostic instrument. It examines git history, plan files, and worktree state to detect anomaly patterns, then produces a structured report. It never modifies files, creates commits, or attempts repairs.

### Hardcoded Behaviors (Always Apply)
- **READ-ONLY**: Never modify files, create commits, or attempt repairs. WHY: A diagnostic tool that modifies state destroys the evidence it needs to analyze. Forensics examines -- it does not fix. The tool restriction to Read/Grep/Glob enforces this at the platform level.
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before analysis. Repository conventions inform what "normal" looks like (e.g., expected branch patterns, required artifacts).
- **Credential Scrubbing**: Before including any file content or path in the report, scan for and redact patterns matching secrets (API keys, tokens, passwords, connection strings). WHY: Diagnostic reports may be shared or logged. Leaking credentials through a forensics report is worse than the original workflow failure.
- **Path Redaction**: Redact absolute home directory paths in report output. Replace paths like `/home/alice/` or `/Users/alice/` with `~/`. WHY: Reports shared across teams should not expose filesystem layout or usernames.
- **Confidence-Based Reporting**: Every anomaly includes a confidence level (High/Medium/Low) based on signal strength. WHY: False positives erode trust. A "High" confidence stuck loop (5 identical commits) is qualitatively different from a "Low" confidence one (3 commits to the same file with different messages). Consumers filter on confidence.
- **No Remediation Execution**: Recommended remediation is advisory text only. Forensics never executes fixes, even if the user asks. WHY: Remediation requires understanding intent, not just detecting anomalies. The wrong fix applied automatically can destroy work. Recommend, don't execute.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report findings factually with evidence. Show git hashes, timestamps, and file paths rather than making assertions. No self-congratulation.
- **Full Scan**: Run all 5 anomaly detectors on every invocation. Skipping detectors creates blind spots -- a stuck loop that also drifted scope is a different situation than a stuck loop alone.
- **Severity-Ordered Output**: Report anomalies ordered by confidence (High first). The reader needs the strongest signals first.
- **Evidence Inclusion**: Include relevant git log excerpts, file snippets, and timestamps as evidence for each anomaly. Claims without evidence are not diagnostics.

### Optional Behaviors (OFF unless enabled)
- **Cross-session comparison**: Compare current branch against other recent branches for pattern similarity (OFF by default -- requires broader git history scan).
- **Timeline visualization**: Produce ASCII timeline of commits with anomaly markers (OFF by default -- adds report length).

## What This Skill CAN Do
- Detect stuck fix/retry loops through git commit pattern analysis
- Identify missing pipeline artifacts by checking expected phase outputs
- Find abandoned work through timestamp gap analysis
- Measure scope drift by comparing modified files against plan expectations
- Detect crash/interruption through uncommitted changes and orphaned worktrees
- Produce structured diagnostic reports with confidence levels
- Scrub credentials and redact paths in report output

## What This Skill CANNOT Do
- Fix any of the issues it finds (read-only -- recommend only)
- Debug code-level bugs (use systematic-debugging)
- Review code quality (use systematic-code-review)
- Access external services or APIs (filesystem and git only)
- Analyze workflows that left no git history or plan files (no evidence = no diagnosis)
- Run shell commands (allowed-tools restricts to Read/Grep/Glob)

## Instructions

### Phase 1: GATHER

**Goal**: Collect the raw evidence needed for anomaly detection. Determine what branch, plan, and time range to analyze.

**Step 1: Identify the investigation target**

Accept the target from one of these sources (in priority order):
1. **Explicit branch**: User specifies a branch name to investigate
2. **Current branch**: Use the current git branch if no branch specified
3. **Explicit plan**: User points to a specific `task_plan.md`

**Step 2: Locate the plan file**

Search for the plan that governed the workflow:
- Check `task_plan.md` in the repository root
- Check `.feature/state/plan/` for feature plans
- Check `plan/active/` for workflow-orchestrator plans

Record whether a plan exists. If no plan is found, note this -- it limits scope drift and abandoned work detection but does not block the investigation.

**Step 3: Collect git history**

Read the git log for the target branch. Extract:
- Commit hashes, messages, timestamps, and files changed
- The branch's divergence point from main/master

Use Grep to search git log output for patterns. Focus on:
- Commits on this branch since divergence from the base branch
- File change frequency across commits
- Commit message patterns (similarity, repetition)

**Step 4: Check working tree state**

Examine the current state:
- Are there uncommitted changes? (look for modified/untracked indicators)
- Are there orphaned `.claude/worktrees/` directories?
- Is there an active `task_plan.md` with incomplete phases?

**GATE**: Evidence collected. At minimum: git history available, branch identified. Proceed to DETECT only when evidence gathering is complete.

---

### Phase 2: DETECT

**Goal**: Run all 5 anomaly detectors against the collected evidence. Each detector produces zero or more findings with confidence levels.

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

**False positive awareness**: Legitimate multi-pass refactoring (e.g., "extract method", "add tests", "clean up") touches the same file repeatedly with genuinely different messages. Check whether the file's changes are cumulative (refactoring) or oscillating (loop). Oscillating changes -- where content reverts and re-applies -- are the strongest stuck loop signal.

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

**Goal**: Compile findings into a structured diagnostic report with root cause hypothesis and remediation recommendations.

**Step 1: Scrub sensitive content**

Before assembling the report, scan all evidence strings for:
- API keys, tokens, passwords (patterns: `sk-`, `ghp_`, `token=`, `password=`, `secret=`, `key=`, bearer tokens, base64-encoded credentials)
- Absolute home directory paths

Replace sensitive values with `[REDACTED]` and home paths with `~/`.

**Step 2: Compile anomaly table**

Order findings by confidence (High first), then by detector number:

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

The hypothesis should be specific and testable, not generic:
- BAD: "Something went wrong during execution"
- GOOD: "Agent entered a lint fix loop on server.go (4 consecutive commits with 'fix lint' messages), which consumed the session's context budget before Phase 3 VERIFY could execute, leaving test artifacts missing"

**Step 4: Recommend remediation**

Provide specific, actionable recommendations. Each recommendation should reference the anomaly it addresses:

| Anomaly Type | Typical Remediation |
|--------------|-------------------|
| Stuck loop | Identify the root cause of the loop (often a lint/type error the agent can't resolve). Fix manually, then resume from the last successful phase. |
| Missing artifacts | Re-run the phase that failed to produce artifacts. Check if the phase definition is clear enough for the executor. |
| Abandoned work | Resume from the last completed phase. Check `.debug-session.md` or plan status for where to pick up. |
| Scope drift | Review out-of-scope changes for necessity. Revert unrelated changes. Re-scope the plan if the drift was needed. |
| Crash/interruption | Check for uncommitted changes worth preserving. Clean up orphaned worktrees. Resume from last committed state. |

**Step 5: Format final report**

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

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Attempting to fix detected issues | Forensics that modifies state destroys evidence and violates read-only constraint. A fix applied without understanding intent can make things worse. | Report findings and recommend remediation. Let the user decide what to fix. |
| Reporting anomalies without evidence | "There might be a stuck loop" without commit hashes or file names is not a diagnostic. Unsubstantiated claims waste the reader's time. | Include specific git hashes, file paths, timestamps, and commit messages for every anomaly. |
| Treating all anomalies as equal severity | A High confidence stuck loop and a Low confidence scope drift require different urgency. Flat reporting obscures priority. | Order by confidence. Lead with the strongest signals. |
| Running only some detectors | "The user asked about stuck loops so I'll skip the other detectors." Anomalies are often correlated -- a stuck loop causes missing artifacts causes abandoned work. Partial analysis misses the causal chain. | Run all 5 detectors. The user asked about one symptom, but the diagnosis may involve several. |
| Including raw credentials in report | Diagnostic reports may be shared, logged, or pasted into issues. A credential in a forensics report is a security incident. | Scrub before reporting. Always. |
| Guessing at root cause without evidence | "The agent probably ran out of context" without timestamp or commit evidence is speculation, not diagnosis. | Every claim in the root cause hypothesis must trace to a specific anomaly finding with evidence. |

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "I can see the problem, let me just fix it" | Forensics is read-only. Fixing destroys evidence. Even if the fix is obvious, the user needs the diagnostic to understand what happened. | Complete the report. Recommend the fix. Do not execute it. |
| "No plan file, so forensics can't help" | 3 of 5 detectors work without a plan (stuck loop, crash/interruption, and degraded abandoned work). Missing the plan limits analysis, it doesn't prevent it. | Run all detectors. Note limitations for plan-dependent detectors. Report what you can. |
| "This is just normal iterative development, not a loop" | That's what confidence levels are for. Report it as Low confidence if the evidence is ambiguous. Don't suppress findings based on your interpretation of intent. | Report the finding with appropriate confidence. Let the consumer decide. |
| "The report is long enough, I'll skip the evidence section" | A forensics report without evidence is an opinion piece. Evidence is what makes it a diagnostic. | Include evidence. Every anomaly must have supporting data in the evidence section. |
| "Credentials in this file aren't real secrets" | You cannot determine whether a credential is real from its format. Treat all credential-shaped strings as real. | Scrub all credential patterns. No exceptions. |
| "Path redaction isn't needed for internal reports" | You don't control where the report ends up. Internal today, shared tomorrow. | Redact paths in every report. It costs nothing and prevents future exposure. |

## References

- [ADR-073: Forensics Meta-Workflow Diagnostics](/adr/073-forensics-meta-workflow-diagnostics.md)
- [Systematic Debugging](/skills/systematic-debugging/SKILL.md) -- for code-level bugs (not workflow-level)
- [Workflow Orchestrator](/pipelines/workflow-orchestrator/SKILL.md) -- produces the plans forensics analyzes
- [Plan Checker](/skills/plan-checker/SKILL.md) -- validates plans pre-execution (forensics analyzes post-execution)
- [Error Learner Hook](/hooks/error-learner.py) -- handles tool-level errors (forensics handles workflow-level patterns)
- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
