# Router A/B Runbook

Standing procedure for judging ANY router change (manifest variants, fast paths,
prompt edits, re-rank policies) with the existing blind A/B harness. One harness:
`scripts/routing-ab-test.py`. Never build a parallel one.

## The standing sequence

1. **Branch.** Put the router change on its own branch. The harness only takes
   manifest *commands* as strings, so the challenger command can live on another
   branch's worktree (e.g. `python3 ../wt-cost-diet/scripts/routing-manifest.py --tiered`).
2. **Pick a run dir.** Every run gets a fresh subdirectory; completed runs in
   `scripts/routing-ab-results/` are never overwritten:
   `OUT=scripts/routing-ab-results/<change>-<date>`
3. **Emit per-arm prompts.**
   ```sh
   python3 scripts/routing-ab-test.py --emit-prompts --out-dir "$OUT" \
     --manifest-arm full="python3 scripts/routing-manifest.py --compact" \
     --manifest-arm tiered="python3 scripts/routing-manifest.py --tiered"
   ```
   The full arm's manifest command (here `--compact`) is part of the experiment
   definition — flag choice changes baseline prompt size materially (~35.7 KB
   default vs ~20 KB compact); record it in `arms.json` and keep it fixed across
   runs being compared.
   First arm = baseline, second = challenger (override at --gate with
   `--baseline-arm/--challenger-arm`). Without `--manifest-arm` the harness runs
   the legacy shared-prompt A/B (deterministic-first vs semantic-first).
4. **Bridge: collect Haiku answers** (see below).
5. **Score.** `python3 scripts/routing-ab-test.py --score --out-dir "$OUT"`
6. **Blind judge.** `--build-judge` writes an arm-stripped, seed-shuffled
   `judge-input.json` plus a private `uid-map.json` (carries case + arm; the judge
   never sees it). Dispatch ONE judge agent over `judge-input.json`; it returns
   `{uid: "correct"|"partial"|"incorrect"}` as `judge-output.json`. Then
   `--rejoin` writes `scoreboard.json` with per-arm, per-bucket accuracy.
7. **Gate.** `python3 scripts/routing-ab-test.py --gate --out-dir "$OUT"` prints
   the pre-registered gates, then the verdict. Exit 0 PROMOTE, 1 REJECT,
   2 UNDERPOWERED. The gate is deterministic (expected-pair/`acceptable`
   matching over raw.json), so it cannot be argued with after the fact.
8. **PR.** Attach `scoreboard.json` + the `--gate` output to the router-change
   PR. The gate verdict decides; a REJECT means the change does not merge in its
   current form.

For force-route fast-path changes there is also a zero-model check:

```sh
python3 scripts/routing-ab-test.py --pre-route-map --assert-buckets --out-dir "$OUT"
```

It asserts every benchmark-force_route, paraphrase-git, and paraphrase-security
case is fast-path eligible (pre-route confidence `high` + `force_route`) and no
false-positive-guard case is. Exit 0/1. As of corpus v1.1 this FAILS (13
violations): all 10 paraphrase-git/security cases fall through the keyword
pre-router by design, and 3 keyword force-route cases sit at `medium`
confidence. Meaning: a fast path keyed on high-confidence force_route fires on
only 8/99 corpus cases and never on paraphrased safety intents — those still
need the semantic router. The guard direction holds (0/7 guards eligible).

## The answer-collection bridge

**Auth preflight (mandatory, before any answer collection).** Nested `claude -p`
reads `~/.claude/.credentials.json`, which `-p` mode never refreshes;
`claude auth status` reports loggedIn even when the token is expired and every
call 401s. Verify first:

```sh
env -u CLAUDECODE claude -p "Say OK" --model haiku --output-format json
```

Proceed only if the JSON shows `is_error: false`. On 401, the owner re-auths
interactively (`claude auth login`) — no scripted workaround.

`routing-ab-test.py` cannot call models (no API key, by design). A runner — the
orchestrator session or a human — bridges, exactly as in the semantic-first run
whose artifacts sit in `scripts/routing-ab-results/`:

