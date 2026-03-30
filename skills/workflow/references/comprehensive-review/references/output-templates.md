# Output Templates

## Findings Summary Matrix

Used during Wave 0+1+2 aggregate (Phase 3b) and final aggregate (Phase 3d):

```
| Agent                    | Wave | CRITICAL | HIGH | MEDIUM | LOW |
|--------------------------|------|----------|------|--------|-----|
| Per-Package: [pkg1]      | 0    | N        | N    | N      | N   |
| Per-Package: [pkg2]      | 0    | N        | N    | N      | N   |
| Per-Package: [...]       | 0    | N        | N    | N      | N   |
| **Wave 0 Subtotal**      | **0**| **N**    | **N**| **N**  | **N**|
| Security                 | 1    | N        | N    | N      | N   |
| Business Logic           | 1    | N        | N    | N      | N   |
| Architecture             | 1    | N        | N    | N      | N   |
| Silent Failures          | 1    | N        | N    | N      | N   |
| Test Coverage            | 1    | N        | N    | N      | N   |
| Type Design              | 1    | N        | N    | N      | N   |
| Code Quality             | 1    | N        | N    | N      | N   |
| Comment Analyzer         | 1    | N        | N    | N      | N   |
| Language Specialist      | 1    | N        | N    | N      | N   |
| Docs & Config            | 1    | N        | N    | N      | N   |
| ADR Compliance           | 1    | N        | N    | N      | N   |
| Newcomer                 | 1    | N        | N    | N      | N   |
| **Wave 1 Subtotal**      | **1**| **N**    | **N**| **N**  | **N**|
| Performance              | 2    | N        | N    | N      | N   |
| Concurrency              | 2    | N        | N    | N      | N   |
| API Contract             | 2    | N        | N    | N      | N   |
| Dependency Audit         | 2    | N        | N    | N      | N   |
| Error Messages           | 2    | N        | N    | N      | N   |
| Dead Code                | 2    | N        | N    | N      | N   |
| Naming Consistency       | 2    | N        | N    | N      | N   |
| Observability            | 2    | N        | N    | N      | N   |
| Config Safety            | 2    | N        | N    | N      | N   |
| Migration Safety         | 2    | N        | N    | N      | N   |
| **Wave 2 Subtotal**      | **2**| **N**    | **N**| **N**  | **N**|
| Contrarian               | 3    | — challenges — | — | — | — |
| Skeptical Senior         | 3    | — challenges — | — | — | — |
| User Advocate            | 3    | — challenges — | — | — | — |
| Meta-Process             | 3    | — challenges — | — | — | — |
| SAPCC Structural         | 3    | — challenges — | — | — | — |
| **Wave 3 Summary**       | **3**| **N agreed** | **N challenged** | **N downgraded** | **N dismissed** |
| **TOTAL (post-Wave 3)**  |      | **N**    | **N**| **N**  | **N**|
```

Wave Agreement Summary (append after matrix):

```
| Agreement Level | Count | Action |
|-----------------|-------|--------|
| UNANIMOUS       | N     | Fix immediately — high confidence |
| MAJORITY        | N     | Fix, note challenge in report |
| CONTESTED       | N     | Needs human judgment — present both sides |
```

## Final Report Template

Write to `comprehensive-review-report.md`:

