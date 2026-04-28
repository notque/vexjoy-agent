# Failure Signatures Reference

> **Scope**: Observable patterns that identify each of the 5 workflow failure types — what they look like in git history, plan files, and working tree state. Complements detectors.md (which defines confidence scoring) with concrete grep commands and symptom-to-failure mappings.
> **Version range**: all git versions
> **Generated**: 2026-04-17

---

## Overview

Each failure type produces a distinct signature in the evidence. This file maps observable signals to failure types, provides grep commands to surface each signature, and documents the causal chains that connect multiple failures. When multiple detectors fire, the causal chain often matters more than individual findings.

---

## Failure Type Signatures

### Type 1: Stuck Loop

**Git signature**: Same file in 3+ consecutive commits, often with similar messages.

```bash
# Surface candidate files (any with 3+ appearances on branch)
git log main..HEAD --name-only --format="" | \
  grep -v "^$" | sort | uniq -c | sort -rn | awk '$1 >= 3 {print $0}'

# Show commit messages alongside file lists to check message similarity
git log main..HEAD --reverse --format="--- %h: %s" --name-only | \
  grep -v "^$"

# Check if a specific file appears in consecutive commits
git log main..HEAD --reverse --name-only --format="COMMIT %h" | \
  grep -B1 -A3 "path/to/suspected.go"
```

**Distinguishing iteration from oscillation**:

| Signal | Iteration (normal) | Oscillation (loop) |
|--------|-------------------|-------------------|
| Commit messages | Progressive ("add test", "refactor", "add docs") | Repetitive ("fix lint", "fix lint", "fix lint") |
| Net file diff | Large (new code was added) | Near-zero (changes cancel out) |
| Commit interval | Variable (thinking time varies) | Uniform (automated retry cadence) |

**Most reliable detection**: `git diff FIRST_COMMIT LAST_COMMIT -- file.go` shows near-zero net change despite multiple intermediate commits. This is oscillation, not iteration.

---

### Type 2: Missing Artifacts

**Plan signature**: Phase marked `[x]` complete but no corresponding output files exist.

```bash
# Find the plan file and extract completed phases
grep -n "\[x\]" task_plan.md 2>/dev/null

# For each completed phase, check if expected artifacts exist
# IMPLEMENT/EXECUTE phases → look for new/modified source files
git log main..HEAD --name-only --format="" | grep -v "^$" | sort -u

# TEST/VERIFY phases → look for test files
find . -name "*_test.go" -newer task_plan.md 2>/dev/null
find . -name "*.test.ts" -newer task_plan.md 2>/dev/null
find . -name "test_*.py" -newer task_plan.md 2>/dev/null

# Check if artifacts were created then deleted (ghost artifacts)
git log main..HEAD --diff-filter=D --name-only --format="" | grep -v "^$"
```

**Artifact expectations by phase type**:

| Phase Keyword | Expected Artifacts | How to Detect Missing |
|--------------|-------------------|----------------------|
| `PLAN`, `UNDERSTAND` | `task_plan.md`, design docs | `ls task_plan.md` |
| `IMPLEMENT`, `EXECUTE` | New/modified source files | `git log --name-only` |
| `TEST`, `VERIFY` | Test files, CI output | `find . -name "*_test*"` |
| `REVIEW` | Review comments, approvals | PR comments, review files |

---

### Type 3: Abandoned Work

**Git signature**: Incomplete plan, significant timestamp gap from last commit.

```bash
# Get last commit timestamp
git log -1 --format="%ai"

# Get branch age since first commit
git log main..HEAD --reverse --format="%ai" | head -1

# Check for incomplete phases in plan
grep -n "^- \[ \]" task_plan.md 2>/dev/null  # unchecked items
grep -n "Currently in Phase" task_plan.md 2>/dev/null

# Without a plan: check for a branch with commits but no PR
gh pr list --head "$(git branch --show-current)" --state all 2>/dev/null | wc -l
```

**Confidence calculation** (requires timestamps):

| Last commit age | Incomplete phases | Confidence |
|----------------|-----------------|------------|
| > 24 hours | Yes, "Currently in Phase X" present | **High** |
| > 3× avg commit interval | Yes | **Medium** |
| < 1 hour | Yes | **Low** (may be active) |

---

### Type 4: Scope Drift

**Git signature**: Files modified outside the directories/packages named in the plan.

```bash
# Extract all files modified on the branch
git log main..HEAD --name-only --format="" | grep -v "^$" | sort -u

# Compare against plan scope — find files NOT matching expected directories
# Replace "expected/dir/" with the actual scope from the plan
git log main..HEAD --name-only --format="" | grep -v "^$" | \
  grep -v "^expected/dir/" | grep -v "^another/expected/" | sort -u

# Find infrastructure/config files that weren't in scope
git log main..HEAD --name-only --format="" | grep -v "^$" | \
  grep -E "\.(yml|yaml|json|toml|mk|Makefile|dockerfile)$|^\.github/"
```

**Drift severity mapping**:

| Files modified outside scope | Severity |
|-----------------------------|----------|
| Sibling subdirectory of target package | Minor |
| Different package, same service | Moderate |
| Config files (`.github/`, `Makefile`, `*.yml`) | Major |
| Completely unrelated domain | Major |

---

