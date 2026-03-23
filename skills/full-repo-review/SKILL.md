---
name: full-repo-review
description: >
  Run comprehensive 3-wave review against all source files in the repo,
  producing a prioritized issue backlog. Use for "full repo review",
  "review entire repo", "codebase health check", "review all files",
  "full codebase review". Do NOT use for PR-scoped reviews (use
  comprehensive-review) or single-concern reviews (use individual agents).
version: 1.0.0
user-invocable: true
command: full-repo-review
context: fork
model: opus
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
    - comprehensive-review
  complexity: Medium
  category: analysis
---

# Full-Repo Review : Codebase Health Check

Orchestrates a comprehensive 3-wave review against ALL source files in the
repository, not just changed files. Delegates the actual review to the
`comprehensive-review` skill. Produces a prioritized issue backlog instead of
auto-fixes.

**When to use**: Quarterly health checks, after major refactors, onboarding to
a new codebase, or any time you want a systemic view of codebase quality.

**How it differs from comprehensive-review**: This skill changes the SCOPE
phase to scan all source files instead of git diff, and changes the output from
auto-fix to a prioritized backlog report. The review waves themselves are
identical.

---

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **Full-Scope, Not Diff-Scope**: Always review ALL source files. Never fall back to git diff. The entire point of this skill is codebase-wide coverage.
- **Report, Don't Auto-Fix**: Output is a prioritized backlog (`full-repo-review-report.md`), not auto-applied fixes. Full-repo auto-fix is impractical and risky -- the user triages and batches fixes.
- **Deterministic Pre-Check First**: Run `score-component.py` before the LLM review. Deterministic checks are cheap and catch structural issues (missing frontmatter, no error handling section) that LLM reviewers shouldn't waste tokens on.
- **Delegate to comprehensive-review**: This skill orchestrates scope and output. The actual 3-wave review is performed by `comprehensive-review` with `--review-only` mode.

### Default Behaviors (ON unless disabled)
- **Score Pre-Check**: Run `score-component.py --all-agents --all-skills` and include scores in the report
- **Severity Aggregation**: Group findings by CRITICAL/HIGH/MEDIUM/LOW
- **Systemic Pattern Detection**: Identify patterns that appear across multiple files/directories
- **Report Artifact**: Write `full-repo-review-report.md` to repo root

### Optional Behaviors (OFF unless enabled)
- **--directory [dir]**: Review only a single directory (e.g., `scripts/`) instead of the full repo. Useful for splitting a large repo into manageable chunks.
- **--skip-precheck**: Skip the `score-component.py` deterministic pre-check. Only use if the script is unavailable or you need faster iteration.
- **--min-severity [level]**: Only include findings at or above a severity threshold (CRITICAL, HIGH, MEDIUM) in the report. Default: include all.

---

## Capabilities

### What This Skill CAN Do
- Discover all source files across scripts/, hooks/, skills/, agents/, docs/
- Run deterministic health scoring on all agents and skills via `score-component.py`
- Invoke comprehensive-review in `--review-only` mode with the full file list
- Aggregate findings by severity into a prioritized backlog report
- Identify systemic patterns that appear across multiple files

### What This Skill CANNOT Do
- Auto-fix findings (by design -- output is a report for human triage)
- Review non-source files (images, binaries, config files without .py/.md extension)
- Replace PR-scoped comprehensive-review (different use case, different frequency)
- Run individual review agents directly (delegates to comprehensive-review for wave orchestration)

---

## Instructions

### Phase 1: DISCOVER AND PRE-CHECK

**Goal**: Identify all source files and run deterministic health checks.

**Step 1: Discover source files**

Build the complete file list by scanning these directories:

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

Log the total file count. If zero files found, STOP and report: "No source files discovered. Verify you are in the correct repository root."

**Step 2: Run deterministic pre-check**

```bash
python3 ~/.claude/scripts/score-component.py --all-agents --all-skills --json
```

Parse the JSON output. Flag any component scoring below 60 (grade F) as a
CRITICAL finding for the final report. Components scoring 60-74 (grade C) are
HIGH findings.

