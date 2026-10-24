---
name: d
version: "2.0.0"
description: "Request router: picks the agent, skill, and pipeline with /do's rules, then uses Jev to validate the requested outcome and attach extra skills."
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

Routes a request in four parts. A deterministic `pre-route.py` guard keeps
git/PR and security work on their quality gates. You, the session model, pick
the agent, skill, and pipeline from the full routing manifest with `/do`'s rule
text. Jev answers the attachment questions that add extra skills, and validates
that the restated outcome survives the route. A script validates your pick and
computes the attachments.

Design rationale: `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md`.

### Phase Banners

Every phase: `/d > Phase N: PHASE_NAME — description...`
After intent alignment resolves: `===` routing banner. Both required.

---

### Phase 1: CLASSIFY

Resolve `$SDIR`: `${HOME}/.claude/scripts`, falling back through
`.gemini`/`.hermes`/`.factory`/`.codex`/`.reasonix`, or the repo's `scripts/`
directory.

**Step 1 — JEV_RESULT.** When `JEV_RESULT` is already in context (the
`jev-route-injector` hook ran the script before your first token), use it and
skip the command below.

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
```

Fields: `available`, `jev_called`, `source`, `forced`, `stack`, `project`,
`signals`, `signal_scores`, `domain_scores`, `error`, `latency_ms`, `usage`.
`forced` is the safety force route (`pr-workflow`, `pr-pipeline`, `security`)
or `null`. `project` holds the request repository's languages, frameworks, and
datastores (names only) or `null`. `error` is set when Jev was unavailable or
its answers were unusable. Routing continues, and `attach` then carries only
the pre-route stack and the agent domain floor.

**Step 2 — Pick.** Set the complexity from `/do` Phase 1 (Trivial, Simple,
Medium, Complex). Trivial: go to Phase 1T.

For Simple and above, load `/do`'s routing rules and the manifest. Read the rule
text in full and apply every rule:

```bash
python3 "$SDIR/print-route-rules.py"
bash "$SDIR/get-routing-manifest.sh" --request-file "$REQUEST_FILE"
```

The manifest is large. If Bash truncates it or saves it to a file, read the
whole file before you pick. Use `JEV_RESULT.project` when the request names no
language or framework.

Return the decision as JSON. Do not print it:

```
{"agent": "<AGENTS: name or null>", "agents": ["<extra fan-out agents>"],
 "skill": "<SKILLS: name or null>", "pipeline": "<PIPELINES: name or null>",
 "complexity": "simple|medium|complex", "confidence": "high|medium|low",
 "reasoning": "<one sentence>",
 "fallback_reason": "general-purpose: <why no listed agent covers this>"}
