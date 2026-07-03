# /do Skill Reduction A/B — VERDICT (run: do-skill-reduction-v1)

Date: 2026-07-03. Question: can the /do router skill shrink to ~half its size
with no behavior loss? Arms differ ONLY by the skill text prepended to an
identical compact manifest; same model (sonnet) both arms.

## Variant construction

- Baseline `full`: production `skills/meta/do/SKILL.md`, 40,924 B.
- Challenger `reduced`: 23,738 B (58.0% of full; −42.0%). Built by
  toolkit-governance-engineer (opus) with a 99-item behavior inventory, then
  hardened by an independent adversarial behavior-diff review (opus) that found
  4 BLOCKER + 8 MAJOR losses (dropped signal phrases, normative examples,
  tiebreaker rules) — all restored before the run. All executed bash blocks
  byte-identical to full. Dropped content: rationale, A/B provenance citations,
  duplicated rule statements, redundant examples.

## Run mechanics

- Harness: `scripts/routing-ab-test.py` manifest-arm mode (one harness for any
  router change). Corpus v3, 178 cases, one sample per (arm, query).
- Arm files: `<skill variant>\n\n<manifest>` filled into `PROMPT_TEMPLATE`'s
  manifest slot; manifest byte-identical across arms
  (`manifest.txt`, 24,254 B). `arms.json` records `--model-arm` sonnet/sonnet.
- Bridge: `collect-answers.py` (this dir) — idempotent, 6-way parallel,
  `env -u CLAUDECODE claude -p --model sonnet`. 356 answers; 7 first-pass
  failures (2.0% < 5% tolerance), re-collected. Total 366 calls, $87.03
  (`call-log.jsonl`).
- Blind judge: one opus agent over arm-stripped shuffled `judge-input.json`
  (356 rows), uid map withheld. Verdicts: 230 correct / 113 partial / 13
  incorrect. Rejoined: full 110/178 (61.8%) vs reduced 120/178 (67.4%) correct.

## Pre-registered gates (verbatim, unchanged from prior runs)

Gates (a) accuracy ±3.0, (b) McNemar harm, (c) zero new safety-bucket misses,
(d) stub-tier ±1 — as printed by `--gate`; see `docs/router-ab-runbook.md`.

## Results (deterministic gate scoring, raw.json)

| Metric | full (baseline) | reduced (challenger) |
|---|---|---|
| Overall accuracy | 93/178 (52.2%) | 106/178 (59.6%) |

Paired: D=0.073, 95% CI [0.011, 0.140], help=24, harm=11, discordant=35,
McNemar p=0.041 (in the challenger-favoring direction — gate (b) fails only on
harm>help). Safety buckets: zero new misses; paraphrase-git 6/6 and
paraphrase-security 4/4 in both arms. Stub-tier 10 → 10.

Gate outcomes: a PASS (+7.4), b PASS, c PASS, d PASS. Discordant 35 ≥ 6.

## VERDICT: PROMOTE (exit 0)

The reduced skill routes no worse — measurably better — at 58% of the size.
Promoted: reduced variant replaced `skills/meta/do/SKILL.md` (old version in
git history). Limitations: the harness exercises routing decisions (Step 0
semantics, force-routes, pipeline picks, interview/vague buckets) — not
Phase 3/4 execution behavior (enhancement stacking, dispatch building). Those
were guarded by the behavior-inventory + adversarial diff review instead, and
all executed bash blocks are byte-identical. Watch `route-events.jsonl`
outcomes post-promotion; rollback = `git checkout` of the prior SKILL.md.
