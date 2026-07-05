# Planning Unknowns A/B — VERDICT (planning-unknowns-v1)

Date: 2026-07-03. Question: do 4 low-effort "Finding Your Unknowns" edits to
planning references (Deviations section + rule, reference-implementations
question, Blindspots subsection, volatile-first ordering) improve planning
outputs?

## Run mechanics

- Arms differ ONLY by reference-file text: `full` = main baseline
  (`.baseline-*.md`), `edited` = the 4 edits (+12 lines across
  plan-files.md, pre-plan.md, spec.md).
- 6 scenarios (2 plan-files, 3 pre-plan Discussion, 1 spec context-gathering),
  one sonnet generation per (arm, scenario) via `collect-answers.py`
  (12 calls, 0 fail).
- Blind pairwise judge: opus, random X/Y assignment per pair
  (`uid-map.json` withheld from judge), generic planning-quality rubric
  (decision coverage, execution resilience, grounding, sequencing, density).
  `judge.py`, `judgments.jsonl`.

## Results

| Metric | full (baseline) | edited (challenger) |
|---|---|---|
| Pairwise wins | 2 | 3 (+1 tie) |
| Score sum (0-10 × 6) | 43 | 45 |

Discordant pairs 5, McNemar p ≈ 0.38 — not significant. Edited wins on s4/s6
cite the Blindspots mechanism directly ("surfaces blindspots the requester
didn't ask about"); full wins on s1/s3 cite generation variance (grounding
detail, one security gray area), not edit-caused regressions.

## VERDICT: INCONCLUSIVE — NOT PROMOTE

Edited leads 3-2-1 but the sample (6 pairs) cannot clear the repo's promotion
bar (v2.1 precedent: CI excluding zero, McNemar p<0.05). Per merge gate, the
PR stays open unmerged. Path to resolution: rerun with 12+ scenarios
(pre-committed) or a paired multi-sample design; positive directional signal
and zero edit-attributed regressions justify the rerun.
