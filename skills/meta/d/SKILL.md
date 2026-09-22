---
name: d
version: "1.1.0"
description: "Jev request router: validates the requested outcome, then dispatches to the matched agent, skill, and pipeline."
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

Classifies requests through Jev and dispatches to the matched
agent, skill, and pipeline. Before every dispatch, it restates the requested
outcome and uses Jev to check that the restatement and route preserve it.

The classification path has three layers: a deterministic `pre-route.py`
force-route guard (offline, runs first, authoritative for git/security), a
configured Jev transport presence check, and a two-stage classification — a cheap
wide-rank stage 1 over all manifest candidates plus a trivial-bypass gate,
then a full-detail shortlist-rerank stage 2 with per-candidate fit checks
and stack/fan-out signals.

Design rationale: `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md`.

### Phase Banners

Every phase: `/d > Phase N: PHASE_NAME — description...`
After intent alignment resolves: `===` routing banner. Both required.

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
`usage`, `agents`, `gate_score`, `fits_scores`, `stage1_shortlist`, and
`intent_alignment` (the hook-generated baseline alignment receipt).

`latency_ms` and `usage` are itemized dicts
(`{"stage1_ms","stage2_ms","total_ms"}` and `{"stage1","stage2"}`). Read
`.total_ms` for a single latency figure.

**Gate**: `fallback == true` → Phase 1F. Every matched result,
including `source == "jev-trivial-bypass"`, proceeds to Phase 2: ALIGN INTENT.

---

### Phase 1T: TRIVIAL-BYPASS (source == "jev-trivial-bypass")

Stage 1's gate fired: `gate_score` below threshold, no agent/skill/pipeline
is needed. It remains a direct-handling path, but it must still pass through
Phase 2 so the user outcome is restated and Jev validates it. After an
aligned Phase 2 result, show `Classification: Trivial` and
`Source: jev-trivial-bypass`, then answer or do the one-line action directly.
Do not run Phases 3–5 or call `build-dispatch.py`. Stop there.

---

### Phase 1F: UNAVAILABLE (fallback == true)

Jev could not classify this request. `JEV_RESULT.source` explains why:

- `unavailable` — neither configured Jev transport is available. `/d` accepts
  Vercel AI Gateway (`AI_GATEWAY_API_KEY`) or the direct Jev API
  (`TYPESAFE_API_KEY`), selected by `JEV_TRANSPORT=auto|vercel|direct`.
- `invalid-pick` — Jev's pick was not a valid manifest name.
- `error` — a Jev call timed out or failed.

Show:

```
===================================================================
 /d: Jev unavailable — [JEV_RESULT.fallback_reason]
 Use /do for manifest-based routing.
===================================================================
```

Fail open to `/do`'s full routing flow and continue the request. Do not reject
the request merely because Vercel AI Gateway is unavailable.

---

### Phase 2: ALIGN INTENT (required for every matched /d route)

**MANDATORY STOP:** For every matched `/d` invocation, write
`PROPOSED_INTENT` and run the validator on that exact text before any routing
banner, dispatch, answer, edit, or other action. `JEV_RESULT.intent_alignment`
is only the hook baseline and does not satisfy Phase 2. This requirement has no
exception for force routes, trivial routes, or an apparently aligned baseline.

Before selecting the work method, write `PROPOSED_INTENT`: a concise one- or
 two-sentence restatement of what the user wants accomplished. State the
outcome, material surfaces or deliverables, and every explicit constraint.
Do not describe the selected agent, skill, or implementation mechanics as the
outcome. Preserve the user's words where precision matters.

Run the Jev validator even when the hook already supplied
`JEV_RESULT.intent_alignment`; that receipt validates a conservative baseline,
while this call validates the actual restatement that will enter the task spec.
Put the request, route JSON, and proposed intent in temporary files rather
than shell-splicing user text, then call:

```bash
python3 "$SDIR/jev-intent-align.py" \
  --request-file "$REQUEST_FILE" \
  --route-file "$ROUTE_FILE" \
  --proposed-intent-file "$INTENT_FILE" \
  --json-compact
```

The validator sends one bounded state and all independent questions together
through the selected Jev transport. It checks whether the outcome and constraints
are preserved, the route can cover the material scope, the restatement is too
narrow, it introduces unrequested work, and essential clarification is needed.
It returns `aligned`, `clarification_needed`, `issues`, and raw `scores`.

Show this before the routing banner:

```
Intent alignment (/d):
  -> Restated outcome: [PROPOSED_INTENT]
  -> Jev: [aligned|review|unavailable] [issues, if any]
```

**Gate:**

- `clarification_needed == true` → ask one concise question that names the
  essential ambiguity; do not dispatch until answered.
