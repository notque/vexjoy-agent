# 009: retire the 44 repo agents; give /d the single-loop setup

Owner decisions (2026-11-17, after reading Anthropic's "When to fold subagents
into your main agent loop"):

- Keep `/do`. Skills don't load reliably on demand, so the router stays.
- Keep pipelines. A pipeline makes the same specific actions happen every time.
- Retire all 44 repo agents (43 indexed plus `base-instructions.md`) in both
  routers. It's a straight retire, not an experiment. What each agent did moves
  into a skill and its references.
- Review the metrics and make sure they're good.
- `/d` gets the article's setup as the comparison arm: main loop by default,
  hard rules in tools, a prompt audit, and skill-load metrics plus a golden
  eval set. It keeps Jev for its current jobs. The owner judges which is better.

## Agent to skill mapping

The agent body moves to `<skill>/references/<slug>.md`, and the agent's
`agents/<name>/references/*` move to `<skill>/references/<slug>/`.

| Lane | Destination skill | Agents (slug = agent name without `-engineer`) |
|---|---|---|
| L1 | `skills/programming/programming` | golang-general, python-general, rust-general, kotlin-general, swift-general, php-general, typescript-debugging, python-openstack, mcp-local-docs, nodejs-api (moved in cleanup) |
| L2 | `skills/frontend/frontend` | typescript-frontend, ui-design, react-portfolio, nextjs-ecommerce, react-native, performance-optimization |
| L2 | `skills/game/game-dev` | pixijs-combat-renderer, rive-skeletal-animator, combat-effects-upgrade |
| L3 | `skills/infrastructure/kubernetes` | kubernetes-helm, ansible-automation, prometheus-grafana, opensearch-elasticsearch, rabbitmq-messaging, perses |
| L3 | `skills/analysis/data` | data-engineer, database-engineer, sqlite-peewee |
| L3 | `skills/process/testing` | testing-automation |
| L4 | `skills/review/review` | reviewer-code, reviewer-domain, reviewer-perspectives, reviewer-system |
| L4 | `skills/research/research` | research-coordinator, research-subagent-executor |
| L4 | `skills/process/workflow` | project-coordinator, pipeline-orchestrator |
| L4 | `skills/meta/toolkit` | toolkit-governance, system-upgrade, hook-development, github-profile-rules |
| L4 | `skills/content/writing` | technical-journalist-writer, technical-documentation |
| L5 | `skills/shared-patterns/base-instructions.md` | base-instructions |

## Dispatch after retirement

- No specialist agent slot. Routing picks skill, pipeline and stack.
- When dispatch pays, the worker is the built-in `general-purpose` agent and the
  skill carries the domain. The `[do-route]` marker keeps `agent=` (`main` or
  `general-purpose`) so the learning DB schema doesn't change.
- Private overlay agents (the resolved agents index minus retired and built-in
  names) are not retired: the manifest lists them in an overlay-only `AGENTS:`
  section when the request names their domain, and `/do` or `/d` (reason
  `overlay-agent`) may dispatch one as the worker.

## Lanes

- L1-L4: content migration, one lane per destination-skill group, no shared files.
- L5: router core for agent retirement (`/do`, shared scripts, hooks, tests, docs).
- L6 (after L5): `/d` single-loop setup, metrics review, golden eval set.

## L6: what was built

`/d` is the single-loop arm. `/do` keeps its behaviour: its `build-dispatch.py`
output is byte-identical (every `/d` rule sits behind `"router": "d"`).

| | `/do` | `/d` (v3.0) |
|---|---|---|
| Where the work runs | Trivial and Simple in the main thread; Medium and Complex on `general-purpose` workers | main loop for every complexity |
| When it dispatches | Medium+, fan-out, long lanes, worktree, Haiku gathering | only `fan-out`, `worktree`, `haiku-gather`, `verifier`, `overlay-agent`, each with a checked precondition |
| Worker handover | skill Skill-tool calls | skill calls plus required `references` from the skill's `references/` |
| Pipelines | phases dispatched per workflow-dispatch | phases run in order in the main loop; only fan-out or verifier phases leave |
| Intent gate | none | Jev receipt required by the execute step (tool-enforced, fail-open on Jev outage) |
| Marker | `[do-route] ...` | same plus `reason=<r>` and `router=d` |

Built:

- `scripts/d_gate.py`: receipt write/check (session-scoped temp dir, hashes
  only, 0600, 6-hour life), dispatch-reason enum and preconditions, reference
  resolution. `jev_intent_align.py` writes the receipt on every path.
- `scripts/build-dispatch.py` `"router": "d"` mode: main-loop default, gates,
  reference line in the worker preamble, pipeline in-order note, `router=d`
  and `reason=` marker tokens before `exec=main`.
- `hooks/routing-decision-recorder.py` (telemetry hook, not a safety hook):
  parses `router=` and `reason=` into `route-events.jsonl` and a `router:d`
  tag. No SQLite schema change.
- `scripts/router-metrics.py`: per-router main/dispatch share, dispatch
  reasons, pipeline rate, skill-load accuracy, with timestamps.
- `scripts/learning-db.py` query fixes: `route-health` drops bookkeeping rows
  from its denominator; `route-stats --by errors` reads the recorder's token
  shape; `--by force-route|override` say "not instrumented"; `handoff-report`
  excludes main-thread rows.
- `skills/meta/d/SKILL.md` v3.0 (17,616 to 13,353 bytes), SPEC, EVAL,
  `references/jev-classifier-design.md`, `references/router-metrics.md`.
- `scripts/golden_eval/`: 14 frozen tasks, fixture repo, routing runner (run:
  `scripts/routing-ab-results/d-single-loop-v1/`), end-to-end runner (built,
  not launched).
- Tests: `test_d_gate.py`, `test_router_metrics.py`, `test_golden_eval.py`,
  recorder and route-stats cases.
