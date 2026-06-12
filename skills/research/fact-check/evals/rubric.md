# Blind A/B Rubric: fact-check

Maintenance artifact — load when evaluating or modifying the skill, not during ordinary execution.

## Setup

- **Arm A**: agent fact-checks each fixture article without the skill.
- **Arm B**: agent reads `SKILL.md` (and references on demand) first, then fact-checks.
- Both arms get the same prompt per fixture: "Fact-check `article.md` against the source documents in this directory. Report your findings per claim." Sources are the files in the fixture dir; the run is closed-book by design.
- Corpus is fixed: 6 fixtures, 32 ground-truth claims, 19 non-Verified claims of which 14 carry seeded errors of the four core types (fabricated-quote ×3, stale-stat ×3, misattribution ×3, unsupported-claim ×5) plus contradicted-fact ×2 and premature-result ×3.
- Run both arms for every fixture in the same session batch; anonymize outputs as Output 1 / Output 2 with arm assignment recorded separately before judging.

## Scoring — deterministic first

Label correctness is deterministic and is scored by matching, not by judge opinion (ground truth is fixed; opinion adds noise). For each arm, walk `ground-truth.json` claim by claim:

| Metric | Definition |
|--------|------------|
| **Catch** | A non-Verified ground-truth claim that the report flags as problematic (any non-Verified label or equivalent wording) |
| **Label match** | The report's label equals the ground-truth label (map free-text verdicts to the nearest of the four labels before comparing; an unmappable verdict counts as no match) |
| **False alarm** | A Verified ground-truth claim that the report flags as problematic |
| **Miss** | A non-Verified ground-truth claim the report treats as fine or omits |

Matching tolerance: claims are matched by content, not ID — an arm that merges or splits claims is scored against the ground-truth claims its text covers. A ground-truth claim the report does not mention at all is a Miss (if non-Verified) or neutral (if Verified).

Report per arm: catch rate (catches / 19), label accuracy (label matches / 32), false-alarm count, misses by seeded-error type.

## Scoring — blind judge second

The judge receives both anonymized reports plus ground-truth.json and scores only what is not deterministic:

1. **Evidence quality** (1–5): does each finding cite the exact source passage?
2. **Report usability** (1–5): verdict-first summary, Warnings section surfaces the serious findings, label meanings readable from the report alone.
3. Winner pick with reasoning.

The judge sees no indication of which output used the skill.

## Promotion bar

Promote (B wins) only when **both** hold:

1. B catches strictly more seeded errors than A (sum across the corpus), and
2. B's false-alarm count is less than or equal to A's.

Ties on catches, or any false-alarm regression, fail to promote — a noisier checker erodes trust in the gate faster than extra catches build it. Label accuracy and judge scores are reported as evidence on the PR but are tiebreakers only, never substitutes for the two conditions.

## Known validation limit

This corpus is closed-book: it exercises extraction, given-source verification, adjudication, and reporting. The open-web methods (lateral reading, source-tier climbing beyond provided files, live staleness re-checks) are outside what this A/B can confirm and are validated only through live use. State this limit wherever these results are cited.
