# Model task fit

Decision record for the `model` field in `build-dispatch.py` and every Agent call. Source: blind Jev eval, 2026-10. Skills `d` (Phase 5) and `do` (Step 2) carry the short table and link here.

## Setup

- 5 task types x 3 models (Opus 5.5, Sonnet 5.5, Haiku 5.5), 1 run per cell, in one TypeScript game repo.
- All 15 runs passed the hidden tests, the full suite, and `tsc`.
- Prices per Mtok in/out: Opus $4/$20, Sonnet $2/$10, Haiku $0.10/$0.50 up to a 100k prompt (5x above 100k).
- Candidates carried blind labels. Jev saw state text only, never model names.

## Results

Cost is Opus / Sonnet / Haiku per run.

| Task type | Cost O/S/H | Jev 0-3 scores | Jev Choice |
|---|---|---|---|
| locate (read-only lookup, cite lines) | $0.43 / $0.19 / $0.02 | all about 2.8-2.9, all right answer | haiku 0.91, sonnet 0.08, opus 0.01 |
| mech_edit (rename across 11 files) | $0.26 / $0.11 / $0.007 | identical 11 files, 32 hits, `tsc` clean | round 1 split haiku 0.48 / sonnet 0.52; with measured scope evidence haiku 0.93 |
| review (find planted bugs, round 1) | about $0.40 / $0.15 / $0.01 | Opus 4/4, Haiku 4/4, Sonnet 3/4 | haiku 0.95 (one run only) |
| deep_debug (root cause + regression test) | $0.39 / $0.20 / $0.015 | root cause 3.0 for all; regression test O 2.88, S 2.86, H 2.00 | sonnet 0.88, opus 0.10, haiku 0.02 |
| ts_feature (pattern feature + tests, 7 files) | $1.30 / $0.32 / $0.088 | Opus scope 1.82 (edited unrequested docs), Sonnet 2.95 | round 1 sonnet 0.59 / haiku 0.40; round 2 sonnet 0.64 / haiku 0.35 |
| long_lane (9-10 files, UI text, 89-135k prompt) | $1.66 / $0.46 / $0.25 | all player-facing level 2 after evidence fix; test Sonnet 2.97 | sonnet 0.77, haiku 0.21 |
| unmatched task | n/a | n/a | sonnet 0.54, haiku 0.45 (split after one sharpening; sonnet chosen as safer) |

Opus won no measured task.

## Tier choice

| Tier | Choice | Probability | Rationale |
|---|---|---|---|
| low-risk | haiku | 0.80 (opus 0.20) | Cheapest, matched quality on locate, mech_edit, review. |
| standard | sonnet | 0.90 | Won deep_debug, ts_feature, long_lane; safer default for unmatched work. |
| high-risk | opus | 1.00 | Unmeasured, and a miss is costly. Opus is the paid-for insurance, not a measured winner. |

`build-dispatch.py` maps `model_policy` low-risk / standard / high-risk to haiku/low, sonnet/medium, opus/high. `max-power` stays opus/xhigh and needs `manual_model_override=true`.

## Escalate on a miss

Order: haiku, sonnet, opus. Retry once on the next model when either holds:

- an objective check fails (tests, `tsc`, `ruff`, acceptance command);
- a Jev blocker Noul ("anything worse or blocking") is at least 0.6.

Do not retry the same model. Do not skip a tier unless the task is high-risk.

## Evidence limits

- One repo (TypeScript game), one run per cell. Variance across runs is unmeasured.
- The review row is n=1 (Sonnet's 3/4 may be noise).
- ts_feature stayed near a split (sonnet 0.59/0.64); treat it as a soft preference.
- Prompts above 100k tokens cost 5x on Haiku; long_lane Haiku ($0.25) sits near that edge.
- Costs are single-run dollars, not averages.

## Lesson: fix evidence before blaming the model

A split long_lane score came from a truncated diff in the state, which hid files from the judge. Restoring the full diff resolved the split: all three scored level 2 on player-facing text. When a score splits, check whether the state shows what a user would see before concluding the models differ.

## Jev as a map

Jev is the map; the table above is the current position. Re-measure with the judge/decide method.

### Re-measure

1. Run the same task on each candidate model. Record cost and objective checks (tests, `tsc`, scope of files touched).
2. Label candidates blind (A/B/C). Keep model names out of the state.
3. Judge test diffs separately from source diffs. Ask one judgment per question: root cause, regression test, scope, player-facing text, each its own Score or Noul.
4. Add the measured numbers to the state: cost, files touched, hit counts. Pair every Jev judgment with one.
5. Split the request so each stays at or under 3.5k tokens; send independent questions together.
6. Ask the Choice: which model for this task type, with `what`, `not_for`, `examples` per option.
7. On a split (0.4-0.6 Noul, or near-even Choice), fix the evidence first (full diffs, measured scope), then re-ask. Re-asking unchanged evidence is fishing.

Keep bar for a changed row: `better` at least 0.7, `worse` below 0.4, no measured guard broken.

### Change a row

Change a table row only on a decisive Choice from new evidence (one option at or above 0.7 and the top-2 margin clear). A single run, a split, or a price change alone does not change a row. Log the old row, new row, probabilities, and evidence in this file.

### Destination ladder

Goal: model routing that follows evidence. Baseline: level 0 (Jev 0.99 at level 0).

| Level | Summary | Signals |
|---|---|---|
| 0 | No evidence-based routing | Skills are silent on model. All tiers map to opus. `haiku` is not accepted by the dispatcher. |
| 1 | Guidance exists but is opinion or unenforced | A model note exists with no measured table. Dispatcher or tests do not pin it. |
| 2 | Measured guidance, enforced by default | Table in `d` and `do`. Dispatcher accepts haiku and maps tiers. Tests pin the mapping. Owner policy updated. |
| 3 | Measured, enforced, self-correcting | Level 2, plus escalate-on-miss naming the next model, evidence limits stated, re-measure loop documented, ruff and tests pass, PR merged green. |

Target: level 3. Re-score the ladder after any row change.
