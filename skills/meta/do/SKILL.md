---
name: do
description: "Classify a request, validate names against the live routing manifest, and dispatch the matched agent, skill, pipeline, and rigor stack."
user-invocable: true
argument-hint: "<request>"
allowed-tools: [Read, Bash, Grep, Glob, Skill, Task]
routing:
  triggers: ["route task", "classify request", "which agent", "delegate to skill", "smart router"]
  category: meta-tooling
---

# /do — Smart router

Route Simple-or-larger work to agents and deliver the verified outcome. Read
repository instructions first. Preserve the user request, conversation context,
constraints, authorization, and prior decisions across every handoff.

**Every phase below is mandatory and ordered.** Emit `/do > Phase N: NAME —
description...` for each phase. Complete applicable steps; record a concrete
`not_applicable` reason only where the stated condition is false. Confidence,
simplicity, a previous route, a hook receipt, urgency, or a cleanup is never
permission to skip a required step. Do not answer, edit, dispatch, or declare
completion before the intent gate succeeds. Gathering bounded read-only context
and preparing the route/plan are permitted prerequisites.

## 1. CLASSIFY

Set `trivial | simple | medium | complex`; uncertainty rounds upward. Trivial
work is a conversational answer or a few obvious edits in an explicitly named
file. Repository exploration, git operations, codebase questions, comparisons,
opinions requiring investigation, and multi-file work are Simple+. Never turn
an involved request into Trivial to bypass dispatch.

Detect creation of an agent, skill, pipeline, hook, feature, plugin, workflow,
or voice profile. Mark `creation_request` explicitly; fix/review/refactor alone
is not creation. Mark `code_change` explicitly. Check existing feature state
when `.feature/` exists. Identify dependencies: independent work can fan out;
dependent stages must remain sequential. Round uncertain scope upward rather than bypassing routing.

**Gate:** Complexity, creation/code-change flags, and scope are recorded.

## 2. SELECT

Resolve `$SDIR` from the active harness scripts directory (`.claude`, `.hermes`,
`.factory`, `.codex`, `.reasonix`), then repository `scripts/`. Read the live
manifest once for this request:

```bash
bash "$SDIR/get-routing-manifest.sh"
```

Choose by the user's meaning in conversation, not keyword overlap. Validate
agents in `AGENTS`, skills in `SKILLS`, pipelines in `PIPELINES`; never put a
skill in the agent slot. Inspect the narrowest domain agents and near-matches
before `general-purpose`. A domain skill requires its matching domain agent,
or an explicit reason no listed agent covers it. Record any general-purpose
reason in the decision, task constraints, and routing banner.

Evaluate semantic FORCE rules in the manifest for both skills and pipelines.
A matching force skill and force pipeline fill different slots and compose;
resolve competing choices within one slot by the most specific intent match.
Protected deterministic git/security guards below remain authoritative.

Simple+ requires agent+methodology skill. Null skill must be repaired:
review/audit→`review`, debug/refactor/plan/loop→`workflow`, explain/compare→
`assessment`, agent comparisons→`toolkit`, TDD→`testing`; otherwise `workflow`.
Select debugging/refactoring pipelines when applicable. Low-confidence names
must be checked against the indexes. Cross-repository work uses the same
membership and specialization rules.

After semantic selection, run the deterministic guard once with the unchanged
request in a temporary file:

```bash
python3 "$SDIR/pre-route.py" --request-file "$REQUEST_FILE" --json-compact
```

High-confidence protected git/security force routes override a conflicting
semantic skill; retain domain agent ownership and the returned stack. Other
guard results do not replace the semantic route. Apply an explicit methodology
verb override only when compatible with that protected route.

**COMBINATION DOCTRINE:** Agent, skill, pipeline, and stack compose. Simple:
agent+skill; Medium: agent+skill+applicable rigor; Complex: two or more agents, two or more skills, and a pipeline are required
unless a concrete `composition_exception` explains why fewer cover the work. Each
fan-out has distinct ownership. A pipeline replaces neither agent nor skill.
`quick` means one step and cannot carry a pipeline. Choose one outer pipeline;
nest another only through workflow dispatch. A domain skill replaces a fallback
`workflow` pick, not its useful rigor. Trivial has no worker selection, but still
records that reason and proceeds through the intent gate.

**Gate:** Validated route and protected guard result recorded; no empty
Simple+ skill and no unexplained general-purpose fallback.

## 3. ENHANCE

Evaluate every row; apply only when its condition holds. Always include
`anti-rationalization-core`; check `pairs_with` and avoid duplicate gates.

| Signal | Required action |
|---|---|
| Substantive work | Consult material retrospective knowledge |
| Tests requested / production ready | Apply `testing` and verification evidence |
| Research needed / investigate first | Add `research-coordinator-engineer` with distinct scope |
| Comprehensive review / 5+ files, no real diff | Apply `review` across security, business logic, architecture |
| Real multi-file diff | Run `right-size-review.py`; its tier overrides generic comprehensive review |
| Complex implementation | Apply relevant `process` coordination |
| Local only / no push | Inject `shared-patterns/local-only.md` |
| User voice profile | Stack `writing` and retain the named profile |
| Knowledge belongs to another person | Load workflow `pl-human-source-elicitation.md`; never send without authority |
| Evidence can resolve consequential uncertainty | Load workflow `pl-empirical-prototype.md` |
| Objective with done-criteria / loop until done | Stack `workflow` objective execution |
| Protected git/security route with Go operands | Keep primary skill; retain guard `programming` stack |

