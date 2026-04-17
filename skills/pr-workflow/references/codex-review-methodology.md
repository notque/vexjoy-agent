# Code Review Methodology

> **Scope**: How to classify, filter, and synthesize Codex findings into a useful review report.
> **Version range**: All versions
> **Generated**: 2026-04-16

---

## Overview

The value of cross-model review is triangulation, not aggregation. Codex findings need the
same scrutiny as any automated tool — it can misread control flow, miss upstream handling,
or flag intentional patterns as errors. The methodology below ensures Claude adds context
rather than passing through Codex output verbatim.

---

## Finding Classification Table

| Codex Finding Type | Claude Action | Report Section |
|-------------------|---------------|----------------|
| Correct, properly scoped | Agree — include as-is | Critical Issues or Improvements |
| Directionally right, wrong severity | Agree with modification — adjust severity | Adjusted section |
| Correct finding, already handled elsewhere | Disagree — document reason | Filtered Findings |
| Hallucinated issue (misread logic) | Disagree — explain what Codex missed | Filtered Findings |
| Style preference marked as critical | Disagree — regrade to Improvements | Improvements (regraded) |
| Issue Claude found that Codex missed | Claude's own finding | Claude's Additional Observations |

---

## Severity Decision Tree

```
Is this issue reachable in production?
├── No → Improvements (not Critical)
└── Yes → Can it cause data loss, crash, or auth bypass?
    ├── Yes → Critical Issues
    └── No → Does it degrade performance measurably?
        ├── Yes → Improvements (performance)
        └── No → Positive Notes or style — not Critical
```

---

## Correct Patterns

### Verifying upstream handling before agreeing with a finding

Before marking a finding as "Agreed", check if the concern is already handled at the call site:

```bash
# If Codex flags missing error handling in function X, check callers
grep -rn "functionName(" --include="*.go" | head -20
# Read the call site to see if errors are caught upstream
```

**Why**: Codex sees functions in isolation. A missing `err` check in a helper may be
intentional if the caller always validates. Agreeing without checking creates noise.

### Making severity adjustments visible in the report

```markdown
### Improvements

**[CODEX: Critical — regraded to Improvement]** Missing nil check on `user.Profile`.
`Profile` is always set by `NewUser()` before this path is reached — the risk is real
but only in tests that bypass the constructor. Not production-blocking.
```

**Why**: Transparent reasoning lets the user disagree. Silent regrading looks like filtering
and erodes trust in the review.

### Surfacing what Codex missed

```markdown
### Claude's Additional Observations

**Error channel not drained**: `results` channel in `processItems()` is written but never
drained if the context is canceled — goroutine blocks forever. Codex reviewed the write
path only, not the consumer.

Detection:
```bash
rg 'chan.*results|results.*chan' --type go
```
```

---

## Anti-Pattern Catalog

### Passing through Codex output verbatim

**Detection**:
```bash
# Report is a copy of $TMPFILE if it contains Codex's exact headers unchanged
grep -c "## CRITICAL ISSUES\|## IMPROVEMENTS\|## POSITIVE NOTES" report.md
```

**Why wrong**: The entire value of cross-model review is Claude's assessment layer. Verbatim
pass-through means the user could have run `codex exec` themselves.

**Fix**: Every Codex finding must be explicitly classified (Agree/Agree-modified/Disagree)
with at least one sentence of Claude's reasoning before it appears in the report.

---

### Silently dropping disagreed findings

**What it looks like**: Codex flags 8 issues; report shows 4 with no explanation of the others.

**Why wrong**: Users who know Codex ran and see fewer findings reported will distrust the
filter. Opacity erodes confidence in the review process.

**Fix**: Always include a "Filtered Findings" section:
```markdown
### Filtered Findings

- **Unused variable `ctx`** (Codex: Critical): `ctx` is passed to `http.NewRequest` on
  the next line — Codex didn't follow the variable reference. Not a real issue.
- **Missing mutex lock** (Codex: Critical): This path is only reached from `ServeHTTP`
  which Go's HTTP server serializes per-connection. Concern doesn't apply here.
```

---

### Skipping assessment when output looks clean

**What it looks like**: Codex output has no CRITICAL issues, so Claude presents it directly.

**Why wrong**: Codex omission does not mean no issues exist. The most dangerous bugs are
ones the first reviewer missed. Claude must check for omissions, especially in security paths.

**Fix**: Always run the severity decision tree for each finding, including reviewing what
Codex's Positive Notes section affirms — confirm those patterns are actually correct.

---

## Error-Fix Mappings

| Scenario | Symptom | Recovery |
|----------|---------|----------|
| Codex output not in expected format | No `## CRITICAL ISSUES` headers | Extract findings manually; note unstructured output in report |
| Codex flags 0 issues | Empty CRITICAL section | Verify scope was right; check for Claude-found issues before reporting clean |
| Codex finding references wrong line | Line numbers don't match current file | Check if diff was applied; read current file version |
| Codex flags entire file vaguely | "This file needs restructuring" | Treat as Improvements; don't flag as Critical without specifics |

---

## Report Structure Template

```markdown
## Codex Code Review (GPT-5.4 xhigh)

**Scope**: {what was reviewed — e.g., "git diff main...HEAD (12 files, +340/-120 lines)"}
**Review date**: {date}

### Critical Issues
{Agreed critical findings with Claude's assessment note}

### Improvements
{Agreed suggestions, modified suggestions with Claude's severity-change reasoning}

### Positive Notes
{Confirmed good patterns — verify these are actually good, not just things Codex skipped}

### Filtered Findings
{Disagreed findings with reasoning — never omit this section if anything was filtered}

### Claude's Additional Observations
{Issues Claude found that Codex missed — omit section if none}

### Summary
{2-3 sentences: combined assessment, biggest risk, biggest strength, merge recommendation}
```

---

## Detection Commands Reference

```bash
# Verify Codex output file has content before processing
[ -s "$TMPFILE" ] && echo "has content" || echo "empty or missing"

# Count top-level sections in Codex output
grep -c "^##" "$TMPFILE"

# Find context clues that Codex may have missed (upstream handling)
grep -rn "if err\|recover()\|defer " --include="*.go" <path>

# Check for nil guards at call sites
grep -rn "!= nil\|== nil" --include="*.go" <path> | grep -i "profile\|user\|result"
```
