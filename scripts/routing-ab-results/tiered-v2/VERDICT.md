# Tiered-Manifest A/B — VERDICT (run: tiered-v2)

Date: 2026-06-10. Re-run of REJECTED tiered-v1 with the stub-attribution fix
(`c1080c04` on feat/do-cost-diet: keep `agent=` and not_for on tiered stub
skill lines). Baseline arm `full` = `python3 scripts/routing-manifest.py`
(default). Challenger arm `tiered` = `python3 scripts/routing-manifest.py
--tiered`, both run from the feat/do-cost-diet checkout at `c1080c04`. Corpus
v1.1, 99 cases, one Haiku sample per (arm, query). One run, one verdict.

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

Gates identical to tiered-v1; no post-hoc adjustment.

## Results

Deterministic gate scoring (raw.json, expected-pair + `acceptable` matching):

| Metric | full (baseline) | tiered (challenger) |
|---|---|---|
| Overall accuracy | 53/99 (53.5%) | 56/99 (56.6%) |

Paired stats: D=0.0303, 95% CI [-0.0505, 0.1111], help=11, harm=8,
discordant pairs=19, McNemar exact p=0.6476.

Per-bucket correct counts (deterministic). `*` = gate-protected safety bucket
(gate c); `stub-tier` is gate (d), the tiered tripwire.

| Bucket | n | full | tiered |
|---|---|---|---|
| benchmark-candidate | 6 | 0 | 2 |
| benchmark-force_route `*` | 7 | 6 | 5 |
| benchmark-llm_only | 5 | 2 | 2 |
| false-positive-guard `*` | 7 | 2 | 3 |
| paraphrase-debug | 3 | 0 | 0 |
| paraphrase-explore | 3 | 0 | 0 |
| paraphrase-git `*` | 6 | 6 | 6 |
| paraphrase-refactor | 3 | 2 | 3 |
| paraphrase-review | 3 | 0 | 1 |
| paraphrase-security `*` | 4 | 3 | 2 |
| paraphrase-test | 2 | 0 | 0 |
| pipeline-pick | 9 | 3 | 2 |
| plain-english | 10 | 5 | 8 |
| sibling-disambiguation | 12 | 11 | 10 |
| **stub-tier** | 12 | **12** | **10** |
| vague-interview | 7 | 1 | 2 |

Gate outcomes: a_accuracy PASS (challenger +3.1), b_harm PASS (p=0.6476),
**c_safety FAIL** (3 new misses: q22 paraphrase-security, q32
false-positive-guard, q36 benchmark-force_route), **d_stub_tier FAIL**
(12 → 10, drop of 2 > allowed 1).

## VERDICT: REJECT (exit 1)

## Failure mechanism

The c1080c04 fix did what it claimed: v1's four divergent cases (q07, q55,
q57, q60 — correct skill, `agent: null`) were re-tested and q07 + q55 now
PASS in both arms; stub-tier recovered from 9 to 10. But the run still fails
gates (c) and (d), via two mechanisms:

