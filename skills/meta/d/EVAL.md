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
| 10 | (simulate) both Jev keys unset | `fallback: true`, `source: "unavailable"` | presence-check fallback |
| 11 | (simulate) `--fits-threshold 0.99` on a multi-agent request | primary pick remains valid; optional fan-out is filtered | fan-out-only fits threshold |
| 12 | "thanks" / "hi" / "say hello" / "what is 2+2" | `source: "jev-trivial-bypass"`, `agent`/`skill`/`pipeline` all `null`, `matched: true`, `fallback: false` | stage-1 gate_score below `--gate-threshold`; stage 2 never called |

**Known result**: case 6 currently force-routes incorrectly
to `public-web-deploy` — traced to a pre-existing bug in `pre-route.py`
itself (the word "hosting" satisfies the "make it public" companion-word
gate). `jev-route.py` behaves exactly as designed — it never overrides a
force-route hit, by construction — the bug is upstream in `pre-route.py` and
out of `/d`'s scope to fix; it affects `/do` identically, since `/do` calls
the same `pre-route.py`. Case 6 therefore remains a known failing regression
case; it must not be listed among the cases that resolve correctly.

## Intent-alignment checks
- A proposed intent that drops material scope, adds unrequested work, or uses a
  route that visibly conflicts with the request must return `alignment: review`.
- The instruction gate must use the receipt produced for the exact runtime
  `PROPOSED_INTENT`; the hook-time baseline receipt cannot satisfy it. This is
  not hook enforcement, so tests must not claim a technical boundary that the
  implementation does not provide.
- Every matched route, including force-route and trivial-bypass, must attempt
  runtime alignment. A classification fallback delegates to `/do` and must not
  claim that intent validation succeeded.
- Essential ambiguity must return `clarification_needed: true`; routine
  implementation choices must not.
- A 429, 503, 529, or timeout from Vercel retries at most twice and persists a
  safe receipt; other gateway errors fail open.
- `auto` prefers Vercel, explicit transport selection never switches, and
  `direct` sends the same state and questions to the Jev API.

## Known failure modes
- Jev returns a name not in the live manifest (renamed/deleted skill) ->
  must null + fallback, not silently pass through. Covered by manifest-
  membership validation in `jev-route.py`.
- Jev call exceeds timeout -> must fallback cleanly, not hang or crash `/d`.
  Covered by the Vercel bridge retry receipt + `--timeout` flag.
- Missing Gateway bridge/HTTP-client dependency -> must not crash. Covered:
  `jev-route.py` uses the isolated Vercel bridge; the bridge package is
  installed by `install.sh`, and a missing bridge fails open to `/do`.
- Confidently-wrong classification on `paraphrase-security`/
  `false-positive-guard` — no runtime backstop exists (see
  `references/jev-classifier-design.md` "Confident-wrong risk"); caught
  only by the per-bucket `SAFETY_BUCKETS` gate on the full corpus run, not
  by any single-request check.

## Full-corpus evidence

Do not cite a run unless its verdict exists in the repository and was produced
from the current corpus, manifest, and implementation. The previously cited
2026-09-16 v1/v2 verdict paths are absent, so their historical percentages are
not part of this maintenance contract. Generate a fresh output directory with
the command above when comparative routing evidence is needed. Intent alignment
is production functionality established by repeated use; the corpus remains a
regression tool for route quality.
