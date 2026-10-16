# EVAL: /d — session-pick router with Jev validation

Regression cases. Load only when evaluating or redesigning this skill. Full
corpus run: `python3 scripts/jev-eval.py --out-dir <new-dir>` against
`scripts/routing-ab-corpus.json` (269 cases); `--out-dir` is required and
must be a fresh directory — never overwrite a completed run. Each case runs
`jev-route.py` prepare, a `claude -p` session pick (`scripts/d_route_model.py`),
and `jev-route.py --finalize`. Pass `--workload-dir NAME=PATH` for corpus cases
that record a workload, so both arms of a comparison see the same repo facts.
Results land under `scripts/routing-ab-results/` per
`docs/router-ab-runbook.md`. The manual set below is the fast sanity check; it
does not replace the full corpus run.

Compare arms with two runs each. A rerun with unchanged code changes the pick
on about 11% of rows, so count a row as changed only when both runs of the arm
agree.

## Idiom-guard sanity set (manual: send each request to `/d`, or run `jev-eval.py --limit`)

| # | Request | Expected | Mechanism under test |
|---|---|---|---|
| 1 | "push my changes" | pr-workflow, `source: "pre-route-force"`; you pick the agent | safety force route keeps its skill |
| 2 | "Push back on this architecture before we commit to it" | NOT pr-workflow | FORCE rule: means, not words |
| 3 | "Commit these changes and push to origin" | pr-workflow, `source: "pre-route-force"` | genuine git intent |
| 4 | "Fish for compliments from the design team before shipping" | NOT shell-config | FORCE rule (fish = search) |
| 5 | "Configure my fish shell prompt to show git branch" | shell-config | genuine Fish shell intent |
| 6 | "Make it public that we're hosting a charity stream next week" | NOT public-web-deploy | FORCE rule (make public != deploy) |
| 7 | "Compare static site generators for a docs site" | NOT public-web-deploy (force) | work-on-a-site guard |
| 8 | "Deploy my landing page to Vercel" | public-web-deploy | genuine deploy intent + companion word |
| 9 | "help me plan a birthday party" | some sensible agent/skill | end-to-end path exercised |
| 10 | (simulate) both Jev keys unset | `error` set, `available: false`; routing still picks; `attach` holds only the pre-route stack and domain floor | Jev failure never blocks routing |
| 11 | (simulate) a decision naming a skill in `agent` | `--finalize` moves it to `skill`, lists it in `problems` | section validator |
| 12 | "thanks" / "hi" / "say hello" / "what is 2+2" | Trivial per `/do` Phase 1: no dispatch, Phase 2 still runs | Trivial path |

**Known result (2026-09-22)**: case 6 resolves to `content`, not a deploy
skill. `pre-route.py` still matches it (the word "hosting" satisfies the
"make it public" companion-word gate); a non-safety force match is no longer
shown to the pick, so the session decides.

## Attachment eval (agent and skills per request)

`scripts/router_attachment/` holds 57 labeled requests (43 dev, 14 held-out
phrasings) with the acceptable agents, required skill groups, and forbidden
picks for each. `run_eval.py` measures `d-prepare` (the Jev evidence alone),
`d-model` (a model plays the `/d` session: it reads this SKILL.md, `/do`'s rule
text, and the manifest, then `--finalize` adds the attachments), and `do-model`
(a model applying `/do` to the manifest).
`scripts/tests/test_router_attachment_eval.py` replays recorded picks and Jev
evidence through the attachment policy offline.

Full attach = right agent, every required skill group, no forbidden pick.

| Run | Dev full attach | Dev skill recall / precision | Held-out full attach |
|---|---|---|---|
| `/d` v1.1 (d-model, 2026-09-22) | 0.558 | 0.667 / 0.731 | 0.429 |
| `/do` (do-model, 2026-09-22) | 0.837 | 0.933 / 1.000 | 1.000 |
| `/d` v1.2 (2026-09-22) | 0.930 | 0.933 / 0.948 | 0.929 |
| `/d` v1.3 keyword fixes and private gate (2026-09-23) | 0.953 | 0.956 / 0.964 | 1.000 |

| `/d` session pick (d-model, 2 runs, 2026-10-15) | 0.977, 0.977 | 1.000 / 0.969 | 1.000, 1.000 |

The first four rows are the Jev two-stage pick.

## Intent-alignment checks
- A proposed intent that drops material scope, adds unrequested work, or uses a
  route that visibly conflicts with the request must return `alignment: review`.
- The instruction gate must use the receipt produced for the exact runtime
  `PROPOSED_INTENT`. This is not hook enforcement, so tests must not claim a
  technical boundary that the implementation does not provide.
- Every route, including force-route and Trivial, must attempt runtime
  alignment.
- Essential ambiguity must return `clarification_needed: true`; routine
  implementation choices must not.
- A 429, 503, 529, or timeout from Vercel retries at most twice and persists a
  safe receipt; other gateway errors fail open.
- `auto` prefers Vercel, explicit transport selection never switches, and
  `direct` sends the same state and questions to the Jev API.

## Known failure modes
- The pick names a skill or agent not in the live manifest (renamed/deleted
  component) -> `--finalize` drops it and lists it in `problems`. Covered by
  `scripts/tests/test_jev_route_finalize.py`.
- Jev call exceeds timeout -> evidence stays empty and routing continues.
  Covered by the Vercel bridge retry receipt + `--timeout` flag.
- Missing Gateway bridge/HTTP-client dependency -> must not crash. Covered:
  `jev-route.py` uses the isolated Vercel bridge; the bridge package is
  installed by `install.sh`.
- Confidently-wrong pick on `paraphrase-security`/`false-positive-guard` — no
  runtime backstop exists for `false-positive-guard` (see
  `references/jev-classifier-design.md` "Confident-wrong risk"); caught only by
  the per-bucket `SAFETY_BUCKETS` gate on the full corpus run, not by any
  single-request check.
- `/do`'s rule text moves or loses a rule -> `print-route-rules.py` exits 1 or
  `scripts/tests/test_print_route_rules.py` fails.

## Full-corpus evidence

Do not cite a run unless its verdict exists in the repository and was produced
from the current corpus, manifest, and implementation. The measurement behind
the current design is summarized in `references/jev-classifier-design.md`.
Generate a fresh output directory with the command above when comparative
routing evidence is needed. Intent alignment is production functionality
established by repeated use; the corpus remains a regression tool for route
quality.
