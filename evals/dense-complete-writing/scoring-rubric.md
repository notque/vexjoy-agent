# Scoring Rubric: Dense-Complete Writing clause race

Two axes per output: a 20-point coverage rubric and a 0-100 dense-and-complete score. Both graded blind, dual-track (Claude + Codex), keys sealed until grading completes.

## Coverage rubric (20 points)

Each point scores 1 if the output states it, 0 if absent. Half-points allowed for partial coverage. Task: a `log-secret-auditor` SKILL.md.

| # | Required point |
|----|----------------|
| 1 | YAML frontmatter with name + description (+ triggers if used) |
| 2 | Explicit scope / when-to-use statement |
| 3 | Workflow placed first, immediately after frontmatter (workflow-first) |
| 4 | Phase decomposition (gather -> scan -> classify -> report) |
| 5 | Deterministic-vs-LLM split: regex scan scriptable, false-positive judgment is LLM |
| 6 | Concrete secret patterns: Authorization/Bearer, JWT, API keys, passwords, DB URLs, private keys, cookies, session IDs |
| 7 | Where to scan: log statements, logging config (formatters/handlers/filters), exception handlers, request/response logging middleware |
| 8 | Redaction-gap detection: full-header/full-body logging, missing redaction filter |
| 9 | Severity classification (critical/high/medium) |
| 10 | False-positive handling: test fixtures, placeholder values, fenced code blocks |
| 11 | Output/report format: count, file:line, redacted match, severity |
| 12 | Safety: never print raw secret values; redact as `<type:last4>` or similar |
| 13 | CI integration / exit codes (deterministic gate) |
| 14 | Remediation guidance: add redaction filter, structured logging, scrub fields |
| 15 | Rotation recommendation when a real leak is confirmed |
| 16 | Self-contained: scanning script lives inside the skill directory |
| 17 | Positive framing (instructions say what to do) |
| 18 | Worked example or concrete sample finding |
| 19 | Edge cases: rotating logs, multi-line tracebacks, third-party library logging |
| 20 | Honest limits / caveats of the audit |

## Dense-and-complete axis (0-100)

Rewards high coverage at low word count. An output that hits every coverage point in the fewest words scores highest. Padding to fill sections lowers the score; dropping a required point lowers it more.

| Band | Meaning |
|------|---------|
| 80-100 | Near-full coverage, tight wording, no filler. |
| 60-79 | Full coverage with some padding, or tight wording with a gap or two. |
| 40-59 | Noticeable padding or several coverage gaps. |
| 0-39 | Thin coverage or heavy filler. |

## Aggregation

1. Average each axis across both grader tracks.
2. Rank arms by dense-and-complete score; break ties by coverage, then by word count (fewer wins).
3. The control arm (bare five rules) is the baseline. A clause earns installation by beating control on the dense-and-complete axis at equal-or-higher coverage.

## Result

| aid | clause family | src | coverage | dense-complete | words |
|-----|---------------|-----|----------|----------------|-------|
| a06 (g07) | rule-of-thumb — content fixed, wording negotiable | codex | 16.0 | **83.5** | 1369 |
| a08 (g01) | definition | codex | 16.0 | 83.0 | 1588 |
| a10 (g09) | test | codex | 16.0 | 82.5 | 1467 |
| a11 (g06) | test | claude | 16.0 | 81.5 | 1374 |
| a04 (g00) | CONTROL (bare five rules) | — | 15.5 | 77.0 | 1909 |

**Winner: a06 (g07).** Top coverage at the fewest words. Installed as the Completeness clause.
