# System upgrade

Load this reference when you orchestrate a toolkit upgrade: adapt skills, references, hooks, and scripts when Claude Code ships a release, the owner's goals change, or retro learnings graduate.

Covers:
- **Change signal parsing**: actionable items from Claude Code release notes, goal statements, and learning.db graduation candidates
- **Cross-system auditing**: skills, references, hooks, and routing tables affected by a change signal
- **Priority classification**: Critical / Important / Minor, with effort estimates and parallel dispatch groups
- **Orchestrated fan-out**: independent changes dispatched in parallel to `general-purpose` workers, each loading the matching reference (hooks: `~/.claude/skills/toolkit/references/hook-development.md`; skills and references: the `toolkit` skill)
- **Validation scoring**: `toolkit` before/after scoring

Run the `system-upgrade` pipeline through workflow dispatch. Follow its six phases and these pipeline principles:
- Show the plan before executing; apply the authorization rules in the pipeline's PLAN phase
- Reuse domain references — never implement domain changes inline when a reference covers them
- Parallel dispatch — independent changes run simultaneously, never sequentially
- Verify changes using the pipeline's VALIDATE phase; scoring is optional

## Rules

### Hardcoded Behaviors (Always Apply)
- **Authorization at Phase 3**: Present the ranked plan. Follow the pipeline’s PLAN rules for existing authorization, uncovered changes, and interactive requests.
- **Domain References for Implementation**: Route hook changes to a `general-purpose`
  worker whose prompt starts "Read ~/.claude/skills/toolkit/references/hook-development.md and follow it";
  route skill and reference changes to the `toolkit` skill.
  Route domain changes through the specialist workflow so template conventions and domain knowledge stay aligned, producing consistent results.
- **Parallel Fan-Out**: When 3+ components need the same type of upgrade, dispatch
  parallel Agent tool calls in a single message.
- **Branch Before Implement**: Create `chore/system-upgrade-YYYY-MM-DD` branch
  before Phase 4 begins.

### Default Behaviors (ON unless disabled)
- **Scoped Audit**: Default audit = 10 most-recently-modified skills + all hooks + all routing tables.
  Full audit only with "comprehensive" keyword. Always report: "Scanned N of M total components."
- **Dry-Run Plan Presentation**: Format Phase 3 output as a table with Tier, component,
  change type, and estimated effort.
- **Sync After Deploy**: After PR is created, remind user to restart Claude Code
  to pick up upgraded skills and hooks.

### Optional Behaviors (OFF unless enabled)
- **Comprehensive Audit**: Audit all skills and references (slow; enable with "comprehensive")
- **Interactive Planning**: Wait after presenting the plan when the user requests an interactive or plan-only session.
- **Evaluation Scoring**: Run toolkit when requested or when it can settle a specific uncertainty. Required validation still applies.

## Capabilities & Limitations

### What the Upgrade Covers
- Parse three trigger types: claude-release, goal-change, retro-driven
- Audit hooks, skills, references, and routing tables for affected components
- Classify changes as deprecate / upgrade / create-new / inject-pattern
- Dispatch parallel `general-purpose` workers, each with its domain reference, for independent change groups
- Score components with toolkit (before/after delta)
- Create branch, commit, sync to `~/.claude`, and create PR

### Out of Scope
- **Modify core scripts** (feature-state.py, plan-manager.py) — requires explicit user direction
- **Expand authorized scope** without the user’s agreement
- **Guarantee correctness** — validation phase catches regressions, but judgment has limits
- **Create new pipelines** — load `~/.claude/skills/workflow/references/pipeline-orchestrator.md` for that
- **Handle production deployments** beyond this repository

When asked to perform unavailable actions, explain the limitation and suggest the appropriate alternative.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Parsing release notes, extracting signals, building Change Manifest, retro graduation signals | `system-upgrade/upgrade-signal-parsing.md` | Routes to the matching deep reference |
| Auditing agents, skills, hooks, routing tables for stale patterns or affected components | `system-upgrade/component-audit-checklists.md` | Routes to the matching deep reference |
| Diagnosing orchestration failures, plan gate issues, inline edits, regression handling | `system-upgrade/upgrade-failure-modes.md` | Routes to the matching deep reference |

## Instructions

Call the Skill tool with `workflow`. Run the `system-upgrade` pipeline's six phases:

1. **CHANGELOG** — Parse the trigger, extract change signals, build Change Manifest. Each signal must include: (a) what changed, (b) which component types are affected, (c) urgency tier.
   > **STOP.** If you extracted 0 actionable signals, do not proceed. Ask the user for specifics.
2. **AUDIT** — Scan affected component types, produce Audit Report. Default scope: 10 most-recently-modified skills + all hooks. Report exact count of components scanned vs total.
   > **STOP.** Reading file names is not auditing. Have you opened and checked each affected component's frontmatter and body? If not, go back.
3. **PLAN** — Rank changes into exactly 3 tiers (Critical / Important / Minor), present as a table with component name, change type, effort estimate (S/M/L), and parallel group assignment. Apply the pipeline’s authorization rules.
   > **STOP.** Uncovered changes wait for approval; already authorized work continues.
