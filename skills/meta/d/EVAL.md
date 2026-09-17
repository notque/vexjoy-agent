# EVAL: /d — Jev-first router

Regression cases. Load only when evaluating or redesigning this skill. Full
corpus run: `python3 scripts/jev-eval.py --out-dir <new-dir>` against
`scripts/routing-ab-corpus.json` (269 cases); `--out-dir` is required and
must be a fresh directory — never overwrite a completed run. Results land
under `scripts/routing-ab-results/jev-router-v<N>-<date>/` per
`docs/router-ab-runbook.md`. The manual set below is the fast sanity check;
it does not replace the full corpus run.

## Idiom-guard sanity set (manual, run via `jev-route.py --request "..." --json-compact`)

| # | Request | Expected | Mechanism under test |
|---|---|---|---|
| 1 | "push my changes" | pr-workflow, `match_type: force_route`, `jev_called: false` | pre-route guard fires before Jev |
| 2 | "Push back on this architecture before we commit to it" | NOT pr-workflow | idiom guard (pushback/commit) |
| 3 | "Commit these changes and push to origin" | pr-workflow, force-route | genuine git intent |
| 4 | "Fish for compliments from the design team before shipping" | NOT shell-config | idiom guard (fish=search) |
| 5 | "Configure my fish shell prompt to show git branch" | shell-config | genuine Fish shell intent |
| 6 | "Make it public that we're hosting a charity stream next week" | NOT public-web-deploy | idiom guard (make public != deploy) |
| 7 | "Compare static site generators for a docs site" | NOT public-web-deploy (force) | work-on-a-site guard |
| 8 | "Deploy my landing page to Vercel" | public-web-deploy | genuine deploy intent + companion word |
| 9 | "help me plan a birthday party" | some sensible agent/skill via real Jev call | end-to-end Jev path exercised |
| 10 | (simulate) `TYPESAFE_API_KEY` unset | `fallback: true`, `source: "unavailable"` | presence-check fallback |
| 11 | (simulate) `--fits-threshold 0.99` on any real request | `fallback: true`, `source: "low-confidence"` | fits-threshold gate (v2; supersedes v1's `--confidence-floor`) |
| 12 | "thanks" / "hi" / "say hello" / "what is 2+2" | `source: "jev-trivial-bypass"`, `agent`/`skill`/`pipeline` all `null`, `matched: true`, `fallback: false` | stage-1 gate_score below `--gate-threshold`; stage 2 never called |

**Known result (2026-09-16 run)**: case 5 currently force-routes incorrectly
to `public-web-deploy` — traced to a pre-existing bug in `pre-route.py`
itself (the word "hosting" satisfies the "make it public" companion-word
gate). `jev-route.py` behaves exactly as designed — it never overrides a
force-route hit, by construction — the bug is upstream in `pre-route.py` and
out of `/d`'s scope to fix; it affects `/do` identically, since `/do` calls
the same `pre-route.py`. Cases 1-4, 6-7 resolve correctly.

## Known failure modes
- Jev returns a name not in the live manifest (renamed/deleted skill) ->
  must null + fallback, not silently pass through. Covered by manifest-
  membership validation in `jev-route.py`.
- Jev call exceeds timeout -> must fallback cleanly, not hang or crash `/d`.
  Covered by the `urllib` try/except + `--timeout` flag.
- Missing `requests`/HTTP-client dependency -> must not crash. Covered:
  `jev-route.py` uses stdlib `urllib.request` only (fixed 2026-09-16 after
  an `adr-consultation` finding; see `adr/d/concerns.md` Concern 10).
- Settings precedence: `settings.local.json` missing must not raise.
  Covered by `jev_router_common.py`'s non-fatal file handling.
- Confidently-wrong classification on `paraphrase-security`/
  `false-positive-guard` — no runtime backstop exists (see
  `references/jev-classifier-design.md` "Confident-wrong risk"); caught
  only by the per-bucket `SAFETY_BUCKETS` gate on the full corpus run, not
  by any single-request check.

## Full corpus run results (v2, 2026-09-16, corpus v1.5, 269 cases)
See `scripts/routing-ab-results/jev-router-v2-2026-09-16/VERDICT.md` for the
authoritative numbers (accuracy, fallback rate, per-bucket table, latency,
decision size) of the CURRENT two-stage design. Headline: `SAFETY_BUCKETS`
PASS (0 critical findings); overall accuracy 113/269 (42.0%, fallback
counted as incorrect); fallback rate 26.0%; decision JSON ~1/53rd the
manifest baseline's byte size; mean latency 285.0 ms across both HTTP round
trips (p50=268.2 ms, p95=400.9 ms). Do not re-quote these numbers without
re-running the eval — corpus and manifest both drift over time, and the
run's own VERDICT.md is the single source of truth for the date it ran.

## Superseded: v1 single-call design (2026-09-16, corpus v1.4, 269 cases)
`scripts/routing-ab-results/jev-router-v1-2026-09-16/VERDICT.md` — the
before/after baseline for the v2 redesign above, NOT the current design.
Headline: `SAFETY_BUCKETS` PASS; accuracy 45/269 (16.7%); fallback rate
62.1%; decision JSON ~1/76th the manifest baseline's byte size; single-call
latency p50=172.8 ms, p95=386.8 ms, mean=201.5 ms. Kept only as the
documented comparison point — see `references/jev-classifier-design.md`
"Why v1 was replaced" for what changed and why.
