# Required router handoff protocol

Both `/d` and `/do` use this builder contract, including fallback, force, and
Trivial routes. Save the decision as JSON; never shell-interpolate user text.

```json
{
  "router": "d",
  "agent": "manifest-agent",
  "skill": "manifest-skill",
  "complexity": "medium",
  "model": "inherit",
  "context_mode": "summary",
  "provider": "openai",
  "manual_model_override": false,
  "health": "-",
  "stack": ["anti-rationalization-core"],
  "creation_request": false,
  "code_change": true,
  "explicit_workflow": false,
  "plan_file": "/absolute/task/worktree/task_plan.md",
  "routing_steps": {
    "classification": "Complexity and creation/code-change evidence",
    "selection": "Manifest validation, protected guard, and route reasoning",
    "enhancement": "Applied conditional rigor and exclusions",
    "handoff": "Verified scope, paths, plan, and acceptance evidence"
  },
  "routing_gates": {
    "creation": {"status": "not_applicable", "reason": "Existing component repair"},
    "quality_loop": {"status": "applied", "reason": "Medium code change; quality loop loaded and scheduled", "artifact": "/absolute/task/worktree/quality-loop-state.md"},
    "workflow": {"status": "not_applicable", "reason": "No pipeline, Complex classification, or explicit workflow"},
    "composition": {"status": "applied", "reason": "One domain owner, primary skill, required rigor"}
  },
  "task_spec": {
    "request_verbatim": "Unchanged original user request",
    "intent": "Actual outcome and constraints this worker will execute",
    "constraints": "Applicable authority and limits",
    "decisions": "Material decisions, or explicit none",
    "prior_results": "Relevant evidence paths, or explicit none",
    "gaps": "Unresolved gaps, or explicit none",
    "acceptance": "Command or observation and expected evidence",
    "files": "Verified owned paths, or explicit none for no file scope",
    "ownership": "This worker's boundary",
    "operator_context": "Active authorization and preferences"
  },
  "flags": {"worktree": false, "local_only": false, "thinking_override": null},
  "token_remaining": 480000
}
```

Replace examples with real evidence. `router` is `d` or `do`; fallback preserves
the originating `/d`. Supply `pipeline` only when selected. `general-purpose`
requires top-level `fallback_reason` explaining why no live domain agent fits.

All four `routing_steps` values must be nonempty. All task fields listed above
except `prior_results` are mechanically required nonempty strings. Both skills
also require `prior_results` (an explicit none is valid) to preserve handoff
continuity. A Simple+ plan must exist
and be nonempty. The router prepares it; workers consume it. Gate reasons must
be nonempty and status is `applied` or `not_applicable`. Creation requires its
gate; Medium+ code changes require quality-loop; pipeline, Complex, or explicit
workflow requires workflow. For Complex, put additional manifest names in top-level `agents` and `skills`
arrays alongside the primary `agent` and `skill`. Complex requires two distinct
agents, two skills, and a pipeline, or a concrete `composition_exception` explaining why fewer
components cover the task. Names remain manifest-validated; rigor tokens do
not turn nonexistent skills into callable skills.

Run:

```bash
python3 "$SDIR/build-dispatch.py" --json-file "$DECISION_FILE"
```

Trivial finalization uses the same evidence/task fields and explicit booleans,
with `complexity: "trivial"`; agent/skill/plan may be omitted. Record gate
nonapplicability reasons rather than omitting phases:

```bash
python3 "$SDIR/build-dispatch.py" --router-finalize --json-file "$DECISION_FILE"
```

The builder checks structural prerequisites and evaluates the exact proposed
intent through Jev. Only fresh aligned results authorize the next action.
Review, clarification, unavailable, and error are blocking diagnostics. Repair
and retry; no stored or self-reported alignment receipt is accepted as proof.
The intent check establishes alignment, not completion: execution, tests,
review, delivery, and final scope reconciliation still have to happen.

Required creation, quality-loop, and workflow gates also require `artifact`:
a path to an existing nonempty task-owned evidence file. Use the registered
ADR for creation, initialized `quality-loop-state.md` for quality-loop, and a
recorded workflow plan/roster for workflow. Create these before validation;
record pending implementation/check/review/delivery honestly. An initialized
artifact proves the gate was prepared, not that future work has already passed.
Composition uses its concrete reason/exception rather than an artifact.

For supported native Agent/Task hooks, use the **exact builder stdout** as the
worker prompt. Do not append instructions or reuse an already consumed prompt;
put all context in the task spec before the builder validates it. Fan-out emits
one independently checked prompt per worker. Trivial finalization authorizes
direct completion only, never a worker dispatch.

For follow-up requests, optional `task_spec.prior_context` is a list of at most
eight verbatim prior user messages. The latest request, proposed intent, and
prior messages share a 180,000-character budget. Supply
only relevant user context; the validator treats it as labeled evidence while
preserving the latest raw `request_verbatim`, including its router prefix. The
builder includes this context in the checked task spec and emitted prompt.

An unprefixed clarification while the native session has a pending, checked-blocked,
queued, validated, or dispatched handoff continues the same router obligation. Use the
latest message unchanged as `request_verbatim`, include the prior pending user
requests and clarifications verbatim in `prior_context`, and reclassify with
that context. The bounded required history retains the original request anchor
and up to seven recent prior messages. The eight-message and shared character
limits still apply. Never truncate a required anchor: if the inputs cannot fit,
report the diagnostic and restart with a fresh scoped `/d` or `/do` request
that restates the outcome and constraints. The hook rotates the request generation and invalidates earlier
approvals; a previous route or checked prompt cannot authorize the new turn.
The builder verifies required prior-request hashes before checking intent.

Claude's Stop gate also blocks while validated Agent/Task prompts remain queued:
invoke every queued prompt once before reporting completion. The Codex adapter
explicitly permits Stop after successful validation because native dispatch
consumption is not observable there; it does not claim workers were invoked.
Execution and outcome verification remain mandatory skill steps on both hosts.
A `checked_blocked` result permits a diagnostic response only. A successful Stop
marks the matching request generation `completed`; only then does an ordinary
later prompt clear the finished routing marker. A stale Stop cannot complete
a newer generation.