### Type 5: Crash/Interruption

**Multi-indicator signature**: Uncommitted changes + incomplete plan + (optionally) orphaned worktree.

```bash
# Indicator 1: uncommitted changes
git status --short | grep -E "^[MAD?]"

# Indicator 2: incomplete plan phases
grep -c "^- \[ \]" task_plan.md 2>/dev/null  # count of unchecked items

# Indicator 3: orphaned worktrees
git worktree list --porcelain | grep "prunable"

# Indicator 4: debug session file with pending next action
ls -la .debug-session.md 2>/dev/null
grep "Next Action" .debug-session.md 2>/dev/null
```

**Indicator count → confidence**:

| Indicators present | Confidence |
|-------------------|------------|
| 3+ simultaneously | **High** |
| 2 | **Medium** |
| 1 alone | **Low** |

---

## Causal Chain Patterns

When multiple detectors fire, these chains appear frequently:

### Chain A: Context Exhaustion

**Sequence**: Stuck Loop → Missing Artifacts → Crash/Interruption

**What happened**: Agent entered a lint/type fix loop. Repeated retries consumed context budget. Session terminated before Phase VERIFY could produce artifacts. No uncommitted changes (session crashed cleanly, changes were committed in the loop).

**Detection**:
```bash
# Look for this chain: many fix commits + missing test artifacts + no uncommitted changes
git log main..HEAD --format="%s" | grep -c -iE "(fix|retry|attempt)"  # high count
find . -name "*_test*" -newer task_plan.md 2>/dev/null | wc -l  # zero
git status --short | wc -l  # zero (clean crash)
```

---

### Chain B: Interrupted Mid-Phase

**Sequence**: Crash/Interruption → Abandoned Work

**What happened**: Session crashed mid-phase (connection drop, OOM, manual kill). Uncommitted changes present. Plan shows "Currently in Phase X" with no subsequent commits.

**Detection**:
```bash
git status --short | grep -v "^$"  # non-empty: uncommitted changes exist
grep "Currently in Phase" task_plan.md  # mid-phase marker
git log -1 --format="%ai"  # timestamp of last commit before crash
```

---

### Chain C: Scope Drift Leading to Loop

**Sequence**: Scope Drift → Stuck Loop

**What happened**: Agent modified infrastructure files (config, CI) outside scope. Those changes introduced a constraint (CI check, lint rule) the agent didn't anticipate. Agent then looped trying to satisfy the new constraint.

**Detection**:
```bash
# Find when infrastructure files were first touched
git log main..HEAD --reverse --name-only --format="COMMIT %h %s" | \
  grep -A5 "COMMIT" | grep -E "(\.yml|\.yaml|Makefile|\.github)"

# Then check if loop commits started after that point
git log main..HEAD --reverse --format="%h %s" | grep -iE "(fix|retry)"
```

---

## Investigation Guardrails
<!-- no-pair-required: section header introducing paired-pattern subsections below -->

### ❌ Stopping after the first detector fires

**Detection**:
<!-- no-pair-required: false positive - comment inside fenced code block; block is paired with Why wrong section below -->
```bash
# This is a process issue, not a git pattern — watch for it in your own analysis
# If you found Detector 1 (Stuck Loop), still run Detectors 2-5
```
<!-- no-pair-required: false positive - comment inside fenced code block; paired with Why wrong section below -->

**Why wrong**: Causal chains mean the first visible symptom is rarely the root cause. A stuck loop (Detector 1) often causes missing artifacts (Detector 2) and may have been triggered by scope drift (Detector 4). Stopping at the first finding produces a symptom report, not a root cause hypothesis.

---

### ❌ Assigning High confidence without verifying consecutiveness

**Detection**:
<!-- no-pair-required: false positive - comment inside fenced code block; block is paired with Why wrong section below -->
```bash
# Before High confidence on Detector 1, run this consecutiveness check:
git log main..HEAD --reverse --name-only --format="COMMIT %h" | \
  grep -E "(COMMIT|suspected-file)"
# If COMMIT lines between suspected-file occurrences contain OTHER files, it's not consecutive
```
<!-- no-pair-required: false positive - shell comment inside fenced code block; this block pairs with Why wrong below -->

**Why wrong**: A file in positions 1, 5, 9 of a 10-commit branch is not a stuck loop — it's iterative development. High confidence Detector 1 requires the same file in positions N, N+1, N+2 (adjacent).

---

## Error-Fix Mappings

| Symptom in Report | Root Cause | Recommended Fix |
|------------------|------------|-----------------|
| "Plan shows Phase 3 complete but no test files found" | Agent marked phase complete prematurely | Re-run Phase 3; clarify artifact definitions in plan |
| "6 commits all touching server.go with near-identical diffs" | Lint error agent couldn't resolve | Manually fix the lint error, then resume from last successful phase |
| "Worktree at .claude/worktrees/feat-x references deleted branch" | Session crashed during worktree cleanup | `git worktree prune` to remove stale registration |
| "task_plan.md shows 'Currently in Phase 2', last commit 3 days ago" | Session abandoned mid-flight | Resume from Phase 2; check uncommitted changes first |
| "12 commits in 4 minutes, all on same file" | Automated retry loop (no human pacing) | Identify the failing constraint, fix manually, squash loop commits |
