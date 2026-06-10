# Self-Route A/B — VERDICT (run: self-route-v1)

Date: 2026-06-10. The model A/B the PHILOSOPHY.md OPEN item calls for: same
FULL manifest both arms, only the routing model differs. Baseline arm `haiku`
= production Step 0 sub-dispatch (`claude -p --model haiku`, resolved
`claude-haiku-4-5-20251001`). Challenger arm `self-route` = same prompt to the
session default model (`--model` omitted, resolved `claude-fable-5`) — the
closest `claude -p` approximation of the orchestrator reading the manifest
itself, no sub-dispatch hop. Corpus v1.1, 99 cases, one sample per (arm,
query). One run, one verdict.

Both arms' manifests came from `python3 scripts/routing-manifest.py` (default,
full) at origin/main `098e23fe`; per-arm prompts are byte-identical (manifest
sha256 c0b5f77f… both arms, 33,858 B). Prompt template: the harness's
`PROMPT_TEMPLATE`, verbatim the one tiered-v1/v2 used, carrying the semantic
FORCE rule and the git rule. Production Step 0 additionally carries a
section-integrity rule; the harness template does not — identical in both
arms, so the comparison is unbiased and stays comparable with tiered runs.
Run mechanics: harness gained `--model-arm name=model` (recorded in
arms.json `models`; tests added) BEFORE the run; gates untouched.

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

Gates identical to tiered-v1/v2; no post-hoc adjustment.

## Results

Deterministic gate scoring (raw.json, expected-pair + `acceptable` matching):

| Metric | haiku (baseline) | self-route (challenger) |
|---|---|---|
| Overall accuracy | 49/99 (49.5%) | 57/99 (57.6%) |

Paired stats: D=0.0808, 95% CI [0.0, 0.1616], help=13, harm=5,
discordant pairs=18, McNemar exact p=0.0963.

Per-bucket correct counts (deterministic). `*` = gate-protected safety bucket
(gate c); `stub-tier` is gate (d).

| Bucket | n | haiku | self-route |
|---|---|---|---|
| benchmark-candidate | 6 | 1 | 1 |
| benchmark-force_route `*` | 7 | 6 | 7 |
| benchmark-llm_only | 5 | 2 | 1 |
| false-positive-guard `*` | 7 | 1 | 2 |
| paraphrase-debug | 3 | 0 | 1 |
| paraphrase-explore | 3 | 0 | 0 |
| paraphrase-git `*` | 6 | 6 | 6 |
| paraphrase-refactor | 3 | 1 | 3 |
| paraphrase-review | 3 | 0 | 0 |
| paraphrase-security `*` | 4 | 3 | 3 |
| paraphrase-test | 2 | 0 | 0 |
| pipeline-pick | 9 | 3 | 4 |
| plain-english | 10 | 6 | 7 |
| sibling-disambiguation | 12 | 9 | 10 |
| **stub-tier** | 12 | **9** | **12** |
| vague-interview | 7 | 2 | 0 |

Gate outcomes: a_accuracy PASS (challenger +8.1), b_harm PASS (help 13 >
harm 5, p=0.0963), c_safety PASS (zero new safety-bucket misses), d_stub_tier
PASS (9 → 12, improved). Discordant pairs 18 ≥ 6.

## VERDICT: PROMOTE (exit 0)

## Mechanism

Where self-route wins (13 help cases): mostly the agent-attribution failure
that REJECTED both tiered runs — Haiku picks the right skill but a null,
wrong, or invented agent. 8 of 13 help cases have the same skill in both arms
and only the agent field fixed (q45, q52, q54, q57, q72, q81, q90 — incl.
removing spurious agents and one `"agent": "Explore"` section-integrity
violation by Haiku at q81), plus stub-tier recovering 9 → 12 and the q36
go-patterns force-route (a tiered-v2 gate-c failure case) landing correctly.
The main model holds attribution on one-line manifest entries where Haiku
drops it.

Where self-route loses (5 harm cases): over-attribution on null-expected
fields (q38, q47, q73 — adds a defensible-but-wrong agent or skill where the
gold label is null) and vague-interview (q86 plant-seed, q88 workflow, where
Haiku picked the expected planning). vague-interview is the only bucket the
challenger drops (2 → 0); it is not gate-protected, and the /do interview
path has its own Phase 1 handling.

Blind-judge scoreboard (nuanced read, scoreboard.json): haiku 47/99 strict
(47.5%) vs self-route 56/99 (56.6%); judge stub-tier 9/12 vs 11/12. Judge and
gate agree on direction overall and per failing bucket. McNemar p=0.0963: the
challenger's +8.1 is not individually significant at n=99 — but the gates are
non-inferiority gates, and every one passes with margin.

## Cost

Measured (call-log.jsonl, kept answers; `claude -p` on the owner's
subscription, so cost_usd is the API-equivalent envelope):

