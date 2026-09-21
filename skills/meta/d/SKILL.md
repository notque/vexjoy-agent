---
name: d
version: "1.3.0"
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

**All phases are mandatory, in order, on every invocation.** Emit `/d > Phase
N: NAME — description...` at each phase. Complete applicable steps; record
nonapplicability only when an explicit condition is false. Never skip the actual
proposed-intent check: normal, force-route, trivial, fallback, injected-result,
and resumed paths all require it. A hook baseline, prior receipt, self-review,
confidence, urgency, or apparent simplicity cannot substitute for the check.

Do not answer, edit, invoke a worker, or declare completion until the required
intent gate succeeds. Bounded read-only context gathering and route/plan
preparation are prerequisites, not permission to execute the task. Carry the
unchanged user request and relevant conversation context throughout.

## 1. CLASSIFY

`scripts/jev-route.py` owns classification. Its deterministic `pre-route.py`
guard runs first and is authoritative for protected git/security routes;
otherwise Jev ranks all manifest candidates, checks triviality, and reranks a
detailed shortlist. Every selected name must belong to the live manifest.

Use an injected `JEV_RESULT` for this request if present; otherwise save the
verbatim request to a temporary file and run:

```bash
python3 "$SDIR/jev-route.py" --request-file "$REQUEST_FILE" --json-compact
```

Resolve `$SDIR` from the active harness scripts directory (`.claude`, `.hermes`,
`.factory`, `.codex`, `.reasonix`), then repository `scripts/`.

Record `fallback`, `fallback_reason`, `agent`, `skill`, `pipeline`, `complexity`,
`confidence`, `reasoning`, `source`, `stack`, `signals`, and `agents`.
See `references/jev-classifier-design.md` for classifier boundaries.

**Gate:** Current request has a classification receipt. Classification alone
never authorizes execution or satisfies intent validation.

## 2. SELECT

For matched routes, retain manifest-validated agent/skill/pipeline. Null
force-route complexity defaults to Medium except a single one-line fix is
Simple. Preserve the protected skill even when adding domain expertise.

For `fallback: true`, report the classification failure and run `/do`'s complete
ordered flow from `../do/SKILL.md`. Classification fails open to that route
selection, **not** past its required intent gate. Unavailable Jev must never
be described as successful alignment. Carry `router: "d"` when a `/d` request
falls back so its provenance and mandatory gate survive.

For `source: jev-trivial-bypass`, select direct handling, record why agent/skill
selection is inapplicable, and continue every remaining phase. Do not answer
here. Phase 5 finalization is mandatory even for greetings and one-line answers.

**Gate:** Route or direct-handling reason recorded. Do not show a success routing
banner until Phase 5 has passed.

## 3. ENHANCE

Apply script-produced stack and evaluate every signal:

| Signal | Required addition |
|---|---|
| `tests_requested` | `testing`, including verification before completion |
| `research_needed` | `research-coordinator-engineer` fan-out |
| `comprehensive_review` | `review`; a real multi-file diff uses `right-size-review.py` and overrides generic coverage |
| `local_only` | `shared-patterns/local-only.md` |
| `objective_loop_worthy` | `workflow` objective execution |

`anti-rationalization-core` always rides nontrivial routes. Preserve protected
force-route stacks. Union/deduplicate `JEV_RESULT.agents` with signal-selected
agents and assign separate ownership. Apply the remaining conditional
composition, uncertainty, voice, evidence, and domain rigor rules in `/do`
Phase 3; a false signal is a recorded condition, not a blanket phase bypass.

**Gate:** Applicable enhancements and fan-out ownership recorded.

## 4. GATHER AND PLAN

Execute `/do` Phase 4 in full: complete task spec, existing Simple+ `task_plan.md`,
creation ADR/registration when applicable, quality loop for Medium+ code
changes, workflow for selected pipelines/Complex/explicit requests, composition
and auto-pipeline evaluation. Quality loop stays outer with workflow inside
implementation. A worker consumes the router's plan; it does not repeat planning
merely because ownership changed.

Write the actual `task_spec.intent` as the requested outcome and material
constraints, preserving context and all explicit deliverables. Preserve
`task_spec.request_verbatim` unchanged. Record constraints/authority, decisions,
prior results, gaps, acceptance evidence, files, ownership, and operator context.
A method or agent name is not the requested outcome.

When the latest request depends on earlier turns, supply `task_spec.prior_context`
as up to eight verbatim prior user messages. The latest request, proposed intent,
and prior messages share a 180,000-character budget. If they cannot fit without
losing required context, report the diagnostic and restart with a fresh scoped
`/d` or `/do` request that restates the outcome and constraints.
This is labeled context for the actual-intent check, never a rewrite of the
latest request. Preserve the full latest `request_verbatim`, including `/d`,
`$d`, `/do`, or `$do` when present.

**Gate:** Complete handoff, plan, and applicable gate evidence.

## 5. VALIDATE INTENT AND BUILD

Follow `references/required-router-protocol.md`. Use `router: "d"` and pass the
actual intent and full route to `build-dispatch.py`. The builder performs a
fresh Jev evaluation before producing an executable dispatch. **This call is
mandatory and cannot be skipped or replaced by an automatic baseline.**

For Trivial, use `build-dispatch.py --router-finalize --json-file <decision>`.
This validates intent without creating a worker dispatch. Ordinary routed work
uses `build-dispatch.py --json-file <decision>`.

If the check is `review`, correct the scope or route and retry. If essential
clarification is required, obtain it before dependent execution. If unavailable
or errored, report that failure and stop dependent execution until validation
can succeed. Never invent scores, mark an unavailable receipt aligned, remove
`router`, or fall back to a manual invocation to get around the gate.

Only after success, print the builder-generated canonical banner verbatim before
execution. For routed work it is the first block of builder output; for Trivial
it is the `banner` field in the `--router-finalize` JSON result. Raw receipt
JSON, a paraphrase, or a banner shown only inside a worker prompt does not
satisfy this requirement. Retain or repeat the exact banner in the final reply;
supported Stop hooks enforce that final user-visible copy. The canonical form is:

```text
Intent alignment (/d):
  -> Restated outcome: [exact task_spec.intent]
  -> Jev: aligned [actual receipt]
===================================================================
 ROUTING (/d): [brief summary]
 Selected:
   -> Agent: [name and reason, or direct trivial handling]
   -> Skill: [name and reason, when routed]
   -> Pipeline: [name and phases, when selected]
   -> Source: [source] (confidence: [confidence])
===================================================================
```

Trivial also shows `Classification: Trivial` and its source.

**Gate:** Fresh actual-intent alignment succeeded; validated output exists.

## 6. EXECUTE AND VERIFY

Execute `/do` Phase 6: invoke the builder's action, run applicable selected
skills/pipeline and rigor, inspect results against scope and acceptance evidence,
repair missing work, and deliver the completed outcome. Fan-out requires a
separate builder call and scoped intent check for each worker. Direct Trivial
handling is allowed only after successful finalization.

A failed, absent, stale, or baseline-only intent check blocks execution. Hooks
can enforce pending gates in supported native sessions; skill instructions and
the builder remain required in other harnesses. Do not claim universal tool
interception where the harness has not installed it.

**Gate:** Work executed and verified; results delivered, or a real blocker
reported without claiming completion.

Maintenance: `SPEC.md`, `EVAL.md`, and `references/jev-classifier-design.md`.
