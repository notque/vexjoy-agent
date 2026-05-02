---
name: full-repo-review
description: "Comprehensive 3-wave review of all repo source files, producing a prioritized issue backlog."
user-invocable: true
command: full-repo-review
context: fork
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - Glob
  - Grep
routing:
  triggers:
    - full repo review
    - review entire repo
    - codebase health check
    - review all files
    - full codebase review
  pairs_with:
    - systematic-code-review
    - parallel-code-review
  complexity: Medium
  category: analysis
---

# Full-Repo Review: Codebase Health Check

Orchestrates a 3-wave review against ALL source files. Delegates actual review to `comprehensive-review`. Produces a prioritized issue backlog, not auto-fixes.

**When to use**: Quarterly health checks, after major refactors, onboarding to a new codebase. Expensive (all files through all waves) -- use `comprehensive-review` for PR-scoped work.

**Differs from comprehensive-review**: Scope phase scans all source files instead of git diff. Output is a prioritized backlog instead of auto-fix.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |

## Instructions

### Options

- **--directory [dir]**: Review single directory instead of full repo
- **--skip-precheck**: Skip `score-component.py` deterministic pre-check
- **--min-severity [level]**: Include only findings at or above threshold (CRITICAL, HIGH, MEDIUM). Default: all.

---

### Phase 1: DISCOVER AND PRE-CHECK

**Goal**: Identify all source files and run deterministic health checks.

**Step 1: Discover source files**

Always scan ALL source files -- never fall back to git diff. If `--directory` provided, scope to that directory.

```bash
# Python scripts (exclude test files and __pycache__)
find scripts/ -name "*.py" -not -path "*/tests/*" -not -path "*/__pycache__/*" 2>/dev/null

# Hooks (exclude test files and lib/)
find hooks/ -name "*.py" -not -path "*/tests/*" -not -path "*/lib/*" 2>/dev/null

# Skills (SKILL.md files only)
find skills/ -name "SKILL.md" 2>/dev/null

# Agents
find agents/ -name "*.md" 2>/dev/null

# Docs
find docs/ -name "*.md" 2>/dev/null
```

If zero files found, STOP: "No source files discovered. Verify you are in the correct repository root."

If too many files for a single session, split by directory rather than cherry-picking files.

**Step 2: Run deterministic pre-check**

```bash
python3 ~/.claude/scripts/score-component.py --all-agents --all-skills --json
```

Flag components scoring below 60 (grade F) as CRITICAL. Scores 60-74 (grade C) as HIGH. Save raw scores for report.

**GATE**: At least one source file discovered AND score-component.py ran. If scoring fails, proceed with warning.

---

### Phase 2: REVIEW

**Goal**: Run comprehensive-review pipeline against all discovered files.

**Step 1: Invoke comprehensive-review**

Overrides:
- **Scope**: Full file list from Phase 1 (`--focus [files]`)
- **Mode**: `--review-only` (backlog, not patches)
- **All waves**: Wave 0, 1, and 2 for maximum coverage

**Step 2: Collect findings**

Per finding: file (path + line), severity (CRITICAL/HIGH/MEDIUM/LOW), category, description, suggested fix.

**GATE**: comprehensive-review completed. If failed, include partial findings and note failure.

---

### Phase 3: REPORT

**Goal**: Aggregate findings into prioritized backlog.

**Step 1: Merge deterministic and LLM findings**

Combine Phase 1 scores and Phase 2 findings. Deduplicate, keep higher severity.

**Step 2: Identify systemic patterns**

Patterns appearing in 3+ files:
- Repeated naming violations
- Consistent missing error handling
- Common anti-patterns
- Documentation gaps following a pattern

These go into "Systemic Patterns" section -- highest-leverage fixes.

**Step 3: Write the report**

Write `full-repo-review-report.md` to repo root:

```markdown
# Full-Repo Review Report

**Date**: {date}
**Files reviewed**: {count}
**Total findings**: {count} (Critical: N, High: N, Medium: N, Low: N)

## Deterministic Health Scores

| Component | Score | Grade | Key Issues |
|-----------|-------|-------|------------|
| {name}    | {n}   | {A-F} | {summary}  |

## Critical (fix immediately)
- **{file}:{line}** : [{category}] {description}
  - Fix: {suggested fix}

## High (fix this sprint)
- ...

## Medium (fix when touching these files)
- ...

## Low (nice to have)
- ...

## Systemic Patterns
- **{pattern name}**: Seen in {N} files. {description}. Fix: {approach}.

## Review Metadata
- Waves executed: 0, 1, 2
- Duration: {time}
- Score pre-check: {pass/warn/fail}
```

Do not auto-apply fixes. User triages findings into manageable PRs.

**GATE**: Report exists at `full-repo-review-report.md` with severity sections and deterministic scores.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No source files found | Wrong directory or empty repo | Verify cwd is repo root with `ls agents/ skills/ scripts/` |
| score-component.py fails | Missing script or dependency | Proceed with warning; note gap in report |
| comprehensive-review times out | Too many files | Split into directory-scoped runs |
| Report write fails | Permission or path issue | Fallback: `/tmp/full-repo-review-report.md` |

---

## References

- [Report Template](references/report-template.md) -- Full structure for `full-repo-review-report.md`
