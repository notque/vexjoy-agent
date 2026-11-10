# Model task fit

Decision record for the `model` field in `build-dispatch.py` and every Agent call. Skills `d` (Model choice) and `do` (Step 2) carry the short table and link here.

## Current policy (2026-11-09)

Sources: Anthropic, "Which Claude model should you build with?" (2026-11-09), the owner override of 2026-11-01, and the owner order of 2026-11-09. Where they differ, the owner wins.

Owner (notque), verbatim, 2026-11-09: "Also I prefer opus 5.5 medium over high". Opus runs at medium on every row and tier, high-risk included.

### Task rows

| Task | Model / effort |
|---|---|
| Read-only gathering: locate, lookup, cite lines, excerpts, research fetch, log reading | haiku |
| Code writing and edits, debugging, features, reviews that decide, decisions, no row fits | opus / medium, then high |
| High-risk: auth, data, security, concurrency, irreversible | opus / medium, then high |
| Major refactor or migration, architecture planning, lead of a many-agent fan-out, deep research synthesis, quantitative analysis, long unattended run, or Opus at high fell short | fable / medium, then high |

Sonnet is no row's default.

### Tiers (`model_policy` in `build-dispatch.py`)

| Tier | Model / effort | Was (2026-11-01) |
|---|---|---|
| low-risk | haiku / low (read-only gathering only) | haiku / low |
| standard | opus / medium | opus / high |
| high-risk | opus / medium | opus / high |
| max-power | fable / high, needs `manual_model_override=true` | opus / xhigh |

- opus/high is no tier's default. It stays valid as an explicit pick (`model: "opus"`, `model_effort: "high"`, no `model_policy`) and as the escalation step after a failed opus/medium attempt. A named tier with `model_effort: "high"` needs `manual_model_override=true`.
- `fable` is accepted wherever `opus` is. An explicit `model: "fable"` needs no override unless it differs from a named `model_policy` tier, the same rule as opus.
- fable/max and opus/max need `manual_model_override=true`. So does an explicit opus/xhigh: test fable at high first.
- Owner per-task override: when the owner names a model for the task ("use fable for everything"), every dispatch passes that model, and the builder accepts and records it.

### Escalate on a miss

Retry when an objective check fails (tests, `tsc`, `ruff`, acceptance command) or a Jev blocker Noul ("anything worse or blocking") is at least 0.6. In order:

1. Give the agent a way to verify its work: a test, build, or script.
2. Raise effort one level, up to high.
3. Move to the next model up, at a lower effort than the smaller model used: haiku → opus/medium → opus/high → fable/medium → fable/high.

Never raise opus past high before trying fable. Effort cannot add knowledge or skill a model lacks.

### What Anthropic suggests

Lineup: Haiku 5.5, Sonnet 5.5, Opus 5.5, Fable 5.2. Start most work on Opus 5.5 at medium effort. Adjust effort before changing model.

| Task | Starting model | Starting effort |
|---|---|---|
| Everyday engineering, debugging, multi-PR feature work | Opus 5.5 | medium, then high |
| Classification, routing, tagging, high-volume extraction | Haiku 5.5 | medium |
| Subagents that search files, read logs, summarize | Haiku 5.5 or Sonnet 5.5 | model default |
| Chat, interactive | Sonnet 5.5 (Haiku for simple chat at volume) | low or medium |
| Well-scoped coding: bug fixes, feature iteration, spec-driven | Sonnet 5.5 | medium, then high |
| Everyday documents, slides, spreadsheets | Sonnet 5.5 (Opus for a complex financial model or large source pile) | high (medium in Claude Code) |
| Repeated agent tasks: investigation, review, drafting | Sonnet 5.5 | medium |
| Computer use, vision-heavy | Opus 5.5 | medium |
| Major refactors and migrations, architecture planning, leading many subagents | Fable 5.2 | medium, then high |
| Deep research, scientific or quantitative analysis | Fable 5.2 | medium, then high |
| Not sure | Opus 5.5 | medium |

The Sonnet rows are Anthropic's suggestion. The owner's experience supersedes them for code, edits, and decisions: Sonnet code work needed redo. The guide itself says to keep edits and judgment on the main model and to measure on your own work. Re-measure with the loop under "Jev as a map" before changing a row.

### Prices (per Mtok)

| Model | Input | Output | Cache read |
|---|---|---|---|
| Haiku 5.5, prompt up to 100K tokens | $0.10 | $0.50 | $0.01 |
| Haiku 5.5, prompt over 100K tokens | $0.50 | $2.50 | $0.05 |
| Sonnet 5.5 | $2 | $10 | $0.10 |
| Opus 5.5 | $4 | $20 | $0.20 |
| Fable 5.2 | $8 | $40 | $0.20 |

All four: 1M context, 128K max output, default effort medium in Claude Code. Fast mode: Opus and Fable only.

### Effort trade-offs

