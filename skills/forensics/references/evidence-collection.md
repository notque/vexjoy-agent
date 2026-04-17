# Evidence Collection Reference

> **Scope**: Concrete git commands and grep patterns for Phase 1 GATHER — collecting raw evidence before anomaly detection begins. Covers git log extraction, loop detection queries, working-tree inspection, and credential scrubbing patterns.
> **Version range**: git 2.5+
> **Generated**: 2026-04-17

---

## Overview

Evidence collection is the precondition for all 5 detectors. Running detectors on incomplete evidence produces false negatives. This file provides copy-pasteable commands for each evidence type needed in Phase 1 GATHER. All commands are read-only — forensics never modifies state.

---

## Git Log Extraction

### Full branch history since divergence

```bash
# List all commits on branch since it diverged from main
git log main..HEAD --oneline --format="%H %ai %s"

# Include files changed per commit (one file per line)
git log main..HEAD --name-only --format="COMMIT %H %ai %s"

# Compact: commit + author + timestamp + subject
git log main..HEAD --pretty=format:"%h %ad %an: %s" --date=short
```

**Why**: The `main..HEAD` range scopes to branch-only commits. Without this, full repo history creates noise that buries loop patterns.

### File change frequency across commits

```bash
# Count how many commits touched each file on this branch
git log main..HEAD --name-only --format="" | grep -v "^$" | sort | uniq -c | sort -rn

# Show which commits touched a specific file (loop investigation)
git log main..HEAD --follow --oneline -- path/to/file.go

# Show diffs for a specific file across all branch commits
git log main..HEAD -p -- path/to/file.go
```

### Detecting oscillating changes (strongest loop signal)

```bash
# Extract file content at two consecutive commits and diff them
git show HASH1:path/to/file.go > /tmp/version_a.txt
git show HASH2:path/to/file.go > /tmp/version_b.txt
diff /tmp/version_a.txt /tmp/version_b.txt

# Show net change between first and last commit on the file
# If net diff is tiny but there were many intermediate commits, it oscillated
git diff FIRST_HASH LAST_HASH -- path/to/file.go
```

---

## Loop Detection Queries

### Consecutive commit analysis

```bash
# List files changed per commit, oldest-first (prerequisite for consecutiveness check)
git log main..HEAD --reverse --name-only --format="=== %h %s" | grep -v "^$"

# Find files appearing 3+ times total across branch commits
git log main..HEAD --name-only --format="" | \
  grep -v "^$" | sort | uniq -c | sort -rn | awk '$1 >= 3'
```

**Note**: High frequency alone is not a loop. Check that appearances are consecutive, not distributed across many sessions.

### Commit message similarity

```bash
# Extract all commit messages on the branch
git log main..HEAD --format="%s"

# Find messages with retry/fix language
git log main..HEAD --format="%s" | \
  grep -iE "(fix|retry|attempt|again|revert|undo|restore)"

# Uniqueness ratio: low ratio = loop signal
echo "Total:  $(git log main..HEAD --format='%s' | wc -l)"
echo "Unique: $(git log main..HEAD --format='%s' | sort -u | wc -l)"
```

---

## Working Tree Inspection

### Uncommitted changes

```bash
# List all modified, staged, or untracked files
git status --short

# Show content of uncommitted modifications
git diff HEAD

# Porcelain output (machine-readable for scripting)
git status --porcelain
```

### Orphaned worktrees (git 2.5+)

```bash
# List all registered worktrees
git worktree list

# Check for prunable (stale) worktrees
git worktree list --porcelain | grep "prunable"

# Find .claude/worktrees/ session artifacts
ls -la .claude/worktrees/ 2>/dev/null || echo "No worktrees directory"
find .claude/worktrees/ -name "*.json" 2>/dev/null | head -20
```

### Plan file location

```bash
# Check all three standard plan locations
ls -la task_plan.md 2>/dev/null
ls -la .feature/state/plan/task_plan.md 2>/dev/null
ls -la plan/active/task_plan.md 2>/dev/null

# Search entire repo for plan files
find . -name "task_plan.md" -not -path "./.git/*"
```

