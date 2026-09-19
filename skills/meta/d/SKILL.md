---
name: d
version: "1.0.0"
description: "Jev-powered request router: classifies via TypeSafe's Jev API, then dispatches to the matched agent, skill, and pipeline."
user-invocable: true
argument-hint: "[request]"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "jev router"
    - "route with jev"
    - "use the d router"
  not_for: "General-purpose task execution — /d classifies and dispatches, it does not perform the work itself."
  category: meta-tooling
---

# /d — Jev Router

Classifies requests via TypeSafe's Jev API and dispatches to the matched
agent, skill, and pipeline. One API call replaces reading the full routing
manifest into context.

The classification path has three layers: a deterministic `pre-route.py`
force-route guard (offline, runs first, authoritative for git/security), a
TypeSafe presence check, and a two-stage Jev classification — a cheap
wide-rank stage 1 over all manifest candidates plus a trivial-bypass gate,
then a full-detail shortlist-rerank stage 2 with per-candidate fit checks
and stack/fan-out signals.

Design rationale: `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md`.

### Phase Banners

Every phase: `/d > Phase N: PHASE_NAME — description...`
After Phase 1 resolves: `===` routing banner. Both required.

---

### Phase 1: CLASSIFY

`scripts/jev-route.py` owns the entire classification in one subprocess call.

When `JEV_RESULT` is already in context (the `jev-route-injector` hook ran the script before your first token), use it and skip the command below.

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
rm -f "$REQUEST_FILE"
```

Resolve `$SDIR`: `${HOME}/.claude/scripts`, falling back through
`.hermes`/`.factory`/`.codex`/`.reasonix`, or the repo's `scripts/`
directory.

Hold the result as `JEV_RESULT`. Shape (stable — see design reference for
full schema):

`available`, `jev_called`, `matched`, `fallback`, `fallback_reason`,
`agent`, `skill`, `pipeline`, `complexity`, `confidence`, `match_type`,
`reasoning`, `stack`, `signals`, `signal_scores`, `source`, `latency_ms`,
`usage`, `agents`, `gate_score`, `fits_scores`, `stage1_shortlist`.

`latency_ms` and `usage` are itemized dicts
(`{"stage1_ms","stage2_ms","total_ms"}` and `{"stage1","stage2"}`). Read
`.total_ms` for a single latency figure.

**Gate**: `source == "jev-trivial-bypass"` → Phase 1T.
`fallback == true` → Phase 1F (stop). Otherwise → Phase 2.

---

### Phase 1T: TRIVIAL-BYPASS (source == "jev-trivial-bypass")

Stage 1's gate fired: `gate_score` below threshold, no agent/skill/pipeline
needed. Terminal state (`matched: true`, `fallback: false`). Show the routing
banner with `Classification: Trivial` and `Source: jev-trivial-bypass`, then
handle the request directly — answer the question, do the one-line action.
Do not run Phase 3 or Phase 4; do not call `build-dispatch.py`. Stop here.

---

### Phase 1F: UNAVAILABLE (fallback == true)

Jev could not classify this request. `JEV_RESULT.source` explains why:

- `unavailable` — TypeSafe not configured (missing `TYPESAFE_API_KEY` or
  plugin disabled).
- `invalid-pick` — Jev's pick was not a valid manifest name.
- `error` — a Jev call timed out or failed.

Show:

```
===================================================================
 /d: Jev unavailable — [JEV_RESULT.fallback_reason]
 Use /do for manifest-based routing.
===================================================================
```

Stop here. Do not attempt the request.

---

### Phase 2: DECIDE (fallback == false, not trivial-bypass)

`JEV_RESULT.source` is either `pre-route-force` (deterministic guard
matched, Jev not called) or `jev` (Jev classification, manifest-validated).

Apply directly:

- `agent` / `skill` / `pipeline`: use `JEV_RESULT`'s values as-is. Already
  validated against the live manifest membership sets inside the script.
- `complexity`: use `JEV_RESULT.complexity` when set. When `null` (always for
  `pre-route-force`), default to `medium`, except a single one-line trivial
  fix → `simple`.
- Confidence: `JEV_RESULT.confidence` (`high`/`medium`/`low`).

**Routing banner** (first visible output):

```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================
 Selected:
   -> Agent: [JEV_RESULT.agent] - [JEV_RESULT.reasoning]
   -> Skill: [JEV_RESULT.skill] - [JEV_RESULT.reasoning]
   -> Pipeline: [JEV_RESULT.pipeline, if set]
   -> Source: [JEV_RESULT.source] (confidence: [JEV_RESULT.confidence])
 Invoking...