- Opus 5.5 on SWE-bench Pro, against high: medium scores about 2.5 points lower at about 70% of the cost; low about 8 points lower at about a third of the cost; xhigh about 1.4 points higher at 2.5x the cost.
- FrontierCode 2.0: Fable 5.2 at high scores 45.3, Opus 5.5 at max 45.5, at about half the cost per task. Past high, one more effort level can cost as much as a bigger model.
- When a check can grade the outcome, run everything at low and re-run only the failures at high. Opus low plus failures at high: about 97% pass at $0.17 per task, against 95.3% at $0.29 for all-high.
- A lean main context matters more the bigger the main model. Let cheaper subagents do the verbose reading. Small models suit high-volume checkable work, not long agentic loops.

### Mixing models

- Switch models at a natural break: `/compact`, or a fresh session with a short plan. The first turn on a new model pays a cache write on the whole conversation.
- Moving down a tier drops earlier thinking blocks. Moving from Fable 5.2 to any other model drops its reasoning.
- Keep small-model subagents on work where a mistake is cheap to spot: find files, run tests, read logs. Keep code edits and judgment calls on the main model.
- `CLAUDE_CODE_SUBAGENT_MODEL` sets the model for subagents that name none. The built-in Explore subagent runs on the session model, so pass `model: "haiku"` to keep exploration cheap. The `haiku` alias is Haiku 5.5 from Claude Code v2.1.293.
- `opusplan` plans on Opus and edits on Sonnet, the reverse of this policy. Do not default to it.
- Advisor tool: none of four pairings clearly beat the executor alone. Measure the consult rate first.
- A lead with cheaper workers pays for work larger than one context window (Opus lead plus up to 25 Sonnet workers: about a third cheaper at the same score on a 22M-token defect search). Skip it for one chain of dependent steps, or for work that fits one context.
- When the routing rule is one model per step type, let code pick the model. Workflow scripts use `modelFor(role, override)` in `workflow-helpers.js`: gather → haiku, work → opus, lead → the session model. The run arg `modelOverride` wins for every role.

### Measure on your own work

Sample real tasks with outcome checks. Run each candidate at 2-3 effort levels in separate sessions. Plot score against spend. Keep a multi-model setup only if it beats every single-model point. The Jev steps are under "Jev as a map".

## Owner override (2026-11-01)

Owner (notque), verbatim: "I like opus running actual code and making decisions, as it's the best model. everything else is worse, and then i don't save any tokens have to redo the work, and fix it." / "haiku for read only gathering has been fine, i just find sonnet for code and work, isn't as strong as opus."

The owner's observed experience supersedes the 2026-10 tables below: Sonnet code work needed redo. It stays binding under the 2026-11-09 policy:

- Opus: all code writing, edits, debugging, features, reviews that decide, and decisions. Default for anything not read-only.
- Haiku: read-only gathering only (locate, lookup, cite lines, collect excerpts, research fetch and executor work) that an Opus thread judges.
- Sonnet: no row's or tier's default.

The 2026-11-09 policy adds Fable above Opus and changes effort: standard and high-risk moved from opus/high to opus/medium, and max-power from opus/xhigh to fable/high. High-risk moved on the owner's order of the same day: "Also I prefer opus 5.5 medium over high".

The rest of this file is the historical 2026-10 record, kept for re-measurement.

## Historical record (2026-10)

Source: blind Jev eval, 2026-10.

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

In this 2026-10 eval, Opus topped none of the five task types; the owner override above supersedes that reading.

## Tier choice (2026-10, superseded)

| Tier | Choice | Probability | Rationale |
|---|---|---|---|
| low-risk | haiku | 0.80 (opus 0.20) | Cheapest, matched quality on locate, mech_edit, review. |
| standard | sonnet | 0.90 | Won deep_debug, ts_feature, long_lane; safer default for unmatched work. |
| high-risk | opus | 1.00 | Unmeasured, and a miss is costly. Opus is the paid-for insurance, not a measured winner. |

Tier mapping history in `build-dispatch.py`, as low-risk, standard, high-risk, max-power:

| Date | Mapping |
|---|---|
| 2026-10 | haiku/low, sonnet/medium, opus/high, opus/xhigh |
| 2026-11-01 | haiku/low, opus/high, opus/high, opus/xhigh |
| 2026-11-09 (PR #1150) | haiku/low, opus/medium, opus/high, fable/high |
| 2026-11-09 (owner order, same day) | haiku/low, opus/medium, opus/medium, fable/high |

Escalation history: haiku, sonnet, opus (2026-10); haiku, opus (2026-11-01); the current order is under "Escalate on a miss" above.

## Evidence limits

- One repo (TypeScript game), one run per cell. Variance across runs is unmeasured.
- The review row is n=1 (Sonnet's 3/4 may be noise).
- ts_feature stayed near a split (sonnet 0.59/0.64); treat it as a soft preference.
- Prompts above 100k tokens cost 5x on Haiku; long_lane Haiku ($0.25) sits near that edge.
- Costs are single-run dollars, not averages.

## Lesson: fix evidence before blaming the model

A split long_lane score came from a truncated diff in the state, which hid files from the judge. Restoring the full diff resolved the split: all three scored level 2 on player-facing text. When a score splits, check whether the state shows what a user would see before concluding the models differ.

## Jev as a map

Jev is the map; the task rows under "Current policy" are the current position. Re-measure with the judge/decide method.

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