```

`fallback_reason` is required when `agent` is `general-purpose`, and only then.

When `JEV_RESULT.forced` is set, its `skill` and `pipeline` are final: step 3
overrides your values for them. Pick the `agent` and `agents` that fit, as
`/do` Phase 2 Step 1(a) does.

**Step 3 — Finalize.** Write `JEV_RESULT` and the decision to temporary files
and run:

```bash
python3 "$SDIR/jev-route.py" --finalize --result-file "$RESULT_FILE" --decision-file "$DECISION_FILE" --json-compact
rm -f "$REQUEST_FILE" "$RESULT_FILE" "$DECISION_FILE"
```

Hold the output as `ROUTE`: `agent`, `agent_source`, `skill`, `skill_source`,
`pipeline`, `agents`, `attach`, `stack`, `complexity`, `confidence`,
`reasoning`, `fallback_reason`, `source`, `signals`, `domain_scores`, and
`problems`. The script checks every name against the live manifest, applies the
safety force route, fills an empty skill with `workflow`, and gives a null or
`general-purpose` agent the owning agent of the skill. `attach` is the list of
extra skills that ride with `skill` (for example `programming` for Go work,
`testing` when tests are part of the work). It is the whole Phase 4 stack.

**Gate**: `problems` empty → Phase 2. `problems` set → fix the decision, run
step 3 once more, and carry any problem that remains into `task_spec.gaps`. The
output has an `error` key and no route fields → use your decision as `ROUTE`
with `attach` set to `[]`.

---

### Phase 1T: TRIVIAL (complexity == Trivial)

Direct-handling path. It still goes through Phase 2 so the user outcome is
restated and Jev validates it; use `{"complexity": "trivial"}` as the route
file. After an aligned Phase 2 result, show `Classification: Trivial`, then
answer or do the one-line action directly. Do not run Phases 3–5 or call
`build-dispatch.py`. Stop there.

---

### Phase 2: ALIGN INTENT (required for every /d route)

**MANDATORY STOP:** For every `/d` invocation, write `PROPOSED_INTENT` and run
the validator on that exact text before any routing banner, dispatch, answer,
edit, or other action. This requirement has no exception for force routes or
trivial routes.

Before selecting the work method, write `PROPOSED_INTENT`: a concise one- or
two-sentence restatement of what the user wants accomplished. State the
outcome and each deliverable the request names or directly requires. Copy
every explicit constraint in the user's words: limits ("only", "at most"),
exclusions ("don't touch", "do not deploy"), required methods, and
authorization boundaries. Do not add deliverables the user did not ask for,
such as extra tests, docs, cleanup, refactors, or verification steps. Do not
add notes about missing inputs or preconditions; the validator decides
whether clarification is needed. Do not describe the selected agent, skill,
or implementation mechanics as the outcome. Preserve the user's words where
precision matters.

Put the request, the `ROUTE` JSON, and the proposed intent in temporary files
rather than shell-splicing user text, then call:

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
- `alignment == aligned` and complexity is Trivial → direct handling in
  Phase 1T; otherwise → Phase 3.
- `alignment == review` because scope is lost, work was added, or the route
  cannot cover the request → correct `PROPOSED_INTENT` or the route and run
  this validator once more. Carry unresolved issues into `task_spec.gaps`; do
  not silently proceed as though Jev approved it.
- `alignment == unavailable` or `error` → state that validation was
  unavailable, preserve the verbatim request and proposed intent in the task
  spec, then continue under the `ROUTE` result. Gateway outage must not
  become a false request rejection.

This is an instruction gate enforced by the `/d` contract, not a hook-enforced
technical boundary. The user remains the final backstop if an agent violates it.

---

### Phase 3: DECIDE (after aligned intent)

Use `ROUTE`'s `agent`, `skill`, `pipeline`, and `complexity` as-is. The script
validated them against the live manifest. `agent_source: skill-default` means
the pick named no domain agent and the script used the skill's owning agent. A
`general-purpose` agent carries `ROUTE.fallback_reason`. When `complexity` is
`null`, use `medium`, except a single one-line trivial fix → `simple`.

**Routing banner** (Phase 2 intent block + routing block, both required, printed together):

```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================

 Intent (/d):
   -> Restated: [PROPOSED_INTENT]
   -> Alignment: [aligned|review|unavailable] [— issues, if any]

 Selected:
   -> Agent: [ROUTE.agent] - [ROUTE.reasoning]
   -> Skill: [ROUTE.skill] - [ROUTE.reasoning]
   -> Attached: [ROUTE.attach, comma-separated, or "none"]
   -> Pipeline: [ROUTE.pipeline, if set]
   -> Source: [ROUTE.source] (confidence: [ROUTE.confidence])

 Invoking...
===================================================================
```

The `Intent` block must be populated from the Phase 2 validator run. Printing
the banner with a placeholder or omitting the `Intent` block is a Phase 2 skip
and is not allowed.

**Gate**: Agent+skill set, banner shown. Phase 4.

---

### Phase 4: ENHANCE (attach skills)

`stack` = `ROUTE.attach`, in order, plus `anti-rationalization-core`.
Copy the names exactly. Do not add, rename, or drop skills: the script built
`attach` from these rules, and `build-dispatch.py` rejects any name absent
from `skills/INDEX.json`.

| Source | Attaches |
|---|---|
| `JEV_RESULT.stack` (pre-route, e.g. a `.go` file with PR or security work) | its entries, first |
| Agent domain floor | `programming` for Go, Kotlin, PHP, and Swift agents; `kubernetes` for `kubernetes-helm-engineer`; `frontend` for `ui-design-engineer` |
| `domain_scores` at 0.6 or higher | `programming`, `frontend`, `kubernetes`, `testing`, `building-with-jev`, `research` |
| `tests_requested` / `comprehensive_review` / `objective_loop_worthy` | `testing` / `review` / `workflow` |
| `local_only` | `local-only` shared pattern |

At most three skills are attached beyond `skill`. Two adjustments stay with
you:

- `comprehensive_review` attached `review` and a real multi-file diff
  exists: `right-size-review.py` outranks it, so drop `review` from `stack`.
- `signals.research_needed` is true: add `research-coordinator-engineer`
  to the fan-out agents.

**Fan-out agents**: union `ROUTE.agents` (your MULTI-AGENT RULE picks, each
validated against the manifest) into the `research_needed` agent list,
deduped. Dispatch fan-out agents as separate parallel `Agent` tool calls
alongside the primary `build-dispatch.py` dispatch.

**Gate**: Stack applied. Phase 5.

---

### Phase 5: EXECUTE

Build the task spec with `request_verbatim` unchanged and `intent` exactly
`PROPOSED_INTENT`; include any unresolved alignment issue in `gaps`, then invoke
`build-dispatch.py`:

```bash
python3 "$SDIR/build-dispatch.py" --json '{
  "agent": "<ROUTE.agent>", "skill": "<ROUTE.skill; omit when agent-only>",
  "pipeline": "<ROUTE.pipeline; omit when null>",
  "complexity": "<ROUTE.complexity>",
  "model": "<haiku|sonnet|opus or gemini-3.8-flash|gemini-4-argon|gemini-4-argon-high from Model choice>",
  "context_mode": "summary",
  "provider": "<anthropic|openai|google|antigravity|other>",
  "manual_model_override": false,
  "health": "-",
  "fallback_reason": "<REQUIRED when agent=general-purpose; omit otherwise>",
  "stack": ["<ROUTE.attach, in order>", "anti-rationalization-core"],
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

