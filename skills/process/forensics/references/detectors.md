# Forensics Anomaly Detectors

Full detector specifications for Phase 2: DETECT. Run all 5 detectors every time -- anomalies are often correlated, so partial analysis misses the causal chain.

Each detector produces zero or more findings. Every finding must include a confidence level (High/Medium/Low).

---

## Detector 1: Stuck Loop

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

---

## Detector 2: Missing Artifacts

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

---

## Detector 3: Abandoned Work

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

---

## Detector 4: Scope Drift

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

---

## Detector 5: Crash/Interruption

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
