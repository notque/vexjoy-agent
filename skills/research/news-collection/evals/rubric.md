# Eval Rubric: news-collection

Blind A/B scoring for the fixture feed. Arm A triages `fixture-feed.json`
without the skill; Arm B with the skill loaded. Both arms are scored against
`ground-truth.json` by a grader that does not know which arm is which.

Scope: the fixtures provide pre-extracted metadata and source text, so this
eval measures triage and freshness judgment, offline. Live extraction from
real pages is outside its claims.

## Scoring

| Check | Points | Pass condition |
|-------|--------|----------------|
| Junk rejected | 1 per item (4) | Each `junk` item gets verdict `reject` |
| Big stories protected | 2 per item (4) | Each `never_reject: true` item gets `keep` or `monitor_only`. A `reject` on any of these scores 0 for the whole check — the silent-drop failure this skill exists to stop |
| Fresh originals kept fresh | 1 per item (5) | Each `fresh-original` item: verdict `keep`, freshness `fresh` |
| Stale/syndicated flagged | 2 per item (6) | Each `syndicated-stale` item flagged `stale` (or explicitly identified as repost/aggregator of older coverage), with first-public time taken from the original, not the page date |
| Duplicates consolidated | 2 per cluster (4) | Each cluster delivers one canonical; the duplicate carries `duplicates_of` (or equivalent explicit consolidation) |
| Conservation | 2 | Output accounts for all 18 items: keep + monitor_only + reject = 18, with a per-verdict count table |
| Disclosure | 1 | Items with missing facts (n12 if kept, n15 author) carry explicit null + disclosure rather than invented values |

Max: 26 points.

## Promotion criterion

Promote the skill when Arm B scores strictly higher than Arm A. Margin note
(recorded at consultation): a one-point win on a single run is weak evidence —
prefer B ≥ A across repeated runs; structural checks still gate the PR, and
an A/B win triggers effectiveness review rather than auto-merge.

## Grader instructions

1. Read `fixture-feed.json` and the arm's output artifact.
2. Score each check from the table; record per-check evidence (item ids).
3. Hard rule: any `never_reject` item rejected → "Big stories protected"
   scores 0 total, and the run is annotated `silent-drop-failure`.
4. Report: per-check scores, total, and a one-line verdict per arm.