Resolve reversible uncertainties with stated assumptions. Ask only for material
missing scope or authority. For multiple consequential decisions, use workflow
`pl-depth-first-interview.md`, batch independent questions, and preserve the
active delivery objective. Implicit interviews cap at five questions and three
rounds; explicit interviews continue until material coverage or a user stop.
Existing authorization and explicit instructions to proceed take precedence
under the session rules. Decisions feed back into execution, not an early
completion report.

**Gate:** Every applicable enhancement applied; remaining uncertainties and
nonapplicability reasons recorded.

## 4. GATHER AND PLAN

Write the actual proposed intent in the task spec: the requested outcome and
all material constraints, grounded in the unchanged `request_verbatim` and
conversation context. Do not substitute the chosen method for the outcome.
Supply constraints/authority, decisions, prior results, gaps, acceptance
commands and expected evidence, owned files, ownership, and operator context.
Use explicit `none` reasons where a field has no material content.

Verify named paths. Gather at most five initial file excerpts; larger routing
investigations use a bounded read-only worker only after that worker has its
own complete scoped handoff and successful builder intent gate. Reuse durable evidence while its
source and context remain unchanged. Use `context_mode: summary` by default;
`files` adds useful excerpts, `none` retains the handoff envelope when the
worker already has current evidence. Do not use legacy `--no-gather` to remove
the envelope for Medium+.

Evaluate these gates and record each as applied or conditionally inapplicable:

- **Plan (Simple+):** Create/update `task_plan.md` and pass its existing path as
  `plan_file`. A plan is a prerequisite, not task completion.
- **Creation:** Create the local `adr/{name}.md`, register with `adr-query.py`,
  and connect the plan to it. Keep local ADR artifacts uncommitted.
- **Quality loop:** For Medium+ code changes, load `references/quality-loop.md`;
  preserve implement→test→intent verification→review→fix→retest→delivery and
  decision-record reconciliation. Non-code, Trivial, and Simple may mark this
  gate inapplicable unless explicitly requested.
- **Workflow:** A selected pipeline, Complex work, or an explicit workflow
  request loads `references/workflow-dispatch.md`. Quality loop stays outer;
  workflow runs inside implementation.
- **Composition:** Confirm the agents, skills, stacks, and pipeline warranted
  by Phase 2, including justified single-owner exceptions.
- **Auto-Pipeline Fallback:** For unmatched Simple+ work, inspect workflow
  `references/auto-pipeline.md`; choose the closest live pipeline when the work
  genuinely has phases, otherwise explain why agent+skill suffices. Never
  leave skill empty or invent a pipeline name.

When the latest request depends on earlier turns, supply `task_spec.prior_context`
as up to eight verbatim prior user messages. The latest request, proposed intent,
and prior messages share a 180,000-character budget. If they cannot fit without
losing required context, report the diagnostic and restart with a fresh scoped
`/d` or `/do` request that restates the outcome and constraints.
This is labeled context for the actual-intent check, never a rewrite of the
latest request. Preserve the full latest `request_verbatim`, including `/d`,
`$d`, `/do`, or `$do` when present.

**Gate:** Complete task spec, existing Simple+ plan, and gate evidence.

## 5. VALIDATE INTENT AND BUILD

Build the decision with `router: "do"` (preserve `"d"` when a `/d` request
fell back here), validated names, complexity, `model:
"inherit"`, active harness provider, stack, flags, task spec, plan and gate
receipts. Use the shared protocol in
`../d/references/required-router-protocol.md` exactly. The builder runs Jev
against the actual proposed intent and selected route. A baseline, self-review,
cached receipt, or statement that intent is obvious cannot replace this call.

Run `build-dispatch.py` from a JSON file. Trivial uses its finalization mode;
it still requires intent validation before the direct answer/action. If Jev
cannot validate, or requests clarification or correction, stop the dependent
action, report the real diagnostic, resolve the issue, and retry. Never label
unavailable/error/review as aligned or silently fall through.

After the gate succeeds, show the routing banner with agent, skill, optional
pipeline, rigor, and reasons. A fallback reason is mandatory for
`general-purpose`. Trivial shows its classification and direct-handling reason.

**Gate:** Successful required intent check and validated builder output.

## 6. EXECUTE AND VERIFY

Native Agent/Task receives the exact builder output as its prompt: do not append
context or reuse a consumed prompt. Put all context in the task spec before
validation. Invoke the emitted action; do not hand-assemble tool calls or `[do-route]`
markers. The builder emits `Call the Skill tool with` for callable skills only;
agents and pipelines are not Skill-tool calls. Read the selected skill in
harnesses without a Skill tool. Inherit the current model; never pass the word
`inherit` as an agent tool model name. Load `references/model-selection.md`
only for deliberate authorized overrides. Requested model metadata does not
prove the worker's actual runtime identity.

Fan-out requires one builder invocation and one worker dispatch per agent,
each with a scoped task spec and independently validated actual intent. Run
independent workers in parallel (maximum ten concurrently; larger prescribed
rosters run in waves); pass prior results and evidence
through sequential dependencies. Synthesis receives all required findings and
checks coverage. Keep protected git/security gates active throughout.

**Lazy-completion check:** Compare returned work against enumerable scope and
acceptance evidence. Reject partial or unsupported “done”, re-dispatch to
repair missing work, and verify changed inputs again. Deliver the requested
state, including tests/docs and authorized PR/merge steps. Report a genuine
blocker explicitly; never substitute a plan or intermediate artifact.

**Gate:** Required work executed, acceptance verified, results delivered.

## Errors and telemetry

Load `references/error-handling.md` on routing errors and
`references/routing-telemetry.md` for observed route failures or telemetry
claims. The builder's `[do-route]` is the sole routing marker; session-end
telemetry is a fallback receipt, never routing authority. Record real failures
rather than manufacturing successful receipts.
