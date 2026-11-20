# Router metrics after agent retirement (plans/009 L6)

Load when comparing `/do` and `/d`, or before quoting a routing figure. Every
figure is a dated observation: rerun the command before quoting it.

## What each metric means now

The 44 specialist agents are retired. Every route runs on the main thread
(`agent=main`) or on a `general-purpose` worker, and the skill carries the
domain. Metrics that scored the agent pick lost their meaning.

| Metric | Source | Status | Why |
|---|---|---|---|
| `route-health` outcome coverage, basis split, silent-success share | `learnings`, `routing_outcome_basis` | Kept, fixed | Bookkeeping rows (`stack-usage:`, `fallback-reason:`) no longer count as routes; they never get an outcome and inflated the no-outcome share (43 of 133 rows on 2026-11-17). |
| Fallback rate | `fallback-reason:invalid-agent:*` rows | Kept (L5 redefined it) | Now counts coerced agent names only. Near 0 by design. |
| `general-purpose` share | `evidence_route_decisions.agent` | Retired as a quality signal | About 100% of dispatches by design. Read `agent` as main vs dispatch instead. |
| Skill concentration, skill entropy | `evidence_route_decisions.skill` | Kept | The skill is the routing choice that remains. |
| Route-fit verdicts | `routing_outcome_basis` `route_fit:*` | Kept for dispatches only | A main-loop route has no worker reply, so it has no verdict. `wrong-agent` is retired. Not comparable across routers with different dispatch shares. |
| `tool_errors` per route | recorder value token | Kept for dispatches only | Main-loop routes record no Agent result. Not comparable across routers. |
| `route-stats --by errors` | recorder value token | Fixed | It read ` | ` pairs the recorder stopped writing; it now reads `tool_errors=1`. |
| `route-stats --by force-route`, `--by override` | none | Retired (prints "not instrumented") | No writer has recorded `force_used` or `llm_override` in the current value shape: 0 rows. |
| `handoff-report` spec score | `evidence_route_decisions.spec_score` | Kept, fixed | Main-thread rows are excluded: their prompt is the bare marker, so they always scored 0 (6 of 6 rows). |
| Health / alts / action tokens | marker | Retired earlier (`docs/route-loop-validation.md`) | Unchanged. |

## Per-router metrics (new)

`python3 scripts/router-metrics.py [--since <date>] [--json]` reads
`route-events.jsonl` and `usage.db`, read-only, and splits by router. A `/d`
marker carries `router=d`; no token means `/do`. Before L6 `/d` emitted no
router token, so start comparisons at `--since` the install date.

| Metric | Definition |
|---|---|
| `main_share` / `dispatch_share` | decisions with `agent=main` / with a worker |
| `dispatch_reasons` | `/d` `reason=` token per dispatch (`fan-out`, `worktree`, `haiku-gather`, `verifier`, `overlay-agent`, `context-budget`); `/do` dispatches read `unstated` |
| `pipeline_rate` | decisions whose marker carries `pipeline=` |
| `verify` | `/d` main routes marked `verify=required`, and how many saw a `reason=verifier` dispatch later in the same session |
| `skill_load.main` | main-loop decisions where the session called the Skill tool with the routed skill within -2 to +30 minutes |
| `skill_load.dispatch` | same for dispatches; a lower bound, because a worker's Skill calls mostly do not land under the parent session (29 of 329 observed on 2026-11-17) |

Compare `skill_load.main` across routers, not the pooled rate: a main-heavy
router would win the pooled number on observability alone.

## Golden eval

`scripts/golden_eval/` holds 14 tasks shaped on the owner's routed work, each
with acceptable skills and pipelines, required skill groups, forbidden skills,
allowed `/d` dispatch reasons, a rubric, and (for 6 tasks) acceptance checks on
a fixture repo.

| Level | Command | Cost |
|---|---|---|
| Routing (each task twice per router, same model) | `nice -n 10 python3 scripts/golden_eval/run_routing.py --out-dir scripts/routing-ab-results/<new> --runs 2` | about $0.2 per routing call on opus, about 1k Jev tokens per `/d` call |
| End to end (real sessions, acceptance checks, rubric grade, skill-load from the stream) | `nice -n 10 python3 scripts/golden_eval/run_e2e.py --out-dir <new> --runs 2 --launch` | `run_e2e.py --estimate`; needs this branch installed |

Count a task as changed between arms only when both runs of each arm agree.