Save the raw scores -- they go into the report's "Deterministic Health Scores"
section.

**GATE**: At least one source file discovered AND score-component.py ran
successfully. If the scoring script fails, proceed with a warning but do not
skip the review phase.

---

### Phase 2: REVIEW

**Goal**: Run the comprehensive-review pipeline against all discovered files.

**Step 1: Invoke comprehensive-review**

Invoke the `comprehensive-review` skill with these overrides:
- **Scope**: Pass the full file list from Phase 1 (use `--focus [files]` mode)
- **Mode**: Use `--review-only` to skip auto-fix (this skill produces a report, not patches)
- **All waves**: Do NOT use `--skip-wave0` or `--wave1-only`. Full-repo review needs maximum coverage.

The comprehensive-review skill handles Wave 0 (per-package), Wave 1 (foundation agents), and Wave 2 (deep-dive agents) internally.

**Step 2: Collect findings**

After comprehensive-review completes, gather all findings from its output. Each finding should have:
- **File**: path and line number
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **Category**: security, architecture, dead-code, naming, etc.
- **Description**: what the issue is
- **Suggested fix**: how to resolve it

**GATE**: comprehensive-review completed and produced findings output. If it
failed, include what partial findings exist and note the failure in the report.

---

### Phase 3: REPORT

**Goal**: Aggregate all findings into a prioritized backlog report.

**Step 1: Merge deterministic and LLM findings**

Combine:
- Phase 1 score-component.py results (structural health)
- Phase 2 comprehensive-review findings (deep analysis)

Deduplicate where both sources flag the same issue. Keep the higher severity.

**Step 2: Identify systemic patterns**

Look for patterns that appear in 3+ files:
- Repeated naming violations
- Consistent missing error handling
- Common anti-patterns across components
- Documentation gaps that follow a pattern

These go into a dedicated "Systemic Patterns" section -- they represent the
highest-leverage fixes because one pattern change improves many files.

**Step 3: Write the report**

Write `full-repo-review-report.md` to the repo root with this structure:

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

**GATE**: Report file exists at `full-repo-review-report.md` and contains at
least the severity sections and deterministic scores.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No source files found | Wrong working directory or empty repo | Verify cwd is repo root with `ls agents/ skills/ scripts/` |
| score-component.py fails | Missing script or dependency | Proceed with warning; the LLM review still runs. Note gap in report. |
| comprehensive-review times out | Too many files for single session | Split into directory-scoped runs: scripts/, hooks/, agents/, skills/ separately |
| Report write fails | Permission or path issue | Try writing to `/tmp/full-repo-review-report.md` as fallback |

---

## Anti-Patterns

### Do NOT auto-fix findings
**Why**: Full-repo auto-fix touches too many files at once. Risk of cascading
breakage is high and review of the fixes themselves would be a massive PR.
Report findings for human triage.

### Do NOT skip the deterministic pre-check
**Why**: score-component.py catches structural issues (missing YAML fields,
no error handling section) cheaply. Skipping it wastes LLM tokens on issues
a script can find in milliseconds.

### Do NOT run on every PR
**Why**: This is expensive (all files through all waves). Use
comprehensive-review for PR-scoped work. This skill is for periodic health
checks.

---

## Anti-Rationalization

| Rationalization | Why Wrong | Required Action |
|-----------------|-----------|-----------------|
| "Too many files, let's just review the important ones" | Cherry-picking defeats the purpose of full-repo review | Review ALL discovered files. If it's too large, split by directory -- don't skip. |
| "The score pre-check already found the issues" | Deterministic checks catch structure, not logic | Always run the full 3-wave review after pre-check |
| "We can auto-fix the obvious ones" | This skill produces a report, not patches | Write findings to the report. User decides what to fix and when. |
| "Wave 0 is slow, let's skip it" | Wave 0 per-package context is what makes full-repo review valuable | Run all three waves. No shortcuts on coverage. |

---

## References

- [Report Template](references/report-template.md) -- Full structure for `full-repo-review-report.md` output
