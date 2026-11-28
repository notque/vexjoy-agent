---
name: d
version: "3.1.0"
description: "Router that runs the work in the main loop: picks skill, pipeline, and stack with /do's rules; Jev checks intent and attaches skills."
user-invocable: true
argument-hint: "[request]"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Agent
routing:
  triggers:
    - "jev router"
    - "route with jev"
    - "use the d router"
  not_for: "Requests that name another router or skill directly; /d routes the request, then runs it in the main loop."
  category: meta-tooling
---

# /d — Jev router, main loop

`/d` is `/do`'s Jev-gated main-loop mode: it shares `/do`'s exact manifest (`get-routing-manifest.sh`), rule text (`print-route-rules.py`), `build-dispatch.py`, and `d-preflight.py`, then executes in this thread with the routed skill loaded. `pre-route.py` keeps git/PR and security work on their quality gates; Jev checks attachment signals and verifies that your restated outcome matches the request; scripts validate the pick and enforce gates.

Print `/d > Phase N: NAME` at each phase. Design: `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md`. `$SDIR`: `${HOME}/.claude/scripts`, else `.gemini`/`.hermes`/`.factory`/`.codex`/`.reasonix`, else repo `scripts/`.

---

### Phase 1: CLASSIFY

**Step 1 — JEV_RESULT.** When `JEV_RESULT` is in context (the
`jev-route-injector` hook ran), use it. Otherwise:

```bash
REQUEST_FILE=$(mktemp); printf '%s' "{user_request}" > "$REQUEST_FILE"
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
```

Keep `REQUEST_FILE` until Phase 5. Fields you use: `forced` (the safety force
route: `pr-workflow`, `pr-pipeline`, `security`, or `null`), `stack`,
`project` (repo languages, frameworks, datastores, or `null`), `signals`,
`domain_scores`, `error`. Jev failure never blocks routing.

**Step 2 — Pick.** Set complexity per `/do` Phase 1 (Trivial, Simple, Medium,
Complex). Trivial: go to Phase 1T. Otherwise load the rules and the manifest
and apply every rule:

```bash
python3 "$SDIR/print-route-rules.py"
bash "$SDIR/get-routing-manifest.sh" --request-file "$REQUEST_FILE"
```

If Bash truncates the manifest or saves it to a file, read all of it. Use
`JEV_RESULT.project` when the request names no language. Hold the decision as
JSON, unprinted:

```
{"skill": "<SKILLS: name or null>", "pipeline": "<PIPELINES: name or null>",
 "stack": ["<domain SKILLS that ride with skill, e.g. programming for Go>"],
 "workers": [{"skill": "<SKILLS: name>", "scope": "<files or part this worker owns>"}],
 "complexity": "simple|medium|complex", "confidence": "high|medium|low",
 "reasoning": "<one sentence>"}
```