4. **IMPLEMENT** — Dispatch `general-purpose` workers in parallel groups, each prompt naming the domain reference to load. For 3+ independent changes of the same type, use parallel Agent tool calls in a single message.
5. **VALIDATE** — Follow the pipeline’s verification rules. Report checks, findings, and any requested evaluation results. Resolve blocking regressions before delivery.
6. **DEPLOY** — Follow the pipeline’s PR and integration sequence. Sync only the accepted revision, through the coordinator when workers run in parallel.

Reuse phase instructions already loaded while they remain current. Reload when the source or scope changes.

Do not skip phases. Do not abbreviate the PLAN presentation.

## Output Format

Use the **Planning Schema**:

1. **Change Manifest** — parsed signals from the trigger
2. **Audit Report** — affected components with change type and rationale
3. **Upgrade Plan** — ranked table (Critical/Important/Minor) with effort estimates
4. **Implementation Log** — which workers dispatched with which reference, which edits made directly
5. **Validation Report** — checks and findings per component; scores when requested
6. **Deployment Summary** — branch, PR URL, sync status

## Error Handling

### Error: "No signals found in changelog"
Cause: Input too vague to extract actionable changes.
Solution: Ask the user for specifics. Quote the feature/change they're referencing.

### Error: "Domain worker incomplete"
Cause: A dispatched worker didn't finish its assignment.
Solution: Re-dispatch with narrower scope. Check for timeout or errors in the worker output.

### Error: "Regression in validation"
Cause: Validation found a regression.
Solution: Fix it within scope and rerun affected checks. Ask only if resolution needs an unapproved tradeoff. Report any requested evaluation score without treating it as proof of correctness.

### Error: "Sync to ~/.claude fails"
Cause: Sync script broken or path wrong.
Solution: Manual copy to `~/.claude/`. Report the broken sync path.

## Patterns to Detect and Fix

### Pattern 1: Skipping Plan Approval
**What it looks like**: Moving directly from AUDIT to IMPLEMENT
**Why wrong**: User loses control of what changes in their system
**Do instead**: Present the Phase 3 plan and apply its authorization rules.

### Pattern 2: Making All Changes Directly
**What it looks like**: Editing hook files inline instead of dispatching a worker that loads `hook-development.md`
**Why wrong**: Bypasses the reference's domain knowledge (event structure, performance requirements, template conventions)
**Do instead**: Route any non-trivial change to a worker that loads its domain reference

### Pattern 3: Unscoped Audit
**What it looks like**: Running comprehensive audit for every trigger
**Why wrong**: Auditing 120+ skills for a 2-hook change wastes time and creates noise
**Do instead**: Scope audit to the change signals. Comprehensive is opt-in.

## Blocker Criteria

Resolve routine issues from repository evidence and existing authorization. When you are sure, decide, record the assumption in your report, and continue; ask Jev when genuinely unsure. Ask only when these situations leave a material decision uncovered:

Rows marked **(owner)** guard production, destructive, credential, public-exposure, or persistence actions; stop and get explicit owner confirmation before acting on those.

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Plan exceeds authorized scope **(owner)** | Scope risk | "These additional changes are outside the request. Include them?" |
| Regression needs an unapproved tradeoff | Correctness risk | "Resolving this changes the requested behavior. Which outcome should we preserve?" |
| Change signal unclear | Wrong plan risk | "What specifically changed in [release/goal]? Give me the concrete feature." |
| Existing component covers the gap | Duplication risk | Reuse or extend it within scope; ask only if this changes the requested outcome. |

## Reference Files

Load these reference files when the task type matches:

| Task Type | Reference File |
|-----------|---------------|
| Parsing release notes, extracting signals, building Change Manifest, retro graduation signals | [upgrade-signal-parsing.md](system-upgrade/upgrade-signal-parsing.md) |
| Auditing agents, skills, hooks, routing tables for stale patterns or affected components | [component-audit-checklists.md](system-upgrade/component-audit-checklists.md) |
| Diagnosing orchestration failures, plan gate issues, inline edits, regression handling | [upgrade-failure-modes.md](system-upgrade/upgrade-failure-modes.md) |

- **Upgrade Signal Parsing**: [upgrade-signal-parsing.md](system-upgrade/upgrade-signal-parsing.md) — Change Manifest construction, signal-type classification, retro-driven signal queries
- **Component Audit Checklists**: [component-audit-checklists.md](system-upgrade/component-audit-checklists.md) — Per-component-type audit fields, detection commands, stale-pattern signals
- **Upgrade Failure Modes**: [upgrade-failure-modes.md](system-upgrade/upgrade-failure-modes.md) — Phase gate bypasses, inline edits, regression rationalization, parallel dispatch patterns

## Related

- **Pipeline**: [workflow system-upgrade](../../../process/workflow/references/system-upgrade.md)
- **Evaluation and routing tables**: [toolkit SKILL.md](../SKILL.md)
- **Learning DB**: [scripts/learning-db.py](../../../../scripts/learning-db.py)