- `alignment == aligned` and `source == jev-trivial-bypass` → direct handling
  in Phase 1T; otherwise → Phase 3.
- `alignment == review` because scope is lost, work was added, or the route
  cannot cover the request → correct `PROPOSED_INTENT` or the route and run
  this validator once more. Carry unresolved issues into `task_spec.gaps`; do
  not silently proceed as though Jev approved it.
- `alignment == unavailable` or `error` → state that validation was
  unavailable, preserve the verbatim request and proposed intent in the task
  spec, then continue under the normal `/d` routing result. Gateway outage
  must not become a false request rejection.

This runtime gate applies to every matched route, including force-routes and
trivial bypasses. A Phase 1 fallback cannot run this gate because no usable Jev
route exists; it fails open to `/do` as described in Phase 1F.

This is an instruction gate enforced by the `/d` contract, not a hook-enforced
technical boundary. The user remains the final backstop if an agent violates it.

---

### Phase 3: DECIDE (fallback == false, after aligned intent)

`JEV_RESULT.source` is either `pre-route-force` (deterministic guard matched)
or `jev` (Jev classification, manifest-validated).

Apply directly:

- `agent` / `skill` / `pipeline`: use `JEV_RESULT`'s values as-is. Already
  validated against the live manifest membership sets inside the script.
- `complexity`: use `JEV_RESULT.complexity` when set. When `null` (always for
  `pre-route-force`), default to `medium`, except a single one-line trivial
  fix → `simple`.
- Confidence: `JEV_RESULT.confidence` (`high`/`medium`/`low`).

**Routing banner** (Phase 2 intent block + routing block, both required, printed together):

```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================

 Intent (/d):
   -> Restated: [PROPOSED_INTENT]
   -> Alignment: [aligned|review|unavailable] [— issues, if any]

 Selected:
   -> Agent: [JEV_RESULT.agent] - [JEV_RESULT.reasoning]
   -> Skill: [JEV_RESULT.skill] - [JEV_RESULT.reasoning]
   -> Pipeline: [JEV_RESULT.pipeline, if set]
   -> Source: [JEV_RESULT.source] (confidence: [JEV_RESULT.confidence])

 Invoking...
===================================================================
```

The `Intent` block must be populated from the Phase 2 validator run. Printing
the banner with a placeholder or omitting the `Intent` block is a Phase 2 skip
and is not allowed.

**Gate**: Agent+skill set, banner shown. Phase 4.

---

### Phase 4: ENHANCE (stack signals)

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

**Gate**: Stack applied. Phase 5.

---

### Phase 5: EXECUTE

Build the task spec with `request_verbatim` unchanged and `intent` exactly
`PROPOSED_INTENT`; include any unresolved alignment issue in `gaps`, then invoke
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

### Post-execute: GRILL-JEV (plan/spec/design output)

After any execution that produces a plan, spec, or design artifact, run
`grill-jev` automatically before declaring the work complete. This applies
whenever the agent's output contains phases, steps, checklists, or a
structured implementation plan.

Detection: the agent wrote `task_plan.md`, a spec file, a design document,
or the response itself is a structured plan with numbered steps or phases.

```bash
# File artifact
python3 scripts/grill-jev.py --file task_plan.md --mode plan

# Inline plan (write to temp file first, then grill)
python3 scripts/grill-jev.py --file /tmp/plan_output.md --mode plan
```

Print the findings report. If high-signal findings exist (exit code 1):
- Show findings to the user
- Ask whether to address findings before proceeding or accept and move on

If no high-signal findings (exit code 0): proceed, note "grill-jev: clean".

Skip grill-jev when:
- The output is code only (no plan structure) — use `--mode code` instead
- The output is a pure research response with no actionable steps
- grill-jev is itself the requested action (avoid recursion)

---

## Error handling

Errors inside `jev-route.py` resolve to `fallback: true, source: "error"` —
Phase 1F reports the error and fails open to `/do`.

## References

- `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md` — request/response
  contract, fallback conditions, phase-by-phase design decisions
- `${CLAUDE_SKILL_DIR}/SPEC.md`, `${CLAUDE_SKILL_DIR}/EVAL.md` — maintenance
  contract and regression cases (load only when creating, evaluating, or
  redesigning this skill)
- `scripts/jev-route.py`, `scripts/jev-intent-align.py`, `scripts/jev_transport.py`, `scripts/jev_vercel.py`,
  `scripts/jev_gateway/jev_vercel_gateway.mjs`, `scripts/pre-route.py`,
  `scripts/routing-manifest.py`, `scripts/build-dispatch.py`
- Jev hook: `hooks/jev-route-injector-userprompt.py` (UserPromptSubmit) precomputes `JEV_RESULT`
