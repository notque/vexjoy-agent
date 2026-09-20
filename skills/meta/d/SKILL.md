---
name: d
version: "1.2.1"
description: "Jev request router: classify requests, then dispatch the manifest-validated agent, skill, pipeline, and stack."
user-invocable: true
argument-hint: "[request]"
allowed-tools: [Read, Bash, Grep, Glob, Skill, Task]
routing:
  triggers: [jev router, route with jev, use the d router]
  not_for: "Direct task execution; /d classifies and dispatches."
  category: meta-tooling
---

# /d — Jev router

`scripts/jev-route.py` owns classification. Its deterministic `pre-route.py` guard is authoritative for git/security; otherwise Jev performs wide ranking plus trivial gate, then detailed shortlist reranking with fitness and fan-out heads. The script validates every selected name against the live manifest.

Show each phase as `/d > Phase N: NAME — description...`. Show the routing banner after classification resolves.

## 1. CLASSIFY

Use an injected `JEV_RESULT` when present; otherwise place the verbatim request in a temporary file and run:

```bash
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
```

Resolve `$SDIR` from the active harness scripts directory (`.claude`, `.hermes`, `.factory`, `.codex`, `.reasonix`), then repository `scripts/`.

Action-changing fields are `fallback`, `fallback_reason`, `agent`, `skill`, `pipeline`, `complexity`, `confidence`, `reasoning`, `source`, `stack`, `signals`, and `agents`. See `references/jev-classifier-design.md` for the full receipt.

If `fallback` is true, print the reason and fail open to `/do`'s complete routing flow. Never reject a task because Jev is unavailable, errored, or returned an invalid manifest pick.

If `source == jev-trivial-bypass`, print `Classification: Trivial` and the source, handle the request directly, and stop before stack/dispatch. Do not call `build-dispatch.py`.

## 2. DECIDE

Use returned agent/skill/pipeline unchanged. Use returned complexity; a force route with null complexity defaults to `medium`, except a single one-line fix is `simple`. Show the routing banner with selections, reasoning, source, and confidence before invocation.

## 3. ENHANCE

Apply script-produced stack plus these signal mappings:

| Signal | Addition |
|---|---|
| `tests_requested` | `test-driven-development`, `verification-before-completion` |
| `research_needed` | `research-coordinator-engineer` fan-out |
| `comprehensive_review` | `parallel-code-review`, unless `right-size-review.py` selects real multi-file review |
| `local_only` | `shared-patterns/local-only.md` |
| `objective_loop_worthy` | `objective-loop` |

`anti-rationalization-core` always rides. Preserve nonempty force-route stack. Union and deduplicate `JEV_RESULT.agents`; dispatch fan-out agents in parallel with the primary.

## 4. EXECUTE

Call `build-dispatch.py` with manifest names, selected complexity, `model: inherit`, `context_mode: summary`, provider, stack, flags, and a task spec containing:

- `request_verbatim`: unchanged user request;
- `intent`: the requested outcome and constraints;
- constraints/authorization, decisions, gaps, acceptance, files/ownership, operator context;
- `fallback_reason` whenever agent is `general-purpose`.

The builder validates names and emits the action. Apply its creation, plan-file, quality-loop, workflow, fan-out, and pipeline gates for complex/creation work. Deliver invoked-agent results.

Maintenance contracts and regression cases are in `SPEC.md` and `EVAL.md`; load them only when changing or evaluating this router.