```markdown
# Comprehensive Code Review Report v4

**Date**: [date]
**Files reviewed**: [N]
**Packages discovered**: [N]
**Agents dispatched**: [N] (Wave 0: [N per-package], Wave 1: 12, Wave 2: 10, Wave 3: [4-5 adversarial])
**Total findings**: [N]
**Findings fixed**: [N]
**Findings blocked**: [N] (ONLY if fix breaks tests after alternative attempt — must be <10%)

---

## Verdict: [CLEAN | ALL_FIXED | BLOCKED_ITEMS]

- CLEAN: No findings (rare)
- ALL_FIXED: Every finding was fixed (expected outcome)
- BLOCKED_ITEMS: Some fixes break tests even after alternative attempts (<10%)

[2-3 sentences: Overall assessment. What systemic patterns emerged?
Is the codebase better after fixes?]

## Wave Summary

| Wave | Agents | Findings | Fixed | Unique to Wave |
|------|--------|----------|-------|----------------|
| Wave 0 (Per-Package) | N | N | N | N |
| Wave 1 (Foundation) | 12 | N | N | N |
| Wave 2 (Deep-Dive) | 10 | N | N | N |
| Wave 3 (Adversarial) | N | — | — | N challenges |
| **TOTAL** | **N** | **N** | **N** | |

## Wave Agreement Analysis

| Agreement Level | Count | Fixed | Skipped | Human Decided |
|-----------------|-------|-------|---------|---------------|
| UNANIMOUS       | N     | N     | —       | —             |
| MAJORITY        | N     | N     | —       | —             |
| CONTESTED       | N     | N     | N       | N             |

## Wave 0: Per-Package Results

| Package | Health | Files | Findings | Key Issue |
|---------|--------|-------|----------|-----------|
| [pkg/path1] | HEALTHY | N | N | — |
| [pkg/path2] | NEEDS_ATTENTION | N | N | [biggest] |
| ... | ... | ... | ... | ... |

**Cross-Package Patterns**: [List of patterns seen across multiple packages]

## Agent Summary

| Agent | Wave | Findings | Fixed | Blocked | Key Issue |
|-------|------|----------|-------|---------|-----------|
| Per-Package (total) | 0 | N | N | N | [biggest] |
| Security | 1 | N | N | N | [biggest] |
| Business Logic | 1 | N | N | N | [biggest] |
| Architecture | 1 | N | N | N | [biggest] |
| Silent Failures | 1 | N | N | N | [biggest] |
| Test Coverage | 1 | N | N | N | [biggest] |
| Type Design | 1 | N | N | N | [biggest] |
| Code Quality | 1 | N | N | N | [biggest] |
| Comment Analyzer | 1 | N | N | N | [biggest] |
| Language Specialist | 1 | N | N | N | [biggest] |
| Docs & Config | 1 | N | N | N | [biggest] |
| ADR Compliance | 1 | N | N | N | [biggest] |
| Newcomer | 1 | N | N | N | [biggest] |
| Performance | 2 | N | N | N | [biggest] |
| Concurrency | 2 | N | N | N | [biggest] |
| API Contract | 2 | N | N | N | [biggest] |
| Dependency Audit | 2 | N | N | N | [biggest] |
| Error Messages | 2 | N | N | N | [biggest] |
| Dead Code | 2 | N | N | N | [biggest] |
| Naming Consistency | 2 | N | N | N | [biggest] |
| Observability | 2 | N | N | N | [biggest] |
| Config Safety | 2 | N | N | N | [biggest] |
| Migration Safety | 2 | N | N | N | [biggest] |
| Contrarian | 3 | — | — | — | [key challenge] |
| Skeptical Senior | 3 | — | — | — | [key challenge] |
| User Advocate | 3 | — | — | — | [key challenge] |
| Meta-Process | 3 | — | — | — | [key challenge] |
| SAPCC Structural | 3 | — | — | — | [key challenge or N/A] |
| **TOTAL** | | **N** | **N** | **N** | |

## Context Cascade Effectiveness

How each wave's context helped later waves find deeper issues:

| Wave 2 Agent | Wave 0 Context Used | Wave 1 Context Used | Additional Findings Due to Context |
|-------------|--------------------|--------------------|-------------------------------------|
| Performance | Package complexity hotspots | Architecture hot paths | [N findings] |
| Concurrency | Intra-package concurrent patterns | Silent failures + arch | [N findings] |
| ... | ... | ... | ... |

### Wave 3 Challenge Effectiveness

How adversarial review changed the final outcome:

| Wave 3 Agent | Findings Challenged | Downgraded | Dismissed | Key Insight |
|-------------|--------------------|-----------|-----------|----|
| Contrarian | N | N | N | [biggest challenge] |
| Skeptical Senior | N | N | N | [biggest challenge] |
| User Advocate | N | N | N | [biggest challenge] |
| Meta-Process | N | N | N | [biggest challenge] |
| SAPCC Structural | N or N/A | N | N | [biggest challenge or N/A] |

## Findings by Severity

### CRITICAL
[Each finding with before/after code]

### HIGH
[Each finding with before/after code]

### MEDIUM
[Summary with file references]

### LOW
[Brief list]

## Contested Findings (Wave 3 vs Wave 1+2)

| Finding | Wave 1+2 Severity | Wave 3 Verdict | Resolution |
|---------|-------------------|----------------|------------|
| [summary] | HIGH | CHALLENGE: [reason] | [Fixed / Skipped / Human decided] |
| ... | ... | ... | ... |

## Quick Wins Applied
[List of easy fixes that improved quality]

## Blocked Items (if any — must be <10% of total)
[List of findings where fix AND alternative fix both break tests]
[Each must include: what was tried, why it failed, suggested manual approach]

## What's Done Well
[Genuine positives found during review]

## Systemic Recommendations
[2-3 big-picture patterns observed across findings]
```

