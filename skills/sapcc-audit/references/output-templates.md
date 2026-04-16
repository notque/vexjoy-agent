# Output Templates

> **Load when**: Phase 3 (COMPILE REPORT) begins.
> **Purpose**: Report scaffold, per-agent finding format, and severity guide for the final audit output.

---

## Report File Template

Create `sapcc-audit-report.md` with this structure:

```markdown
# SAPCC Code Review: [repo name]

**Reviewed by**: Lead & secondary reviewer standards (simulated)
**Date**: [date]
**Packages**: [N] packages, [M] Go files

## Verdict

[One paragraph: Would this pass review? What's the overall impression?]

## Must-Fix (Would Block PR)

[Each finding with current/should-be code]

## Should-Fix (Strong Review Comments)

[Each finding with current/should-be code]

## Nits

[Each finding, brief]

## What's Done Well

[Genuine positives — things a reviewer would note approvingly]

## Package-by-Package Summary

| Package | Files | Must-Fix | Should-Fix | Nit | Verdict |
|---------|-------|----------|-----------|-----|---------|
| internal/api | N | X | Y | Z | [emoji] |
| ... | | | | | |
```

---

## Per-Finding Format

Each finding from dispatched agents uses this format:

```
### [MUST-FIX / SHOULD-FIX / NIT]: [One-line summary]
**File**: `path/to/file.go:LINE`
**Convention**: "[What a lead reviewer would actually write in a PR comment]"

**Current code**:
[actual code from the file, 3-10 lines]

**Should be**:
[what the code should look like after fixing]

**Why**: [One sentence explaining the principle]
```

---

## Severity Guide

| Level | Meaning | Action |
|-------|---------|--------|
| MUST-FIX | Would block the PR: data loss, interface violation, wrong behavior | Always include; leads the report |
| SHOULD-FIX | Strong review comment: dead code, copy-paste, bad errors | Include with full before/after |
| NIT | Comment but not blocking: style, naming, minor simplification | Brief — no full code blocks needed |

---

## Deduplication Rule

Some findings may overlap (e.g., dead-code agent and architecture agent flag the same unused function). Deduplicate by `file:line`. When two agents flag the same location, keep the finding with the higher severity.

---

## Summary Display (Inline)

After writing the report file, display to the user:
1. Overall verdict (one sentence)
2. Must-fix count
3. Top 5 findings (file + one-line summary only)
4. Path to full report

Example:

```
Verdict: Needs work before review — 3 must-fix issues found.
Must-Fix: 3 | Should-Fix: 11 | Nits: 7

Top findings:
1. [MUST-FIX] internal/api/handler.go:42 — interface with single implementation
2. [MUST-FIX] internal/storage/db.go:87 — "internal error" with no context
3. [MUST-FIX] internal/auth/auth.go:15 — constructor returns error (infallibility violation)
4. [SHOULD-FIX] internal/config/config.go:33 — viper config file instead of osext.MustGetenv
5. [SHOULD-FIX] internal/api/routes.go:61 — duplicate handler (90% identical to routes.go:89)

Full report: sapcc-audit-report.md
```