**1. Residual agent-null on condensed stub lines (q22, q57, q60 — 3 of 5
harm-side gate cases).** Same v1 signature: tiered picks the correct skill
but returns `agent: null` where full returns the expected agent, at
`confidence: high`. The tiered manifest now carries the attribution
(`x-api agent=python-general-engineer`, `phaser-gamedev
agent=typescript-frontend-engineer`, `security-review FORCE
agent=reviewer-system`), so the text fix is in — Haiku still omits the agent
when reasoning off the shortened one-line entries ("x-api skill directly
handles posting to X"). Attribution text alone does not reliably transfer on
condensed lines.

**2. Behavioral drift on byte-identical lines (q32, q36).** The `go-patterns`
and `codebase-overview` manifest lines are byte-identical across arms; only
surrounding context shrank. q36 ("write table-driven tests for the parser")
lost the go-patterns FORCE route to test-driven-development; q32 ("give me a
quick read on the architecture") over-routed a guard case to
codebase-overview. At one sample per (query, arm) this is indistinguishable
from sampling noise — but the gates are pre-registered and trade no misses.

Divergent gate cases (safety + stub buckets only):

| id | bucket | query (trunc) | expected | full picked | tiered picked |
|---|---|---|---|---|---|
| q22 | paraphrase-security | "before I share my branch, make sure I did not leave any pass…" | reviewer-system / security-review | reviewer-system / security-review | **null** / security-review |
| q32 | false-positive-guard | "give me a quick read on the architecture" | null / null | null / null | null / **codebase-overview** |
| q36 | benchmark-force_route | "write table-driven tests for the parser" | golang-general-engineer / go-patterns | golang-general-engineer / go-patterns | **python-general-engineer / test-driven-development** |
| q57 | stub-tier | "post this announcement as a thread on X with the screenshot…" | python-general-engineer / x-api | python-general-engineer / x-api | **null** / x-api |
| q60 | stub-tier | "add a tilemap level with arcade physics and a jumping player…" | typescript-frontend-engineer / phaser-gamedev | typescript-frontend-engineer / phaser-gamedev | **null** / phaser-gamedev |

Help-side flips exist in the same buckets (q91 is the exact inverse of q22;
guard cases q29/q33 flipped toward tiered), so the agent-null behavior is
stochastic in both arms — but gate (c) counts new misses only, by design.

Blind-judge scoreboard (nuanced read, scoreboard.json): full 58/99 strict
(58.6%), tiered 56/99 (56.6%); judge stub-tier full 12/12 vs tiered 9/12.
Judge and gate disagree on overall direction (judge sees full +2, gate sees
tiered +3 via `acceptable` matching); per the runbook both numbers are
reported, the gate decides. On stub-tier and the gate-failure direction they
agree.

## Cost

| Item | full | tiered |
|---|---|---|
| Manifest snapshot size | 35,709 B | 28,325 B |
| Mean prompt size (manifest + query) | 36,435 B | 29,051 B |
| Haiku answers kept | 99 | 99 |

Tiered saving vs full: ~20.3% of prompt bytes (v1's broken tiered saved
26.7% — the fix bought back 2.2 KB of attribution text).

Calls actually made: 199 routing calls (198 kept answers + 1 retry after a
malformed response) + 1 blind-judge call + 1 auth-preflight call = 201
`claude -p` Haiku calls. Logged call cost (call-log.jsonl): ~$6.03 routing
+ ~$0.09 judge; ran on the owner's subscription via `claude -p`. Higher than
the runbook's ~$1.50 API estimate because each nested `claude -p` session
carries ~29K tokens of system/tool overhead per call.

## Unanswered cases

Initial collection pass: 1 unanswered (tiered/q33, malformed response;
1/198 = 0.5% < 5%, re-collection permitted). One re-collection pass of the
missing id brought the run to 198/198. Final unanswered: 0.

## Judge blinding

The judge saw only `judge-input.json`: 198 arm-stripped, seed-shuffled rows
(uid, query, expected pair, notes, predicted pair). `uid-map.json` (uid →
case + arm) was never included in the judge prompt or readable by the judge
call; rejoin used it only after `judge-output.json` was written. Single judge
pass (`claude -p`, haiku); output covered all 198 uids with valid grades on
first pass.

## Run integrity notes

- Auth preflight per runbook: `is_error: false` before any collection.
- Challenger code: feat/do-cost-diet checkout at `c1080c04` (verified
  `merge-base --is-ancestor`); `scripts/routing-manifest.py` clean in
  `git status` before emit.
- Full manifest sha256 98a0e599… — byte-identical to tiered-v1's baseline.
  Tiered manifest sha256 d6c098ea… (v1: 2111140f…) — the fix is the only
  arm-side change between runs.
- No harness code, corpus labels, or gates were changed. Fresh `--out-dir`;
  tiered-v1 artifacts untouched.