| Item | haiku | self-route |
|---|---|---|
| Model | claude-haiku-4-5-20251001 | claude-fable-5 (session default) |
| Manifest snapshot size | 33,858 B | 33,858 B (byte-identical) |
| Mean prompt size (manifest + query) | 34,546 B (q00) | 34,546 B (q00) |
| Answers kept | 99 | 99 |
| Total kept-answer cost | $2.51 | $27.92 |
| Mean cost / call | $0.0253 | $0.2820 (11.2x) |
| Cost / correct route | $0.0512 | $0.4898 (9.6x) |
| Tokens / correct route (all types) | 68,489 | 67,183 |
| Mean wall time / call | 16.3 s | 11.6 s |

The honest cost story, both sides:

- **As measured, self-route costs ~11x per call and ~9.6x per correct
  route.** Raw tokens-per-correct-route are near parity only because each
  nested `claude -p` session drags ~20K cache-write + up to ~320K cache-read
  tokens of session bootstrap in BOTH arms; the dollar gap is real because
  the challenger pays main-model rates.
- **The measurement overstates production self-route cost.** In production,
  self-route deletes the dispatch hop: no second session bootstrap, no Haiku
  round trip (~16 s wall here), no `[do-route]` relay. The marginal cost is
  the orchestrator reading the ~34 KB manifest (~8.5K tokens) in its already
  open main-model session. The spend driver is the manifest, not the hop —
  PHILOSOPHY.md's standing follow-up (trim the manifest to router-only
  metadata) is where the real savings live, and it compounds with this
  verdict instead of competing with it.

Calls actually made: 202 routing calls (198 kept + 2 haiku malformed retries
+ 1 haiku smoke-test malformed + 1 haiku out-of-band diagnostic whose answer
was not kept) + 1 blind-judge call ($0.11, haiku) + 2 auth-preflight calls
(one per arm model) = 205 `claude -p` calls. Non-kept overhead: ~$0.19
routing + $0.32 preflight.

## Unanswered cases

Initial collection pass: 2 unanswered (haiku/q33, haiku/q39 — malformed
responses; 2/198 = 1.0% < 5%, re-collection permitted). One re-collection
pass of the missing ids brought the run to 198/198. Final unanswered: 0.

## Judge blinding

The judge saw only `judge-input.json`: 198 arm-stripped, seed-shuffled rows
(uid, query, expected pair, notes, predicted pair). `uid-map.json` (uid →
case + arm) was never included in the judge prompt or readable by the judge
call; rejoin used it only after `judge-output.json` was written. Single judge
pass (`claude -p`, haiku); output covered all 198 uids with valid grades on
first pass.

## Run integrity notes

- Auth preflight per runbook for BOTH arm models before any collection:
  `is_error: false` on `--model haiku` and on the default model
  (resolved `claude-fable-5`).
- Fresh `git worktree` at origin/main `098e23fe`; the live checkout and the
  tiered worktree were not touched. `skills/INDEX.json` / `agents/INDEX.json`
  are gitignored generated artifacts, regenerated in the worktree from
  tracked frontmatter before emit (hence manifest sha c0b5f77f… differs from
  tiered-v1/v2's 98a0e599… — main moved between runs; within this run both
  arms are byte-identical).
- Harness change (`--model-arm`) is collection plumbing only — it records
  models in arms.json for the bridge; scoring, judging, and gates untouched.
  Added with tests before emit; full suite green (38 passed).
- No corpus labels or gates were changed. Fresh `--out-dir`; prior run
  artifacts untouched.

## Interpretation

This run decides the PHILOSOPHY.md OPEN item ("whether the Haiku sub-dispatch
beats orchestrator self-route", tied 63.3% vs 63.3% at n=49): at n=99 under
pre-registered gates, **self-route PROMOTES** — +8.1 points, zero new safety
misses, stub-tier improved, and it fixes the agent-attribution failure mode
two tiered runs died on. By the program's own rule — "if it isn't improving
the router, remove it" — the Haiku hop is not improving the router; it is
buying a cheaper price per routing call and nothing else, while costing
accuracy and a dispatch round trip.

**Follow-up spec (NOT implemented here): delete the Haiku hop from /do
Phase 2 Step 0.**

- Step 0 becomes: orchestrator generates the manifest
  (`routing-manifest.py`, unchanged) and routes directly off it in-session,
  applying the full production Step 0 prompt rules inline (section-integrity,
  FORCE/semantic matching, pipeline-selection, git rule). No
  `Agent(model: "haiku")` dispatch; the routing JSON stays internal.
- Keep unchanged: the pre-route high-confidence force-route fast path (runs
  first), Step 1 deterministic safety net, dispatch-time section validator,
  routing banner, Step 2 overrides, all Phase 3/4 injections.
- `[do-route]` marker keeps its shape; router identity is implicit.
- Sequencing: land the manifest trim (router-only metadata) with or after
  this change — the manifest is now the whole marginal cost of routing.
- Re-run guard: any later router-prompt change goes through this same
  harness (`--model-arm` now makes model arms first-class).