## task_plan.md Template

Created at the start of Phase 1:

```markdown
# Task Plan: Comprehensive Review v4

## Goal
Four-wave review and auto-fix of [N] changed files across [N] packages.

## Phases
- [ ] Phase 0.5: Static Analysis (linters, auto-fix trivial, capture remaining)
- [ ] Phase 1: Scope (identify files, detect org, discover packages, create findings dir)
- [ ] Phase 1b: Wave 0 Dispatch (per-package deep review)
- [ ] Phase 1c: Wave 0 Aggregate (per-package findings)
- [ ] Phase 1.5: Library Contract Verification (Go repos only)
- [ ] Phase 2a: Wave 1 Dispatch (12 foundation agents + Wave 0 context)
- [ ] Phase 2b: Wave 1 Aggregate (collect and summarize Wave 0+1 findings)
- [ ] Phase 3a: Wave 2 Dispatch (10 deep-dive agents with Wave 0+1 context)
- [ ] Phase 3b: Wave 2 Aggregate (merge Wave 0+1+2 findings)
- [ ] Phase 3c: Wave 3 Dispatch (4-5 adversarial agents with Wave 0+1+2 context)
- [ ] Phase 3d: Wave 3 Aggregate (merge adversarial challenges, label agreement)
- [ ] Phase 4: Fix (auto-fix on branch)
- [ ] Phase 5: Report (write report, verify)

## Review Profile
- Files: [list]
- Packages discovered: [N]
- Wave 0 agents: [N] (one per package)
- Wave 1 agents: 12
- Wave 2 agents: 10
- Wave 3 agents: 4-5 (adversarial; 5 if SAPCC detected)
- Org conventions: [detected org or none]
- Mode: [review+fix | review-only]

## Findings Directory
$REVIEW_DIR = [path from Phase 1 Step 3]

## Status
**Currently in Phase 1** - Discovering packages
```

## Findings Directory Layout

```
$REVIEW_DIR/
  wave0-findings.md   — Per-package deep review results
  wave1-findings.md   — Foundation agent results (12 agents)
  wave01-summary.md   — Combined Wave 0+1 context for Wave 2
  wave2-findings.md   — Deep-dive agent results (10 agents)
  wave012-summary.md  — Combined Wave 0+1+2 context for Wave 3
  wave3-findings.md   — Adversarial challenge results (4-5 agents)
  final-report.md     — Aggregated, deduplicated, agreement-labeled
```

| File | Written By | Read By |
|------|-----------|---------|
| `$REVIEW_DIR/wave0-findings.md` | Phase 1c | Phase 2a, 2b |
| `$REVIEW_DIR/wave1-findings.md` | Phase 2b | Phase 3a |
| `$REVIEW_DIR/wave01-summary.md` | Phase 2b | Phase 3a |
| `$REVIEW_DIR/wave2-findings.md` | Phase 3b | Phase 3c |
| `$REVIEW_DIR/wave012-summary.md` | Phase 3b | Phase 3c |
| `$REVIEW_DIR/wave3-findings.md` | Phase 3d | Phase 4 |
| `$REVIEW_DIR/final-report.md` | Phase 3d | Phase 4, Phase 5 |

These files persist in `/tmp/` until next reboot and can be re-read in future sessions if needed.
