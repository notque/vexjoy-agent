# Router attachment eval

Measures whether `/d` and `/do` attach the right agent and skills to a request: the Go agent plus `programming` for Go work, `frontend` for UI work, `testing` when tests are part of the deliverable, `building-with-jev` for Jev programs, and so on.

## Files

| File | Purpose |
|---|---|
| `cases.json` | 57 labeled requests: 43 `dev`, 14 `ood` (held-out phrasings: informal, typos, Spanish, no trigger words) |
| `run_eval.py` | Runs one router over the cases, writes a fresh results JSON, and scores it |
| `intent-cases.json`, `intent_eval.py` | 18 labeled request/intent pairs for `scripts/jev_intent_align.py` |
| `fixtures/jev-answers-r2.json` | Recorded Jev answers the offline regression test replays |

## Labels

Each case lists:

- `agents`: acceptable primary agents (`*` accepts any). A null agent scores as `general-purpose`.
- `required`: skill groups; a group is met when any member is attached.
- `acceptable`: skills that may be attached without penalty.
- `forbid_agents`, `forbid_skills`: near-miss traps, for example `golang-general-engineer` on "go ahead and..." or `programming` on Python work.

Labels come from `agents/INDEX.json`, `skills/INDEX.json`, and each component's `not_for` text. `scripts/tests/test_router_attachment_eval.py` fails when a label names a component that no longer exists.

## Metrics

Attached skills are the primary `skill` plus `stack`, excluding shared patterns such as `anti-rationalization-core`.

| Metric | Definition |
|---|---|
| Agent accuracy | Primary agent is acceptable and not forbidden |
| Skill recall | Required groups met / required groups |
| Skill precision | Attached skills that are required or acceptable / attached skills |
| Full attach | Agent correct, every group met, no forbidden skill |

## Routers

| Router | What runs | Cost |
|---|---|---|
| `d-code` | `scripts/jev-route.py` per case (Jev through Vercel AI Gateway) | about 9k Jev tokens per case |
| `d-model` | `claude -p --model claude-opus-4-6 --tools ""` applies `skills/meta/d/SKILL.md` to recorded `d-code` output | about $0.065 per case |
| `do-model` | Same model applies `skills/meta/do/SKILL.md` to the routing manifest and the `pre-route.py` result | about $0.093 per case |

Model runs ask only for the build-dispatch routing JSON; nothing executes. The first call warms the prompt cache before the rest fan out.

```bash
OUT=/tmp/router-attach-$(date +%s)
python3 scripts/router_attachment/run_eval.py --router d-code --out $OUT/d-code.json --workers 2
python3 scripts/router_attachment/run_eval.py --router d-model --jev-results $OUT/d-code.json --out $OUT/d-model.json --workers 3
python3 scripts/router_attachment/run_eval.py --router do-model --out $OUT/do-model.json --workers 3
python3 scripts/router_attachment/intent_eval.py --out $OUT/intent.json
```

Use two `d-code` workers: three concurrent routes hit a burst of Gateway failures on 2026-09-22.

## Results (2026-09-22)

| Router | Dev agent / recall / precision / full | Held-out agent / recall / precision / full |
|---|---|---|
| `/d` v1.1, d-code | 0.744 / 0.667 / 0.974 / 0.558 | 0.571 / 0.562 / 0.846 / 0.429 |
| `/d` v1.1, d-model | 0.744 / 0.667 / 0.731 / 0.558 | 0.571 / 0.562 / 0.733 / 0.429 |
| `/do`, do-model | 0.907 / 0.933 / 1.000 / 0.837 | 1.000 / 1.000 / 1.000 / 1.000 |
| `/d` v1.2, d-code and d-model | 0.977 / 0.933 / 0.948 / 0.930 | 1.000 / 0.938 / 0.905 / 0.929 |

## Results (2026-09-23): keyword fixes and private-skill gate

Changes: trigger last words take plain inflections only ("write post" no longer matches PostToolUse or Postgres); plain "review my changes" routes to `review`; "ship it" only suggests `pr-workflow` inside a later clause ("before I ship it"); private overlay skills are candidates only when the request names their domain; `ui-frontend-engineer` renamed `ui-design-engineer`.

| Router | Dev agent / recall / precision / full | Held-out agent / recall / precision / full |
|---|---|---|
| `/d` before, d-code | 0.977 / 0.933 / 0.945 / 0.930 | 0.929 / 0.875 / 0.900 / 0.857 |
| `/d` before, d-model | 0.977 / 0.933 / 0.945 / 0.930 | 1.000 / 0.938 / 0.905 / 0.929 |
| `/d` after, d-code and d-model | 0.977 / 0.956 / 0.964 / 0.953 | 1.000 / 1.000 / 1.000 / 1.000 |
| `/do` before, do-model (2 held-out runs) | 0.930 / 0.889 / 1.000 / 0.814 | full 0.929, 0.786 |
| `/do` after, do-model (2 held-out runs) | 0.907 / 0.889 / 1.000 / 0.791 | full 0.500, 0.714 |

Private skills sat in the `/d` stage-1 skill shortlist on 40 of 57 requests before and 0 after. Gateway failures were retried per case; one baseline held-out case (`ood-k8s-01`) failed twice and scores as a miss. `/do` differences fall on requests whose pre-route input and manifest text are unchanged apart from the agent rename, and a rerun of the unchanged baseline moved held-out full attach from 0.929 to 0.786, so they are run-to-run model variance. The one `/do` held-out input that changed (`ood-go-04`, "before I ship it") routed correctly in every run.

`d-model` v1.1 precision falls below `d-code` because the model added skill names that no longer exist (`test-driven-development`, `parallel-code-review`), which `build-dispatch.py` rejects. Changes and the decision card: `skills/meta/d/references/jev-classifier-design.md`, "Attachment step".
