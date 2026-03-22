# Full-Repo Review Report Template

Use this template when generating `full-repo-review-report.md`.

---

```markdown
# Full-Repo Review Report

**Date**: YYYY-MM-DD
**Files reviewed**: N
**Total findings**: N (Critical: N, High: N, Medium: N, Low: N)

## Deterministic Health Scores

Scores from `score-component.py --all-agents --all-skills`.

| Component | Score | Grade | Key Issues |
|-----------|-------|-------|------------|
| example-agent | 85 | B | Missing CAN/CANNOT sections |

### Score Summary
- **A (90-100)**: N components
- **B (75-89)**: N components
- **C (60-74)**: N components -- listed as HIGH findings below
- **D/F (<60)**: N components -- listed as CRITICAL findings below

## Critical (fix immediately)

Security vulnerabilities, broken functionality, data loss risks.

- **{file}:{line}** -- [{category}] {description}
  - Fix: {suggested fix}
  - Source: {wave N agent / score-component.py}

## High (fix this sprint)

Significant quality issues, missing error handling, test gaps.

- **{file}:{line}** -- [{category}] {description}
  - Fix: {suggested fix}
  - Source: {wave N agent / score-component.py}

## Medium (fix when touching these files)

Style violations, naming drift, documentation gaps.

- **{file}:{line}** -- [{category}] {description}
  - Fix: {suggested fix}
  - Source: {wave N agent}

## Low (nice to have)

Minor improvements, optional enhancements.

- **{file}:{line}** -- [{category}] {description}
  - Fix: {suggested fix}
  - Source: {wave N agent}

## Systemic Patterns

Issues that appear across 3+ files. These are the highest-leverage fixes.

- **{pattern name}**: Seen in N files ({file1}, {file2}, ...). {description of the pattern}. Fix: {recommended approach}.

## Review Metadata

- **Waves executed**: 0, 1, 2
- **Duration**: N minutes
- **Score pre-check**: pass / warn (script failed, review continued) / fail
- **comprehensive-review version**: N.N.N
- **Files by type**: N scripts, N hooks, N skills, N agents, N docs
```
