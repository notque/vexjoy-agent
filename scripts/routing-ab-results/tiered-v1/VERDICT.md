# Tiered-Manifest A/B — VERDICT (run: tiered-v1)

Date: 2026-06-10. Baseline arm `full` = `python3 scripts/routing-manifest.py`
(default). Challenger arm `tiered` = `python3 scripts/routing-manifest.py
--tiered`. Corpus v1.1, 99 cases, one Haiku sample per (arm, query). One run,
one verdict.

## Pre-registered gates (verbatim from `--gate`)

```
PRE-REGISTERED GATES (fixed in code before any run; change only BEFORE a run):
  (a) accuracy : challenger accuracy not worse than baseline by more than 3.0 points.
                 correct = exact expected agent+skill pair; where `acceptable` is
                 present, any listed {agent, skill} alternate also counts.
  (b) harm     : McNemar exact p for harm > 0.05. Fails only when challenger-harm
                 pairs exceed challenger-help pairs AND p <= 0.05.
  (c) safety   : ZERO new misses (baseline correct -> challenger wrong) in buckets
                 benchmark-force_route, false-positive-guard, paraphrase-git,
                 paraphrase-security.
  (d) stub-tier: challenger correct count in the stub-tier bucket within 1 case
                 of baseline.
VERDICT: PROMOTE (exit 0) = all gates pass AND discordant pairs >= 6.
         UNDERPOWERED (exit 2) = all gates pass but discordant pairs < 6.
         REJECT (exit 1) = any gate fails.
```

## Results

Deterministic gate scoring (raw.json, expected-pair + `acceptable` matching):

| Metric | full (baseline) | tiered (challenger) |
|---|---|---|
| Overall accuracy | 60/99 (60.6%) | 64/99 (64.6%) |

Paired stats: D=0.0404, 95% CI [-0.0404, 0.1212], help=11, harm=7,
discordant pairs=18, McNemar exact p=0.4807.

Per-bucket correct counts (deterministic). `*` = gate-protected safety bucket
(gate c); `stub-tier` is gate (d), the tiered tripwire.

| Bucket | n | full | tiered |
|---|---|---|---|
| benchmark-candidate | 6 | 2 | 2 |
| benchmark-force_route `*` | 7 | 6 | 7 |
| benchmark-llm_only | 5 | 2 | 2 |
| false-positive-guard `*` | 7 | 2 | 2 |
| paraphrase-debug | 3 | 0 | 0 |
| paraphrase-explore | 3 | 0 | 0 |
| paraphrase-git `*` | 6 | 6 | 6 |
| paraphrase-refactor | 3 | 2 | 3 |
| paraphrase-review | 3 | 0 | 1 |
| paraphrase-security `*` | 4 | 3 | 3 |
| paraphrase-test | 2 | 1 | 0 |
| pipeline-pick | 9 | 6 | 5 |
| plain-english | 10 | 6 | 9 |
| sibling-disambiguation | 12 | 10 | 11 |
| **stub-tier** | 12 | **12** | **9** |
| vague-interview | 7 | 2 | 4 |

Gate outcomes: a_accuracy PASS, b_harm PASS, **c_safety FAIL** (1 new miss:
q07, paraphrase-security), **d_stub_tier FAIL** (12 → 9, drop of 3 > allowed 1).

## VERDICT: REJECT (exit 1)

Failure mechanism (one root cause, 4/4 divergent gate cases): the tiered arm
picked the **correct skill** but returned `agent: null` where full returned the
expected agent — q07 (security-review, expected reviewer-system), q55
(frontend-slides, expected typescript-frontend-engineer), q57 (x-api, expected
python-general-engineer), q60 (phaser-gamedev, expected
typescript-frontend-engineer). Consistent with the
tiered manifest dropping agent attribution for low/zero-route skills. Fix the
tiered manifest's agent mapping and re-run with a fresh `--out-dir`.

Blind-judge scoreboard (nuanced read, scoreboard.json): full 59/99 strict
(59.6%), tiered 59/99 (59.6%); judge stub-tier full 12/12 vs tiered 8/12. Judge
and gate agree on direction for stub-tier; the judge sees overall parity where
the gate sees tiered +4 — per the runbook, both numbers are reported, the gate
decides.

## Cost

| Item | full | tiered |
|---|---|---|
| Manifest snapshot size | 35,709 B | 26,127 B |
| Mean prompt size (manifest + query) | 36,434 B | 26,852 B |
| Haiku answers kept | 99 | 99 |

Calls actually made: 212 routing calls (198 kept answers + 14
retries/timeouts/duplicates, from the bridge call log) + 1 blind-judge call
+ 1 auth-preflight call = 214 `claude -p` Haiku calls. Exact $ not derivable:
calls ran on the owner's subscription via `claude -p` and per-call cost
envelopes were not retained. Runbook estimate for this shape: ~$1.50–2.00.

## Unanswered cases

Initial collection pass: 4 unanswered (timeouts): full/q97, tiered/q33,
tiered/q36, tiered/q85 (4/198 = 2.0% < 5%, re-collection permitted). One
re-collection pass of missing ids only brought the run to 198/198. Final
unanswered: 0. (tiered/q41 was also re-collected mid-run after a transient
malformed response; final answer present.)

## Judge blinding

The judge saw only `judge-input.json`: 198 arm-stripped, seed-shuffled rows
(uid, query, expected pair, notes, predicted pair). `uid-map.json` (uid → case
+ arm) was never included in the judge prompt or readable by the judge call;
rejoin used it only after `judge-output.json` was written. Single judge pass
(`claude -p`, haiku); output covered all 198 uids with valid grades on first
pass.

## Run integrity notes

- Live `~/.claude/learning/*` was not edited by this run's tooling. Mtime
  check across the run window: `rules-distill-*` unchanged; `learning.db`,
  `route-events.jsonl`, `usage.db` mtimes advanced — written by the toolkit's
  own session hooks reacting to the nested `claude -p` sessions and the
  orchestrator session, not by the harness or any manual edit.
- No harness code, corpus labels, or gates were changed. Arms were frozen
  before this resume; prompts and manifest snapshots untouched (full manifest
  sha256 98a0e599…, tiered 2111140f…).
