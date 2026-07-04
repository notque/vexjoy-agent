# Planning Unknowns A/B v2 — VERDICT (runs: planning-unknowns-v1 INCONCLUSIVE → v2 PROMOTE)

Date: 2026-07-03. Pre-committed rerun of v1 (which leaned edited 3-2-1,
p ≈ 0.38). Gates fixed in `GATES.md` before any v2 result.

## Run mechanics

- Same 4 edits, same arms: `full` = main baseline snapshots, `edited` = +12
  lines across plan-files.md, pre-plan.md, spec.md.
- 12 scenarios (v1's 6 + 6 new; 4 plan-files, 6 pre-plan, 2 spec) × 2
  independent sonnet samples per arm = 48 generations (0 fail).
- Blind judge: opus, one judgment per (scenario, sample) pair = 24, random
  X/Y order, uid map withheld, generic planning-quality rubric.

## Results

| Metric | full (baseline) | edited (challenger) |
|---|---|---|
| Pairwise wins | 6 | 18 (ties 0) |
| Score sum (0-10 × 24) | 166 | 180 |

Two-sided sign test on 24 discordant pairs: p = 0.0227.

## Gate check (per GATES.md)

- (a) p < 0.05 favoring edited: PASS (0.0227, 18-6).
- (b) No edit-attributed loss: PASS — all 6 full wins (s01a, s05b, s08a,
  s08b, s10a, s12a) credit the full arm's own content (extra decisions,
  grounding, sequencing); none cites edited-text bloat, confusion, or scope
  creep.
- (c) 0 collection failures, 24/24 judgments parsed: PASS.

Edited wins repeatedly cite the edits' mechanisms by name: blindspots the
requester didn't ask about (s04b, s06b, s09a/b, s12b), reference-code
grounding questions (s06b, s11a/b), deviation/rollback resilience (s07a/b).

## VERDICT: PROMOTE

Merge gate satisfied (with green Actions). Watch: planning outputs growing
past the 3-6 decision budget (Blindspots share it by rule). Rollback =
git revert of the reference edits; harness is rerunnable as-is.
