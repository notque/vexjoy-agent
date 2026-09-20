---
name: d
version: "1.2.0"
description: "Jev request router: validate intent, then dispatch the manifest-validated agent, skill, pipeline, and stack."
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

Show each phase as `/d > Phase N: NAME — description...`. Intent validation must appear before the routing banner.

## 1. CLASSIFY

Use an injected `JEV_RESULT` when present; otherwise place the verbatim request in a temporary file and run:

```bash
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
```

Resolve `$SDIR` from the active harness scripts directory (`.claude`, `.hermes`, `.factory`, `.codex`, `.reasonix`), then repository `scripts/`.

Action-changing fields are `fallback`, `fallback_reason`, `agent`, `skill`, `pipeline`, `complexity`, `confidence`, `reasoning`, `source`, `stack`, `signals`, `agents`, and `intent_alignment`. See `references/jev-classifier-design.md` for the full receipt.

If `fallback` is true, print the reason and fail open to `/do`'s complete routing flow. Never reject a task because Jev is unavailable, errored, or returned an invalid manifest pick.

## 2. ALIGN INTENT — mandatory matched-route gate

Before any banner, dispatch, answer, or edit, write `PROPOSED_INTENT`: one or two sentences preserving the requested outcome, deliverables/surfaces, and every explicit constraint. It describes the outcome, not route mechanics.

The hook's baseline `intent_alignment` never satisfies this gate. Put request, route JSON, and proposed intent in separate temporary files and run:

```bash
python3 "$SDIR/jev-intent-align.py" \
  --request-file "$REQUEST_FILE" --route-file "$ROUTE_FILE" \
  --proposed-intent-file "$INTENT_FILE" --json-compact
```

Print the restated outcome and Jev status. Then:

- `clarification_needed`: ask one question naming the essential ambiguity; do not dispatch.
- aligned trivial bypass (`source == jev-trivial-bypass`): print `Classification: Trivial` and the source, handle directly, and stop before stack/dispatch.
- review due to lost/added scope or route mismatch: correct intent/route and validate once more; unresolved issues go in `task_spec.gaps`.
- unavailable/error: state validation was unavailable, retain verbatim request and proposed intent in the spec, and continue with the classification.

Phase-1 fallback cannot align because it has no usable Jev route; `/do` takes over.

## 3. DECIDE

Use returned agent/skill/pipeline unchanged. Use returned complexity; a force route with null complexity defaults to `medium`, except a single one-line fix is `simple`. Show the routing banner with selections, reasoning, source, and confidence before invocation.

## 4. ENHANCE

Apply script-produced stack plus these signal mappings:

| Signal | Addition |
|---|---|
| `tests_requested` | `test-driven-development`, `verification-before-completion` |
| `research_needed` | `research-coordinator-engineer` fan-out |
| `comprehensive_review` | `parallel-code-review`, unless `right-size-review.py` selects real multi-file review |
| `local_only` | `shared-patterns/local-only.md` |
| `objective_loop_worthy` | `objective-loop` |

`anti-rationalization-core` always rides. Preserve nonempty force-route stack. Union and deduplicate `JEV_RESULT.agents`; dispatch fan-out agents in parallel with the primary.

## 5. EXECUTE

Call `build-dispatch.py` with manifest names, selected complexity, `model: inherit`, `context_mode: summary`, provider, stack, flags, and a task spec containing:

- `request_verbatim`: unchanged user request;
- `intent`: exact `PROPOSED_INTENT`;
- constraints/authorization, decisions, gaps, acceptance, files/ownership, operator context;
- `fallback_reason` whenever agent is `general-purpose`.

The builder validates names and emits the action. Apply its creation, plan-file, quality-loop, workflow, fan-out, and pipeline gates for complex/creation work. Deliver invoked-agent results.

Maintenance contracts and regression cases are in `SPEC.md` and `EVAL.md`; load them only when changing or evaluating this router.