---

## Timestamp Analysis

```bash
# Last commit timestamp (ISO format)
git log -1 --format="%ai"

# First commit on branch
git log main..HEAD --reverse --format="%ai" | head -1

# All commit timestamps (for average interval calculation)
git log main..HEAD --format="%ai"

# Total commit count on branch
git log main..HEAD --format="%H" | wc -l
```

---

## Credential Scrubbing Patterns

Before quoting any git output in a report, scan for credential-shaped strings:

```bash
# Scan commit messages and bodies for common credential patterns
git log main..HEAD --format="%s %b" | \
  grep -iE "(sk-|ghp_|token=|password=|secret=|key=|bearer )"

# Scan diff output for credentials in added/removed lines
git log main..HEAD -p | \
  grep -iE "^\+.*(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|password\s*=|secret\s*=)"
```

**Rule**: Deleted credentials (lines starting with `-`) must also be redacted — git history is the attack surface forensics is reading. Replace any match with `[REDACTED]`.

---

## Pattern Catalog
<!-- no-pair-required: section header introducing paired-pattern subsections below -->

### ❌ Scanning full repo history instead of branch scope

**Detection**:
```bash
git branch --show-current  # if "main" or "master", scope is wrong
```

**Why wrong**: `git log --oneline` without `main..HEAD` scoping shows all commits across all history. The stuck loop detector produces false positives on unrelated commits from other branches. Every loop detection query must be scoped to the branch under investigation.

**Fix**: Always use `git log main..HEAD` or `git log $(git merge-base HEAD main)..HEAD` when the default branch name is uncertain.

---

### ❌ Concluding loop from total frequency without checking consecutiveness

**Detection**:
<!-- no-pair-required: false positive - shell comment inside fenced code block; paired with Why wrong and Fix blocks below -->
```bash
# Generate per-commit file lists and manually inspect adjacency
git log main..HEAD --reverse --name-only --format="COMMIT %h" | \
  grep -E "(COMMIT|suspected-file\.go)"
```
<!-- no-pair-required: false positive - shell comment inside fenced code block; paired with Why wrong and Fix blocks below -->

**Why wrong**: A file touched 6 times across 60 commits is normal iterative development. Detector 1 confidence requires consecutive appearances, not just count. Reporting High confidence without consecutiveness check produces false positives that erode trust.

**Fix**: Map file appearances to commit positions. Only assign High confidence when 3+ consecutive commits all contain the same file.

---

## Error-Fix Mappings

| Investigation Blocker | Root Cause | Fix |
|----------------------|------------|-----|
| `fatal: no upstream configured` | Branch has no remote tracking branch | Use `git log $(git merge-base HEAD main)..HEAD` instead |
| Empty output from `git log main..HEAD` | Branch not yet diverged (zero commits) | Report "insufficient evidence — branch has no commits since divergence" |
| `git: 'worktree' is not a git command` | git < 2.5 | Worktree command requires git 2.5+; skip orphaned worktree check |
| Plan file not readable | File in gitignored or encrypted directory | Note access limitation in report; continue with git-only detectors |
| Binary output from `git log -p` | Committed binary file changed | Skip binary files in loop analysis; they cannot show oscillation |
| `ambiguous argument 'main'` | Branch named differently (e.g., `master`) | Run `git symbolic-ref refs/remotes/origin/HEAD` to find default branch |

---

## Detection Commands Reference

```bash
# Scoped branch history with file lists
git log main..HEAD --name-only --format="COMMIT %H %ai %s"

# File frequency (top loop candidates)
git log main..HEAD --name-only --format="" | grep -v "^$" | sort | uniq -c | sort -rn

# Retry/fix language in commit messages
git log main..HEAD --format="%s" | grep -iE "(fix|retry|attempt|again|revert)"

# Orphaned worktrees
git worktree list --porcelain | grep "prunable"

# Credential patterns in log output
git log main..HEAD --format="%s %b" | grep -iE "(sk-|ghp_|token=|password=|secret=)"
```