#### Model choice

Set `model` from the task type, not `inherit`. Pass the same `model` on every Agent call, including Explore and Plan.

| Task type | Model | Cost O/S/H per run (USD) | Deciding Jev evidence |
|---|---|---|---|
| locate, lookup, cite lines | haiku | 0.43 / 0.19 / 0.02 | haiku 0.91 |
| mechanical edit (rename, 11 files) | haiku | 0.26 / 0.11 / 0.007 | haiku 0.93 with scope evidence |
| review, find planted bugs | haiku | 0.4 / 0.15 / 0.01 | haiku 0.95 (n=1) |
| debug: root cause + regression test | sonnet | 0.39 / 0.20 / 0.015 | sonnet 0.88; haiku test 2.00 vs 2.86 |
| feature in an existing pattern (7 files) | sonnet | 1.30 / 0.32 / 0.088 | sonnet 0.64; Opus edited unrequested docs |
| long lane (9-10 files, UI text) | sonnet | 1.66 / 0.46 / 0.25 | sonnet 0.77 |
| no row fits | sonnet | n/a | sonnet 0.54 / haiku 0.45 (split) |

Opus won no measured task.

Tiers (`model_policy`): low-risk = haiku, standard = sonnet, high-risk (unmeasured, costly miss) = opus (on Antigravity / Google AI with `provider="google"`: `low-risk` = `gemini-3.8-flash`, `standard` = `gemini-4-argon`, `high-risk` = `gemini-4-argon-high`, `max-power` = `gemini-4-argon-high` / `max`; see `skills/meta/do/references/antigravity-execution.md`). `max-power` stays opus/xhigh (or `gemini-4-argon-high`/`max`) and needs `manual_model_override=true`. Use `inherit` only when no row or tier fits and the session model is acceptable.

Escalate on a miss: haiku, then sonnet, then opus. Retry once on the next model when an objective check fails (tests, `tsc`, `ruff`, acceptance command) or a Jev blocker Noul is at least 0.6.

Evidence limits: one repo, one run per cell; the review row is n=1. Full record, Jev questions, probabilities, and the re-measure method: `skills/meta/d/references/model-task-fit.md`.

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

Errors inside `jev-route.py` resolve to an `error` key and an empty evidence
set. Routing continues; Phase 2 reports an unavailable validation.

When changing how the router or validator builds or sends Jev requests, apply
`skills/shared-patterns/jev-production-lessons.md`: stage requests at or under the reliable size, send each
stage's requests together, and retry by status code.

## References

- `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md` — request/response
  contract, what Jev still decides, design decisions
- `${CLAUDE_SKILL_DIR}/references/model-task-fit.md` — model per task type,
  measured cost and Jev scores, re-measure method
- `${CLAUDE_SKILL_DIR}/SPEC.md`, `${CLAUDE_SKILL_DIR}/EVAL.md` — maintenance
  contract and regression cases (load only when creating, evaluating, or
  redesigning this skill)
- `scripts/jev-route.py`, `scripts/print-route-rules.py`, `scripts/jev-intent-align.py`,
  `scripts/jev_transport.py`, `scripts/jev_vercel.py`,
  `scripts/jev_gateway/jev_vercel_gateway.mjs`, `scripts/pre-route.py`,
  `scripts/routing-manifest.py`, `scripts/build-dispatch.py`
- Rule text: `skills/meta/do/SKILL.md` Phase 2 (printed by `print-route-rules.py`)
- Jev hook: `hooks/jev-route-injector-userprompt.py` (UserPromptSubmit) precomputes `JEV_RESULT`
