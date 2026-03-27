# Report Template

This file contains the full report template used in Phase 3 (AGGREGATE) and the severity boost table for cross-repository reinforcement.

---

## Severity Boost Table

Apply cross-repository reinforcement from §35 when prioritizing findings:

| Pattern Strength | Severity Boost |
|-----------------|----------------|
| NON-NEGOTIABLE (4+ repos) | +1 severity level (MEDIUM->HIGH) |
| Strong Signal (2-3 repos) | No change |
| Context-Specific (1 repo) | -1 severity level (HIGH->MEDIUM) |

---

## Report Template

Create `sapcc-review-report.md` using this structure:

```markdown
# SAPCC Code Review: [repo name]

**Module**: [go module path]
**Date**: [date]
**Packages reviewed**: [N] packages, [M] Go files, [T] test files
**Agents dispatched**: 10 domain specialists
**Reference version**: sapcc-code-patterns.md (comprehensive patterns reference, 36 sections)

---

## Verdict

[2-3 sentences: Would this codebase pass lead review? What are the systemic issues?
Not just "there are problems" — identify the PATTERN of problems.]

## Score Card

| Domain | Agent | Findings | Critical | High | Medium | Low |
|--------|-------|----------|----------|------|--------|-----|
| Signatures/Config | 1 | N | ... | ... | ... | ... |
| Types/Option[T] | 2 | N | ... | ... | ... | ... |
| HTTP/API | 3 | N | ... | ... | ... | ... |
| Error Handling | 4 | N | ... | ... | ... | ... |
| Database/SQL | 5 | N | ... | ... | ... | ... |
| Testing | 6 | N | ... | ... | ... | ... |
| Pkg Org/Imports | 7 | N | ... | ... | ... | ... |
| Modern Go/Stdlib | 8 | N | ... | ... | ... | ... |
| Observability/Jobs | 9 | N | ... | ... | ... | ... |
| Anti-Patterns/LLM | 10 | N | ... | ... | ... | ... |
| **TOTAL** | | **N** | **X** | **Y** | **Z** | **W** |

## Quick Wins (Easy Fixes, High Impact)

[5-10 findings that can be fixed with minimal effort]

## Critical Findings

[Each finding with full REJECTED/CORRECT code]

## High Findings

[Each finding with full REJECTED/CORRECT code]

## Medium Findings

[Each finding]

## Low Findings

[Brief list]

## What's Done Well

[Genuine positives the lead reviewer would note approvingly. This is important for morale
and to show the review isn't blindly negative.]

## Systemic Recommendations

[2-3 big-picture recommendations based on patterns across findings.
E.g., "This repo consistently uses *T for optionals — a bulk migration
to Option[T] would address 15 findings at once."]
```
