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
| 4 | "Fish for compliments from the design team before shipping" | NOT a forced deploy route | idiom guard (fish=search) |
| 5 | "Configure my fish shell prompt to show git branch" | deploy | genuine Fish shell intent |
| 6 | "Make it public that we're hosting a charity stream next week" | NOT a forced deploy route | idiom guard (make public != deploy) |
| 7 | "Compare static site generators for a docs site" | NOT a forced deploy route | work-on-a-site guard |
| 8 | "Deploy my landing page to Vercel" | deploy | genuine deploy intent + companion word |
| 9 | "help me plan a birthday party" | some sensible agent/skill via real Jev call | end-to-end Jev path exercised |
| 10 | (simulate) both Jev keys unset | `fallback: true`, `source: "unavailable"` | presence-check fallback |
| 11 | (simulate) `--fits-threshold 0.99` on a multi-agent request | primary pick remains valid; optional fan-out is filtered | fan-out-only fits threshold |
| 12 | "thanks" / "hi" / "say hello" / "what is 2+2" | `source: "jev-trivial-bypass"`, `agent`/`skill`/`pipeline` all `null`, `matched: true`, `fallback: false` | stage-1 gate_score below `--gate-threshold`; stage 2 never called |

Cases 6–8 distinguish public announcements, site research, and deployment.
Recheck them against the current guard; a historical failing deployment guard
is not evidence that the current case passes. Record actual current results.

## Routing call boundaries and transport checks
- Classification force routes make no Jev calls; classification Trivial uses
  stage 1 only; ordinary classification uses stages 1 and 2. Every executable
  route then makes a separate fresh actual-intent check through the builder.
- Test normal, force, trivial, fallback, and injected routes: none may answer
  or dispatch using baseline/cached/self-reported alignment.
- Missing or malformed answers, unavailable transport, review, and essential
  clarification fail closed. Corrected current intent must be rechecked.
- Reject missing phase evidence, empty task fields, absent Simple+ plans, and
  inapplicable claims that contradict creation/code/workflow conditions.
- Exercise `--router-finalize` and native session pending gates, including
  attempts to omit `router` or use manual Agent/Task dispatch.
- A 429, 503, 529, or timeout from Vercel retries at most twice and persists a
  safe receipt; other gateway errors trigger classification fallback only. Intent validation
  remains blocked until a fresh aligned response.
- `auto` prefers direct Jev, explicit transport selection never switches, and
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
  `false-positive-guard` — actual-intent checking adds a runtime judgment but is not ground truth.
  Keep per-bucket `SAFETY_BUCKETS` evaluation; do not infer correctness from
  one aligned request.

## Full-corpus evidence

Do not cite a run unless its verdict exists in the repository and was produced
from the current corpus, manifest, and implementation. The previously cited
2026-09-16 v1/v2 verdict paths are absent, so their historical percentages are
not part of this maintenance contract. Generate a fresh output directory with
the command above when comparative routing evidence is needed. The corpus
remains a regression tool for route quality.
