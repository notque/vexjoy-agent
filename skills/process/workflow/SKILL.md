---
name: workflow
description: "Structured work: multi-phase tasks, feature builds, planning, objective loops, hill climbing."
user-invocable: true
context: fork
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Skill
  - Agent
  - Task
routing:
  force_route: true
  not_for: "code review (use review), testing (use testing), security (use security)"
  triggers:
    - "workflow"
    - "multi-phase task"
    - "feature design"
    - "feature plan"
    - "feature implement"
    - "build feature end to end"
    - "full feature lifecycle"
    - "write spec"
    - "define requirements"
    - "create plan"
    - "create tasks"
    - "keep working until"
    - "iterate until done"
    - "drive this to done"
    - "make this faster"
    - "speed this up"
    - "reduce latency"
    - "profile and optimize"
    - "hill climb on this metric"
    - "tidy up"
    - "clean up"
    - "untangle"
    - "reorganize"
    - "structured pipeline"
    - "phased execution"
  category: process
  pairs_with:
    - review
    - testing
    - security
    - pr-workflow
---

# Workflow Skill

Five modes for structured multi-phase work. Match the request, follow that
mode's instructions.

## Mode Selection

| Request pattern | Mode |
|---|---|
| Feature design/plan/implement/validate/release, end-to-end | [Feature Lifecycle](#feature-lifecycle) |
| Write spec, define requirements, create plan, interview, pause/resume | [Planning](#planning) |
| Keep working until, iterate until done, drive to done | [Objective Loop](#objective-loop) |
| Make faster, speed up, reduce latency, profile, hill climb | [Hill Climb](#hill-climb) |
| All other structured workflows: review, debug, refactor, research, create, explore, upgrade | [Ad-Hoc Workflow](#ad-hoc-workflow) |

---

## Feature Lifecycle

Phase-gated workflow: DESIGN > PLAN > IMPLEMENT > VALIDATE > RELEASE. Each
phase must pass its gate before the next begins.

### Phase Routing

If `.feature/` exists, check state: `python3 ~/.claude/scripts/feature-state.py status`.
Route to the indicated phase.

If no feature state exists, determine entry from intent:
- "design", "think through", "explore approaches" -> DESIGN
- "plan", "break down", "create tasks" -> PLAN (requires completed design)
- "implement", "execute plan" -> IMPLEMENT (requires completed plan)
- "validate", "quality gates" -> VALIDATE (requires completed implementation)
- "release", "merge", "ship it" -> RELEASE (requires passed validation)
- "end to end", "full lifecycle" -> DESIGN (start from beginning)

### Phase References

Load the phase reference, then follow it exactly:

| Phase | Reference | Produces |
|---|---|---|
| DESIGN | `references/fl-design.md` | design.md |
| PLAN | `references/fl-plan.md` | Wave-ordered task list |
| IMPLEMENT | `references/fl-implement.md` | Code changes |
| VALIDATE | `references/fl-validate.md` | Quality gate report |
| RELEASE | `references/fl-release.md` | Merged PR |
| End-to-end | `references/fl-pipeline.md` | Full lifecycle |
| State conventions | `references/fl-shared.md` | -- |
| Error recovery | `references/fl-error-handling.md` | -- |

State operations use `python3 ~/.claude/scripts/feature-state.py` only.
Never manipulate state files directly.

---

## Planning

Spec writing, plan creation, interviews, ambiguity triage, and session
pause/resume. Planning owns specs and saved plans; execution goes through
subagent-driven-development or workflow dispatch.

### Sub-mode Routing

| Signal | Reference |
|---|---|
| Write spec, user stories, define requirements, scope, acceptance criteria | `references/pl-spec.md` |
| Discuss ambiguities, resolve gray areas, pre-planning discussion | `references/pl-pre-plan.md` |
| Interview me, depth-first review, "not sure", "where do I start", "poke holes" | `references/pl-depth-first-interview.md` |
| Implicit ambiguity or unclear implementation choices | `references/pl-ambiguity-triage.md` |
| Another person holds needed facts or approval | `references/pl-human-source-elicitation.md` |
| Observation can settle a disputed choice | `references/pl-empirical-prototype.md` |
| Phase or session transition near | `references/pl-context-boundary.md` |
| Create plan, task plan, file-backed planning | `references/pl-plan-files.md` |
| Check plan, validate plan, pre-execution check | `references/pl-check.md` |
| List plans, show plan, complete plan, manage plans | `references/pl-manage.md` |
| Pause, save progress, handoff, stopping for now | `references/pl-pause.md` |
| Resume, continue, pick up where I left off | `references/pl-resume.md` |

For interviews, batch independent questions into frontier rounds. Ask dependent
questions sequentially. Include a recommendation per question.

---

## Objective Loop

Iterate-until-verified-done loop. A user states an objective with verifiable
done-criteria; each iteration routes one /do cycle, verifies by executing the
criteria, and reschedules until verified-done or budget-stop.

### Phase 1: SPEC

Gather from the request: objective statement, DONE-CRITERIA (verifiable checks),
iteration budget (default 5), NOT-DONE-YET guardrails (what may never be done
to satisfy a criterion).

DONE-CRITERIA types: `command` (preferred -- deterministic command with expected
exit code/output) or `rubric` (only when no mechanical check exists -- frozen
at SPEC time, graded by a fresh-context agent).

### Phase 2: STATE

Write `.objective/<slug>/state.md` from `references/ol-state-file.md`. Wakeups
resume from the state file, never conversation memory.

### Phase 3: ITERATE

Plan the smallest next step. Route through /do: classify -> route -> dispatch
agents -> evaluate. The loop dispatches exclusively through /do -- never edit
inline.

### Phase 4: VERIFY

Run every done-criterion check. A worker's "passes" claim never substitutes for
re-running.
- `command`: run it, paste exit code and output into iteration log.
- `rubric`: dispatch fresh-context sub-agent (did NOT produce the work) with
  artifact + rubric only. Returns PASS/FAIL with cited evidence.

All pass -> final report, STOP. Any unmet -> Phase 5.

**Criteria-gaming guard**: a criterion may never be satisfied by weakening a
hook, gate, test, or safety control. Stop and report the conflict if that is
the only visible path.

### Phase 5: RESCHEDULE or STOP

All pass: stop. Unmet + iterations remain: update state file, call
`ScheduleWakeup` (delay 270s for active polling, 1200s+ for idle work).
Budget exhausted: honest NOT-DONE report with per-criterion status.

---

## Hill Climb

Metric-driven optimization loop. One number moves; everything else stays fixed.
Each iteration: hypothesis -> one change -> correctness floor -> re-measure ->
accept or revert.

### Phase 1: SPEC

| Field | Required | Default |
|---|---|---|
| METRIC (one number, units, direction) | yes | -- |
| MEASURE (deterministic command) | yes | -- |
| TARGET (value that ends the loop) | yes | -- |
| FLOOR (correctness gate commands, must exit 0) | yes | -- |
| FIXTURE (pinned dataset/workload) | yes | -- |
| Variance tolerance | no | 2x baseline spread |
| Iteration budget | no | 8 |
| Plateau threshold K | no | 3 |

One METRIC per loop. Two numbers with a trade-off: promote one to the FLOOR.
Load `references/hc-domain-playbooks.md` for pre-filled SPEC blocks per domain
(frame rate, API latency, CI time, bundle size, memory, token cost).

### Phase 2: BASELINE

Run MEASURE N times (N >= 5, N >= 10 for wall-clock). Record median and spread.
If spread >= target improvement: STOP -- harness too noisy. Report noise sources
and offer to stabilize first.

### Phase 3: PROFILE

Locate the cost before changing anything. Load `references/hc-profiling-tools.md`
for per-domain tooling. Guessing at hot spots is the dominant failure mode.

### Phase 4: HYPOTHESIZE and CHANGE

State one hypothesis targeting the profiled hot spot. Make one change. Run FLOOR
commands -- revert immediately if any fail.

### Phase 5: MEASURE

Run MEASURE N times. Compare median to baseline. Accept only if delta > variance
tolerance. Update ledger (`references/hc-ledger.md`). If accepted, new baseline.

### Phase 6: LOOP or STOP

Target reached: final report. K consecutive non-improving iterations: plateau
stop. Budget exhausted: report what worked and what remains.

---

## Ad-Hoc Workflow

For structured multi-phase work that does not fit the four modes above. Identify
the workflow from the table, load its reference, follow its phases exactly.

### Cost Gate

Ask first: does this need a multi-agent workflow? Skip the workflow when:
single-file mechanical edit (use `quick`), one agent satisfies the request
(direct dispatch), lookup/status/count (direct agent). Escalate only when the
request has independent subtasks, needs orthogonal verification, or names
"comprehensive / thorough / adversarial / tournament."

### Composable Patterns

| Pattern | What it does |
|---|---|
| Classify-and-act | Route by type up front; or classify-at-end |
| Fan-out-and-synthesize | Independent agents in parallel, barrier, one synthesizer |
| Adversarial verification | Executor builds, fresh skeptic refutes |
| Generate-and-filter | Over-generate candidates, gate keeps survivors |
| Tournament | N agents attempt same task; pairwise judges pick winner per round |
| Loop-until-done | Repeat until hard completion test passes |
| Quarantine | Read-only triage agent for untrusted content; separate privileged acting agent |

### Workflow Catalog

Load the reference for the matched workflow. `references/...` paths resolve
under `${CLAUDE_SKILL_DIR}`.

| Category | Workflow | Reference |
|----------|----------|-----------|
| Code Review | Comprehensive multi-wave | `references/comprehensive-review.md` |
| Debugging | Evidence-based diagnosis | `references/systematic-debugging.md` |
| Refactoring | Safe refactoring with test gates | `references/systematic-refactoring.md` |
| Research | Formal research with source gates | `references/research-pipeline.md` |
| Research | Research to article | `references/research-to-article.md` |
| Content | Article evaluation | `references/article-evaluation-pipeline.md` |
| Content | De-AI content | `references/de-ai-pipeline.md` |
| Content | Documentation | `references/doc-pipeline.md` |
| Exploration | Codebase exploration | `references/explore-pipeline.md` |
| Exploration | Multi-perspective analysis | `references/do-perspectives.md` |
| Creation | Skill creation | `references/skill-creation-pipeline.md` |
| Creation | Hook development | `references/hook-development-pipeline.md` |
| Creation | MCP server | `references/mcp-pipeline-builder.md` |
| Creation | Pipeline scaffolding | `references/pipeline-scaffolder.md` |
| Creation | Domain research | `references/domain-research.md` |
| Creation | Chain composition | `references/chain-composer.md` |
| Creation | Auto-pipeline generation | `references/auto-pipeline.md` |
| Upgrade | Agent/skill upgrade | `references/agent-upgrade.md` |
| Upgrade | System upgrade | `references/system-upgrade.md` |
| Upgrade | Toolkit improvement | `references/toolkit-improvement.md` |
| Testing | Pipeline test runner | `references/pipeline-test-runner.md` |
| Testing | Pipeline retro | `references/pipeline-retro.md` |
| GitHub | Profile rules extraction | `references/github-profile-rules.md` |
| Orchestration | Task orchestration | `references/workflow-orchestrator.md` |
| Orchestration | DAG composition | `references/dag-composition-patterns.md` |
| Orchestration | Compatibility matrix | `references/dag-compatibility-matrix.md` |
| Orchestration | Common DAG patterns | `references/dag-skill-patterns.md` |
| Orchestration | DAG examples | `references/dag-orchestration-examples.md` |
| Orchestration | DAG advanced | `references/dag-orchestration-advanced.md` |
| Orchestration | Feedback loop | `references/feedback-loop-construction.md` |

### Terminology

"Workflow" is the canonical term. "Pipeline" is the retained legacy alias --
kept for back-compat in routing keys, `meta.name` exports, and
`pipeline-index.json`. Use "workflow" in new prose; do not rename code
identifiers.

---

## Error Handling

| Error | Response |
|-------|----------|
| Mode ambiguous | Ask the user to clarify intent |
| Phase mismatch | Report current state, suggest correct next phase |
| Missing artifact | Route back to previous phase |
| Noisy harness (hill-climb) | Stop; report spread vs target improvement |
| Budget exhausted | Honest NOT-DONE report with per-criterion status |
| State file missing on wakeup | Report and stop; ask user to restate objective |