- For each `"$OUT"/prompts/<arm>/<id>.txt` (legacy: `prompts/<id>.txt`), send the
  file content verbatim as a single prompt to **Haiku** (`claude-haiku-4-5`, the
  project's router model).
- Save the model's raw JSON object — shape
  `{"agent": ..., "skill": ..., "pipeline": ..., "reasoning": ..., "confidence": ...}`
  — as `"$OUT"/answers/<arm>/<id>.json` (legacy: `answers/<id>.json`).
- `--score` refuses to run until every (arm, query) answer exists, and lists the
  missing ones.
- **Unanswered cases: the harness wins.** "Retry once, then record unanswered"
  conflicts with `--score`, which refuses to run with ANY missing answer — so an
  unanswered case always blocks scoring. The <5%-loss tolerance decides only
  whether re-collection is permitted: re-collect just the missing ids via the
  idempotent bridge (it skips existing answers). If more than 5% of cases are
  still missing after one re-collection pass, declare the run INVALID.

The judge step is the same pattern: one agent reads `judge-input.json`, writes
`judge-output.json`. Keep `uid-map.json` away from the judge.

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

**Rule: gates change only BEFORE a run.** They live in code
(`GATES_TEXT`, `gate_verdict` in `scripts/routing-ab-test.py`) and in this file.
Editing a gate after seeing results invalidates the run — re-register the gate,
then run again. The McNemar exact test and paired-bootstrap stats are ported
from `feat/outcome-routing-loop:scripts/route-value-eval.py`.

## Adding corpus cases or buckets

Corpus: `scripts/routing-ab-corpus.json` (v1.1, 99 cases). Rules:

- **Append only.** The 49 legacy v1.0 cases are pinned by SHA-256 in
  `scripts/tests/test_routing_ab_harness.py`; editing them breaks CI.
- Schema per case: `{request, expected_agent, expected_skill, category, bucket,
  notes}` + optional `expected_pipeline` (default null), `acceptable` (list of
  `{agent, skill}` alternates), `uncertain: true` (best-effort gold label).
- Gold labels come from `skills/INDEX.json` / `pipeline-index.json` semantics,
  never from what the current router picks (that would be circular).
- Write realistic phrasing (file paths, casual wording), not abstract one-liners.
- New buckets are fine; if a bucket should be gate-protected, add it to
  `SAFETY_BUCKETS` in the harness BEFORE the run and note it here.
- Buckets v1.1 added: `stub-tier` (skills with zero recorded routes — the
  tiered-manifest tripwire), `sibling-disambiguation`, `pipeline-pick`
  (`expected_pipeline`; near-misses must yield pipeline null), `vague-interview`,
  `plain-english`.
- Add cases on a branch and run the corpus tests:
  `python3 -m pytest scripts/tests/test_routing_ab_harness.py -q`.

## Cost: 100-case, 2-arm run

Haiku 4.5 (`claude-haiku-4-5`): $1.00/M input, $5.00/M output.

| Step | Calls | Tokens (approx) | Cost |
|---|---|---|---|
| Routing answers | 200 (100 x 2 arms) | ~6K in + ~0.1K out each → 1.2M in, 20K out | ~$1.30 |
| Blind judge | 1 agent pass over 200 rows | ~40K in, ~5K out | ~$0.07 |
| score / gate / pre-route-map | 0 model calls | — | $0 |

**~$1.50 per full run** (compact manifest ≈ 20KB ≈ 5-6K tokens per prompt; a
tiered arm's prompts are smaller, so real runs cost less). Negligible against
the Opus orchestrator session driving it.

## Prior results

- Semantic-first experiment (49-case corpus, Arm A deterministic-first vs Arm B
  semantic-first): artifacts in `scripts/routing-ab-results/` (answers,
  `answers-v2/` git-rule fix retest, scoreboard). Results doc:
  `skills/meta/do/references/semantic-first-ab-results.md`. Outcome:
  A ≡ B at 89.8% strict; the win was the git-rule prompt fix (~91.8%, zero
  guard violations); Option B (semantic-first + safety net) shipped.
- Fast-path eligibility map for corpus v1.1:
  `scripts/routing-ab-results/pre-route-map-v1.1/` (deterministic, regenerate
  any time with `--pre-route-map`).

## Queued experiments

1. **Tiered manifest** (`feat/do-cost-diet`): run the standing sequence with
   `--manifest-arm full=... --manifest-arm tiered=...` once that branch lands.
   Watch gate (d) — stub-tier is the bucket a tiered manifest can starve.
2. **Force-route fast path**: `--pre-route-map --assert-buckets` is the
   behavior-identical check; today's failing baseline (above) is the comparison
   point. A fast path must not make a guard case eligible, and any claim that
   paraphrases are covered must flip those 10 cases to PASS first.

## Known limits

- ~100 cases is small: gates use a 3-point margin, an exact McNemar test, and an
  explicit UNDERPOWERED verdict (discordant < 6) instead of pretending power.
- Gate correctness is exact-pair matching softened only by `acceptable`; the
  blind judge scoreboard remains the nuanced read. When they disagree, say so in
  the PR rather than picking the friendlier number.
- Single Haiku sample per (query, arm): no self-consistency estimate. Re-run
  with a fresh `--out-dir` to measure variance.
- 8 corpus cases carry `uncertain: true` — best-effort gold labels.
- Gold labels encode INDEX semantics as of corpus v1.1; renamed or split skills
  need corpus maintenance (append corrected cases, never edit legacy ones).
- `--pre-route-map` depends on the live `skills/INDEX.json` triggers; results
  drift as triggers change. Snapshot per run via `--out-dir`.