===================================================================
```

Always include `Source:` — it distinguishes a Jev decision from a force-route
match.

**Gate**: Agent+skill set, banner shown. Phase 3.

---

### Phase 3: ENHANCE (stack signals)

`JEV_RESULT.signals` (booleans at 0.6 confidence threshold, computed by the
script) map to stack entries:

| Signal true | Stack |
|---|---|
| `tests_requested` | `test-driven-development` + `verification-before-completion` |
| `research_needed` | add `research-coordinator-engineer` to agents (fan-out) |
| `comprehensive_review` | `parallel-code-review` (drop if a real multi-file diff exists — `right-size-review.py` outranks it) |
| `local_only` | inject `shared-patterns/local-only.md` |
| `objective_loop_worthy` | `objective-loop` |

`anti-rationalization-core` always rides. When `source` is
`pre-route-force` and `JEV_RESULT.stack` is non-empty (e.g. `go-patterns`),
keep it.

**Fan-out agents**: union `JEV_RESULT.agents` (script-computed fan-out picks,
each passed its per-candidate fit check) into the `research_needed` agent
list, deduped. Dispatch fan-out agents as separate parallel `Agent` tool
calls alongside the primary `build-dispatch.py` dispatch.

**Gate**: Stack applied. Phase 4.

---

### Phase 4: EXECUTE

Build the task spec (request_verbatim unchanged; intent, constraints, files,
ownership, acceptance filled from this turn's context), then invoke
`build-dispatch.py`:

```bash
python3 "$SDIR/build-dispatch.py" --json '{
  "agent": "<JEV_RESULT.agent>", "skill": "<JEV_RESULT.skill; omit when agent-only>",
  "pipeline": "<JEV_RESULT.pipeline; omit when null>",
  "complexity": "<from Phase 2>",
  "model": "inherit",
  "context_mode": "summary",
  "provider": "<anthropic|openai|other>",
  "manual_model_override": false,
  "health": "-",
  "fallback_reason": "<REQUIRED when agent=general-purpose; omit otherwise>",
  "stack": ["s1","s2"],
  "task_spec": {"request_verbatim": "<user message, unchanged>", "intent": "...",
                "constraints": "<applicable rules, limits, and authorization>",
                "decisions": "...",
                "gaps": "...",
                "acceptance": "<command> -> <expected>",
                "files": "<owned paths; optional line ranges>", "ownership": "<worker scope>",
                "operator_context": "..."},
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}'
```

The builder validates each name against its index, then emits the dispatch
action. For Complex or creation requests, apply creation detection, plan-file
gating, quality-loop, workflow dispatch, fan-out, and auto-pipeline fallback.

**Gate**: Agent invoked, results delivered.

---

## Error handling

Errors inside `jev-route.py` resolve to `fallback: true, source: "error"` —
Phase 1F reports the error and stops.

## References

- `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md` — request/response
  contract, fallback conditions, phase-by-phase design decisions
- `${CLAUDE_SKILL_DIR}/SPEC.md`, `${CLAUDE_SKILL_DIR}/EVAL.md` — maintenance
  contract and regression cases (load only when creating, evaluating, or
  redesigning this skill)
- `scripts/jev-route.py`, `scripts/jev_router_common.py`, `scripts/pre-route.py`,
  `scripts/routing-manifest.py`, `scripts/build-dispatch.py`
- Jev hook: `hooks/jev-route-injector-userprompt.py` (UserPromptSubmit) precomputes `JEV_RESULT`