When `JEV_RESULT.error` is set, add `"signals": {...}` with your own true/false
for `tests_requested`, `research_needed`, `comprehensive_review`,
`local_only`, and `objective_loop_worthy` (`/do`'s Phase 3 signals);
finalize attaches from them instead of Jev's.

`stack` names the domain skill when `skill` is a methodology (e.g. `programming` for Go); `workers` holds independent fan-out parts (`[]` for one thread); add `"agent": "<AGENTS: name>"` only for a matching private overlay agent (keeping `skill`). When `JEV_RESULT.forced` is set, its `skill` and `pipeline` win in Step 3 while your `stack` and `workers` stand.

**Step 3 — Finalize.**

```bash
python3 "$SDIR/jev-route.py" --finalize --result-file "$RESULT_FILE" --decision-file "$DECISION_FILE" --json-compact
```

Hold the output as `ROUTE` (`agent`, `skill`, `pipeline`, `workers`, `attach`,
`complexity`, `confidence`, `reasoning`, `source`, `problems`). The script
checks names against the live manifest, applies the safety force route, fills
an empty skill with `workflow`, and builds `attach`. `problems` set: fix the
decision and finalize once more; carry what remains into `task_spec.gaps`. An
`error` key with no route fields: use your decision with `attach` `[]`.

**Step 4 — Preflight.** Simple and above, once you know the paths you will
create or change:

```bash
python3 "$SDIR/d-preflight.py" --paths <planned paths>
```

It names each safety gate those paths will hit and its cost (an ADR and its
3-reviewer consultation, a commit blocked on a key-shaped string or a private
name). Advisory, exit 0. Act on it now: pick the cheaper path or plan the
cost into the work, instead of meeting the gate mid-commit.

---

### Phase 1T: TRIVIAL

Run Phase 2 with `{"complexity": "trivial"}` as the route file, then
`build-dispatch.py` with `"execution": "main", "skill": "-", "complexity":
"trivial"` (Phase 5 shape). Show `Classification: Trivial`, then answer or do
the one-line action. Skip Phases 3-4.

---

### Phase 2: ALIGN INTENT (every route)

Write `PROPOSED_INTENT`: one or two sentences stating the outcome and each
deliverable the request names or directly requires. Copy every explicit
constraint in the user's words: limits ("only", "at most"), exclusions
("don't touch", "do not deploy"), required methods, and authorization
boundaries. Add no deliverable the user did not ask for (extra tests, docs,
cleanup, refactors, verification). Add no notes about missing inputs; the
validator decides on clarification. Do not describe the skill or mechanics as
the outcome.

Put `ROUTE` and the intent in files, then:

```bash
python3 "$SDIR/jev-intent-align.py" --request-file "$REQUEST_FILE" --route-file "$ROUTE_FILE" \
  --proposed-intent-file "$INTENT_FILE" --json-compact
```

It returns `alignment` (`aligned`, `review`, `unavailable`, `error`),
`clarification_needed`, and `issues`, and writes a receipt for this request
and intent. Show:

```
Intent alignment (/d):
  -> Restated outcome: [PROPOSED_INTENT]
  -> Jev: [alignment] [issues, if any]
```

| Result | Do |
|---|---|
| `clarification_needed` | Ask one concise question naming the ambiguity. Stop until answered. |
| `review` | Correct the intent or the route and run the validator once more. Carry remaining issues into `task_spec.gaps`. |
| `unavailable` / `error` | Say validation was unavailable and continue. A Jev outage never becomes a rejection. |
| `aligned` | Continue. |

`build-dispatch.py` with `"router": "d"` enforces this table: it refuses to run without
a receipt for the exact `request_verbatim` and `intent`, on a clarification
without `task_spec.clarification`, and on `review` with empty `gaps`. It is a
tool check, not a hook; skipping the script skips the gate.

---

### Phase 3: DECIDE

Use `ROUTE` as validated. `complexity` `null` → `medium` (a one-line fix →
`simple`). Print together:

```
===================================================================
 ROUTING (/d): [brief summary]
===================================================================
 Intent (/d):
   -> Restated: [PROPOSED_INTENT]
   -> Alignment: [alignment] [— issues, if any]
 Selected:
   -> Execution: main loop | dispatch ([reason]) per part
   -> Skill: [ROUTE.skill] - [ROUTE.reasoning]
   -> Attached: [ROUTE.attach, or "none"]
   -> Pipeline: [ROUTE.pipeline, if set]
   -> Source: [ROUTE.source] (confidence: [ROUTE.confidence])
===================================================================
```

---

### Phase 4: ENHANCE

`stack` = `ROUTE.attach` in order, plus `anti-rationalization-core`. Copy the
names exactly; `build-dispatch.py` rejects names absent from
`skills/INDEX.json`.

| Source | Attaches |
|---|---|
| `JEV_RESULT.stack` (pre-route, e.g. a `.go` file with PR or security work) | its entries, first |
| Domain floor: your decision's `stack` | e.g. `programming` for Go, Kotlin, PHP, and Swift work; `kubernetes`; `frontend` |
| `domain_scores` at 0.6 or higher | `programming`, `frontend`, `kubernetes`, `testing`, `building-with-jev`, `research` |
| `tests_requested` / `comprehensive_review` / `objective_loop_worthy` | `testing` / `review` / `workflow` |
| `local_only` | `local-only` shared pattern |

At most three beyond `skill`. Two calls stay with you: `comprehensive_review`
attached `review` and a real multi-file diff exists → `right-size-review.py`
outranks it, drop `review`; `signals.research_needed` → add a `research` part
to `workers`.

---

### Phase 5: EXECUTE (main loop by default)

Write the decision to a file and run, with `request_verbatim` unchanged and
`intent` exactly `PROPOSED_INTENT`:

```bash
python3 "$SDIR/build-dispatch.py" --json-file "$DISPATCH_FILE"
```

```
{"router": "d", "execution": "main", "skill": "<ROUTE.skill>",
 "pipeline": "<ROUTE.pipeline; omit when null>", "complexity": "<ROUTE.complexity>",
 "stack": ["<ROUTE.attach, in order>", "anti-rationalization-core"],
 "task_spec": {"request_verbatim": "<user message, unchanged>", "intent": "<PROPOSED_INTENT>",
               "constraints": "<rules, limits, authorization>", "gaps": "<open alignment issues>",
               "acceptance": "<command> -> <expected>", "files": "<planned paths>",
               "scenario": "<real-scenario check, when files touch installer/hooks/routing>"}}
```

Medium and Complex main routes also need `task_spec.acceptance` (the check
that proves the work), and `task_spec.scenario` when `files` touch the
installer, hooks, or routing scripts: a real-scenario run, not only unit tests.
The script refuses without them and prints the closing verifier step.

It prints the marker (`router=d`, recorded for telemetry), the Skill-tool
calls, the pipeline's phases, the reference-loading rule, and the local-only
block when `local-only` is in the stack. Call the Skill tool as printed, read
the matching references, and do the work in this thread, running every
pipeline phase in order.

**Dispatch only when it pays**, one `build-dispatch.py` call per worker with
`"execution": "dispatch"`, a `model` from Model choice, and one
`dispatch_reason`:

| `dispatch_reason` | When | The script requires |
|---|---|---|
| `fan-out` | independent parts that each need a fresh context (`ROUTE.workers`, a pipeline's parallel phase) | `task_spec.ownership` or `files` |
| `worktree` | work that needs worktree isolation | `flags.worktree: true` |
| `haiku-gather` | read-only gathering (locate, cite, excerpt, fetch) that this thread judges | `model: "haiku"` |
| `verifier` | an independent reviewer or verifier of work already done | `task_spec.acceptance` |
| `overlay-agent` | `ROUTE.agent` is a private overlay agent (not `general-purpose`) | `"agent": "<ROUTE.agent>"`, a live overlay agent |
| `context-budget` | one long job whose reading would flood this thread and is not needed afterwards | `task_spec.files` names 10+ existing files or 50+ KB (measured); `acceptance` says what comes back |

A dispatch also needs `references`: one or more files from the skill's
`references/` directory, so the `general-purpose` worker gets the skill and
the reference (optional for `overlay-agent`: the agent file carries its domain). The script lists the options when they are missing. Emit
parallel Agent calls in one message. PR work in a worker: `constraints` says
commit locally, report the SHA, and never push or open a PR without the
go-ahead. Creation, plan-file, quality-loop, and auto-pipeline rules follow
`/do` Phase 4.

#### Model choice

Set `model` from the task type, not `inherit`. Pass the same `model` on every Agent call, including Explore and Plan.

| Task type | Model / effort |
|---|---|
| read-only gathering: locate, lookup, cite lines, excerpts, research fetch, log reading | haiku |
| code writing and edits, debugging, features, reviews that decide, decisions, no row fits | opus / medium, then high |
| high-risk: auth, data, security, concurrency, irreversible | opus / medium, then high |
| major refactor or migration, architecture planning, lead of a many-worker fan-out, deep research synthesis, quantitative analysis, long unattended run, or Opus at high fell short | fable / medium, then high |

Sonnet is no row's default. When the owner names a model for the task ("use fable for everything"), pass that model on every dispatch with `manual_model_override=true`.

Tiers (`model_policy`): low-risk = haiku/low (read-only gathering only), standard = opus/medium, high-risk = opus/medium, max-power = fable/high. Owner, 2026-11-09: "Also I prefer opus 5.5 medium over high". Opus starts at medium on every row and tier, high-risk included. opus/high is no tier's default: reach it as an explicit pick (`model: "opus"`, `model_effort: "high"`, no `model_policy`) or as the step after a failed opus/medium attempt. `max-power`, fable/max, opus/max, and explicit opus/xhigh need `manual_model_override=true`; test fable at high before opus/xhigh. Use `inherit` only when no row or tier fits and the session model is acceptable.

Escalate on a miss, when an objective check fails (tests, `tsc`, `ruff`, acceptance command) or a Jev blocker Noul is at least 0.6. In order: (1) give the agent a way to verify (test, build, script); (2) raise effort one level, up to high; (3) move to the next model up at a lower effort: haiku → opus/medium → opus/high → fable/medium → fable/high. Never raise opus past high before trying fable.

Evidence: Anthropic's 2026-11-09 model guide and the owner's 2026-11-01 and 2026-11-09 orders, which win where they differ. Prices, effort trade-offs, mixing rules, history, and the re-measure method: `skills/meta/d/references/model-task-fit.md`.

On Antigravity / Google AI (`provider="google"`), follow `skills/meta/do/references/antigravity-execution.md`. Main-loop work runs on the session model; the table sets each dispatch's model.

---

### Post-execute: VERIFY (Medium and Complex)

Before you report done, run the closing step build-dispatch printed: one
`verifier` dispatch that gets the change, not your conclusion, and runs
`acceptance` and `scenario`. Fix what it confirms, re-run the failed check,
and report its verdict. Unit tests passing is not the verdict: both blocking
bugs in PR #1156 passed 8,038 tests and fell to an install-then-upgrade run.

### Post-execute: GRILL-JEV

When the work produced a plan, spec, or design (`task_plan.md`, a spec file, or
a reply with numbered phases or steps), run before declaring done:

```bash
python3 "$SDIR/grill-jev.py" --file <artifact> --mode plan
```

Exit 1: show the findings and ask whether to address them. Exit 0: note
"grill-jev: clean". Skip for code-only output (use `--mode code`), pure
research answers, and when grill-jev was the request.

---

## Errors

`jev-route.py` errors resolve to an `error` key; routing continues and Phase 2
reports unavailable. When changing how a script builds or sends Jev requests,
apply `skills/shared-patterns/jev-production-lessons.md`.

## References

- `${CLAUDE_SKILL_DIR}/references/jev-classifier-design.md`: contract, what Jev decides, what code enforces
- `${CLAUDE_SKILL_DIR}/references/model-task-fit.md`: model per task type, re-measure method
- `${CLAUDE_SKILL_DIR}/SPEC.md`, `${CLAUDE_SKILL_DIR}/EVAL.md`: maintenance contract and evals (load only to change or evaluate /d)
- Scripts: `jev-route.py`, `print-route-rules.py`, `jev-intent-align.py`, `d_gate.py`, `build-dispatch.py`, `d-preflight.py`, `router-metrics.py`
- Rule text: `skills/meta/do/SKILL.md` Phase 2, printed by `print-route-rules.py`
