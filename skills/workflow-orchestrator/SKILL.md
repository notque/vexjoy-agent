---
name: workflow-orchestrator
user-invocable: false
description: |
  Three-phase task orchestration: BRAINSTORM requirements and approaches,
  WRITE-PLAN with atomic verifiable tasks, EXECUTE-PLAN with progress
  tracking. Use for complex multi-step tasks requiring coordination across
  multiple files or systems. Use for "orchestrate", "complex task", "plan
  and execute", "break this down", or "multi-step implementation". Do NOT
  use for single-file edits or tasks completable in under 2 minutes.
version: 3.0.0
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Task
---

# Workflow Orchestrator Skill

## Purpose

Orchestrate complex multi-step software development tasks using the BRAINSTORM / WRITE-PLAN / EXECUTE-PLAN pattern. Breaks ambiguous or complex work into well-defined, verifiable subtasks with clear progress tracking.

## Operator Context

This skill operates as an operator for complex task orchestration, configuring Claude's behavior for systematic multi-phase workflow execution.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before orchestration. Project instructions override default behaviors.
- **Over-Engineering Prevention**: Only create tasks for work that's directly requested. Keep plans simple and focused. No speculative features or flexibility that wasn't asked for.
- **Exact File Paths Required**: All tasks must specify absolute file paths, never relative paths or wildcards
- **Verification Mandatory**: Every task must include a verification step that confirms successful completion
- **Task Duration**: Individual tasks must be scoped to 2-5 minutes of work (break larger work into multiple tasks)
- **Dependency Declaration**: Tasks with dependencies must explicitly list prerequisite task IDs
- **Status Tracking**: After each task execution, report completion status and any blockers encountered
- **Context-Budget Awareness**: Monitor estimated context usage and adjust execution behavior by zone. Plans should target completion within 50% of context. Why: context exhaustion mid-execution produces silently degraded output with no recovery path.

  | Context Used | Zone | Behavior |
  |-------------|------|----------|
  | 0-30% | PEAK | Full execution, all quality gates, comprehensive verification |
  | 30-50% | GOOD | Full execution, all quality gates. Target plan completion within this zone. |
  | 50-70% | DEGRADING | Prioritize remaining critical tasks. Skip optional verification. Warn user. |
  | 70%+ | POOR | Complete only in-progress task. Create handoff artifacts ([Session Handoff](../../adr/069-session-handoff-system.md)). Stop accepting new tasks. |

  Zone transitions trigger explicit log entries: "Entering DEGRADING zone at ~52% context usage. 3 tasks remaining. Prioritizing critical path." These zones are planning heuristics based on estimated usage, not precise measurements.

- **Deviation Rules**: Numbered rules governing what the orchestrator may do autonomously during execution versus what requires human approval. Why: without explicit boundaries, the orchestrator either over-escalates (asking about typos) or under-escalates (silently making architectural changes).

  | Rule | Category | Action | Example |
  |------|----------|--------|---------|
  | 1 | Bug fix | Auto-fix | Typo in variable name, missing import, off-by-one error |
  | 2 | Missing critical functionality | Auto-add if clearly required by the plan | A function referenced in the plan but not yet created |
  | 3 | Blocking issue | Auto-fix environmental/dependency problems | Missing package, wrong version, permission issue |
  | 4 | Architectural change | **STOP and ask user** | Changing a data model, adding a new service, altering an API contract |

  Rules 1-3 are autonomous -- the orchestrator handles them without user input. Rule 4 is a hard stop. Every autonomous deviation is logged with: the rule number that authorized it, what was changed, and why. Deviation rules classify WHAT to fix; the [Autonomous Repair](../shared-patterns/autonomous-repair.md) pattern governs HOW MANY TIMES to try (default: 2 attempts per task).

### Default Behaviors (ON unless disabled)
- **Plan Directory Storage**: Save all plans to `plan/active/{plan-name}.md` instead of temp files. This enables plan discovery, tracking, and cleanup workflows.
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative.
- **Plan Lifecycle Management**: After workflow completion, ask user whether to archive plan to `plan/completed/` or keep active.
- **Progress Reporting**: Report progress after each task completion
- **Blocker Detection**: Detect and report blockers immediately when encountered
- **Status Updates**: Provide phase transition notifications
- **Rationale Logging**: Document decision rationale in brainstorm phase

### Optional Behaviors (OFF unless enabled)
- **Parallel Execution**: Execute independent tasks in parallel using Task tool (OFF by default - sequential is safer)
- **Automated Rollback**: Automatically revert changes if verification fails (OFF by default - manual review safer)
- **Time Tracking**: Log actual time taken per task vs estimated (OFF by default)
- **Dry Run Mode**: Generate plan without executing (OFF by default)

## What This Skill CAN Do
- Break complex tasks into atomic, verifiable subtasks (2-5 min each)
- Manage dependencies between subtasks
- Track progress with status reporting
- Handle verification failures with retry/rollback
- Manage plan lifecycle (create, execute, archive, abandon)
- Suggest parallelization opportunities
- Validate plans before execution via plan-checker integration
- Detect regressions across task groups during execution
- Autonomously fix Rule 1-3 deviations without user intervention
- Adapt execution behavior based on context-budget zone

## What This Skill CANNOT Do
- Execute tasks without a plan (must complete BRAINSTORM and WRITE-PLAN first)
- Skip phase gates (all gates must pass before proceeding)
- Create tasks without absolute file paths and verification commands
- Handle trivial single-file edits (use direct editing instead)
- Proceed past blockers without user input
- Make architectural changes autonomously (Deviation Rule 4 -- always requires user approval)
- Precisely measure context usage (zones are estimates, not metered values)

## Instructions

### Three-Phase Workflow Overview

1. **BRAINSTORM**: Refine requirements, explore approaches, select best option
2. **WRITE-PLAN**: Create detailed task breakdown with verification steps
3. **VALIDATE-PLAN**: Run plan-checker with bounded revision loop
4. **EXECUTE-PLAN**: Execute tasks sequentially or in parallel, verify each step

### Phase 1: BRAINSTORM

**PHASE GATE: Do NOT proceed to WRITE-PLAN phase until:**
- [ ] Requirements have been clarified (or user confirmed they're clear)
- [ ] At least 2 approaches have been considered
- [ ] Selected approach has documented rationale
- [ ] Constraints and dependencies are identified

**Purpose**: Transform ambiguous requirements into clear, actionable plans through Socratic refinement.

#### Step 1: Understand Requirements

Ask clarifying questions **one at a time** to understand:
- What is the actual problem being solved?
- What are the success criteria?
- What constraints exist (time, resources, compatibility)?
- What parts of the system are affected?

Prefer **multiple choice questions** when possible -- easier to answer than open-ended. Open-ended only when truly necessary.

**Example Multiple Choice**:
```
How should auth tokens be stored?
1. In-memory only (simpler, lost on restart)
2. Database (persistent, more setup)
3. Redis (fast, external dependency)
```

#### Step 2: Identify Constraints and Dependencies

Document:
- **Technical Constraints**: Language versions, library compatibility, API limitations
- **System Dependencies**: Files that must be modified together
- **External Dependencies**: Services, databases, APIs that must be available
- **Compatibility Requirements**: Backward compatibility, migration needs

#### Step 3: Generate Multiple Approaches

Brainstorm 2-3 approaches with pros, cons, complexity, and risk for each.

```markdown
## Approach 1: [Name]
**Pros**: [List advantages]
**Cons**: [List disadvantages]
**Complexity**: [Low/Medium/High]
**Risk**: [Low/Medium/High]
```

#### Step 4: Select Best Approach

Choose the approach that best balances complexity vs. benefit, risk vs. needs, time vs. deadline, and maintainability vs. short-term gains.

Document the selected approach, rationale for choosing it, how it addresses constraints, and why alternatives were rejected.

### Phase 2: WRITE-PLAN

**PHASE GATE: Do NOT proceed to VALIDATE-PLAN phase until:**
- [ ] All tasks have absolute file paths (no relative paths)
- [ ] All tasks have verification commands
- [ ] All tasks are scoped to 2-5 minutes
- [ ] Dependencies between tasks are documented
- [ ] Plan has been saved to a file

**Purpose**: Break down the selected approach into executable, verifiable tasks.

#### Step 1: Create Task Breakdown

Break work into tasks that are:
- **Atomic**: Each task does ONE thing
- **Time-Bounded**: 2-5 minutes per task
- **Verifiable**: Has clear success/failure criteria
- **Explicit**: Specifies exact file paths and operations

**Task format** (use this in plans):

```markdown
### T1: Create database migration for user preferences
- **Duration**: 3 minutes
- **Dependencies**: None
- **Files**: `/absolute/path/to/migrations/0001_user_preferences.py`
- **Operations**: Create migration file, add model, define schema
- **Verification**: `python manage.py check` exits 0
```

#### Step 2: Identify Task Dependencies

Create dependency graph. Tasks with no dependencies can potentially run in parallel. Tasks must wait for all dependencies to complete. Circular dependencies are not allowed.

```
T1 -> T2 -> T4
  \-> T3 -/
```

**Note on parallelization**: If independent task groups exist, note them in the plan. Suggest parallel execution mode to user if it would provide meaningful speedup.

#### Step 3: Define Verification Steps

Each task must have:
- **Command**: Exact command to verify success
- **Expected Output**: What should happen if successful
- **Success Criteria**: How to determine pass/fail

#### Step 4: Document the Plan

Save plans to the `plan/active/` directory using kebab-case descriptive names.

**Plan format**:

```markdown
# Plan: [Descriptive Title]

**Status**: Draft
**Created**: YYYY-MM-DD
**Priority**: [Low/Medium/High]
**Complexity**: [Low/Medium/High]

## Summary
[One-sentence description of the work]

## Context
[Why this work is needed]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Implementation Tasks

### T1: [Task title]
- **Duration**: X minutes
- **Dependencies**: None
- **Files**: `/absolute/path/to/file.py`
- **Operations**: [Specific operations]
- **Verification**: `command` exits 0

### T2: [Task title]
- **Duration**: X minutes
- **Dependencies**: T1
- **Files**: `/absolute/path/to/file.py`
- **Operations**: [Specific operations]
- **Verification**: `command` exits 0

## Dependency Graph
T1 -> T2

## Notes
(Add notes during execution)
```

**Save location**: `plan/active/{descriptive-name}.md`

### Phase 2.5: VALIDATE-PLAN

**PHASE GATE: Do NOT proceed to EXECUTE-PLAN phase until:**
- [ ] Plan-checker has evaluated the plan
- [ ] All blocker-severity findings are resolved (or documented as accepted risks after 3 revision iterations)
- [ ] Context-budget estimate confirms plan is achievable within ~50% of remaining context

**Purpose**: Catch plan-level defects before they waste an execution cycle. A poorly structured plan -- vague tasks, missing dependencies, implicit ordering -- produces predictable execution failures. Validating before execution is cheaper than discovering problems mid-implementation.

#### Step 1: Run Plan-Checker

Invoke the [plan-checker](../plan-checker/SKILL.md) against the saved plan. The plan-checker evaluates the plan across its verification dimensions, including:
- Every task has a clear completion criterion
- Task dependencies are explicit (no implicit ordering)
- No task depends on an artifact that no prior task produces
- Scope is bounded (no open-ended tasks like "improve performance")
- Plan is achievable within ~50% of remaining context (context-budget check)

The plan-checker produces a PASS/BLOCK verdict with structured findings.

#### Step 2: Bounded Revision Loop

If the plan-checker finds issues:

```
CHECK -> issues found -> REVISE plan -> CHECK again -> max 3 iterations
```

1. Review each finding (dimension, severity, description, fix hint)
2. Revise the plan to address blocker-severity findings first, then warnings
3. Re-run the plan-checker on the revised plan
4. Repeat up to **3 iterations maximum**

If issues persist after 3 iterations, log the remaining issues as accepted risks in the plan's Notes section and proceed to execution. An imperfect plan executed is better than a perfect plan never started. The 3-iteration limit prevents infinite planning loops -- if a plan cannot pass validation in 3 revisions, the issues are likely structural and will surface clearly during execution.

#### Step 3: Log Validation Outcome

Record in the plan file:
- Plan-checker verdict (PASS / PASS-WITH-WARNINGS / BLOCK-OVERRIDDEN)
- Number of revision iterations used
- Any accepted risks from unresolved findings

### Phase 3: EXECUTE-PLAN

**PHASE GATE: Do NOT mark workflow complete until:**
- [ ] All tasks have been attempted
- [ ] All verification commands have been run
- [ ] All passing tasks are logged with status
- [ ] Any failures have been documented with root cause
- [ ] Regression checks have passed for prior task groups
- [ ] Final status report has been generated

**Purpose**: Execute tasks from the plan, verify each step, handle blockers.

#### Step 1: Load and Validate Plan

Read the plan from `plan/active/{plan-name}.md` and verify:
- All tasks have absolute file paths
- All tasks have verification commands
- Dependencies are valid (no circular refs)
- Plan status is "Draft" or "In Progress"
- Plan-checker validation has been completed (Phase 2.5)

Update plan status to "In Progress".

#### Step 2: Execute Tasks in Order

**For each task**:
1. **Check Dependencies**: Verify all prerequisite tasks completed successfully
2. **Report Start**: Log task start and current context-budget zone
3. **Execute Operations**: Perform the task operations
4. **Apply Deviation Rules**: If unexpected issues arise during execution, classify by rule number (1-3: auto-fix with logged justification; 4: stop and ask user). See Deviation Rules in Hardcoded Behaviors.
5. **Run Verification**: Execute verification command
6. **Evaluate Result**: Check against success criteria
7. **Report Completion**: Log task status and overall progress (e.g., "2/6 tasks complete")

#### Step 3: Regression Gate

Before verifying the current task group, re-run verification checks for prior completed task groups. Why: Task 5 may silently break what Task 3 built. Independent per-task verification misses cross-task regressions that compound into harder-to-diagnose failures later.

**Regression check protocol**:

```
After Task Group 1 executes -> verify Group 1
After Task Group 2 executes -> verify Group 1 (regression) -> verify Group 2
After Task Group 3 executes -> verify Groups 1+2 (regression) -> verify Group 3
```

**When a regression is detected**:
1. Identify which task in the current group broke which prior task's verification
2. Attempt autonomous repair on the current group's task, constrained to not re-break the prior task. Apply Deviation Rules to classify the fix (typically Rule 1: bug fix).
3. If repair fails after the repair budget (default: 2 attempts), ESCALATE with the specific regression identified -- include both what broke and what caused it.

**Scaling for large plans**: Full regression checking on every prior group is the default for plans with 5 or fewer task groups. For plans with more than 5 groups, check only the immediately preceding group to avoid consuming excessive context on re-verification. The tradeoff: less thorough regression detection, but more context available for actual execution.

**Task groups**: In sequential execution, each task is its own group. When wave-based parallel execution is enabled (see [Autonomous Repair](../shared-patterns/autonomous-repair.md)), each wave forms a task group. Regression checks happen between groups, not between individual tasks within a group.

#### Step 4: Handle Verification Failures

If verification fails, apply the [Autonomous Repair](../shared-patterns/autonomous-repair.md) pattern:

1. **Report Failure**: Document the error output and analysis
2. **Classify by Deviation Rule**: Determine if the failure falls under Rule 1-3 (auto-fix) or Rule 4 (stop and ask). This classification happens before strategy selection -- if it's Rule 4, ESCALATE immediately regardless of repair budget.
3. **Select Strategy** (decision tree, for Rule 1-3 failures only):
   - **RETRY**: Error is specific and actionable (typo, missing import, wrong arg) -- fix and re-verify. Consumes 1 repair attempt.
   - **DECOMPOSE**: Retry failed and task has independent sub-parts -- break into sub-tasks (in-memory only, never modify the plan file). Consumes 1 repair attempt.
   - **PRUNE**: Task is genuinely unnecessary or already satisfied by prior task -- skip with documented justification.
   - **ESCALATE**: Error is vague/systemic, budget exhausted, or sub-tasks also failed -- ask user. Mandatory when repair budget (default: 2 attempts) is exhausted.
4. **Log Deviation**: Record every repair action (rule number, strategy, error, outcome, attempts consumed) in the execution summary.

#### Step 5: Handle Blockers

When encountering a blocker that cannot be automatically resolved, document the blocker type, details, and impact on downstream tasks. Ask user for resolution before proceeding.

#### Step 6: Report Final Status

After all tasks attempted, report:
- Total tasks, completed, failed, blocked counts
- Per-task summary with status
- Deviation log (all autonomous fixes with rule numbers)
- Regression check results (pass/fail per group)
- Context-budget zone at completion
- Overall execution result

After successful execution, prompt user about plan lifecycle:
1. **Archive** to `plan/completed/YYYY-MM/` -- work is done
2. **Keep active** -- more work needed or waiting for merge
3. **Abandon** to `plan/abandoned/` -- decided not to proceed (ask for reason)

## Error Handling

### Verification Failure Strategy

**Level 1: Auto-Fix** (Deviation Rules 1-3):
- Missing import, syntax error, simple typo (Rule 1)
- Missing function clearly required by the plan (Rule 2)
- Dependency or environment issue (Rule 3)
- Fix and retry verification

**Level 2: Rollback** (if changes broke something):
- Execute rollback commands from task definition
- Restore to pre-task state

**Level 3: User Escalation** (Deviation Rule 4, or budget exhausted):
- Architectural changes require explicit user approval
- Document the failure and what was attempted
- Request user guidance

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Task verification timeout | Verification command took >2 minutes | Break task into smaller subtasks |
| Circular dependency detected | Tasks form a dependency cycle | Restructure tasks to remove cycle |
| File path is relative | Task used `./` path | Convert to absolute path |
| Task duration exceeds 5 min | Task too large for atomic execution | Break into multiple smaller tasks |
| Plan-checker blocker after 3 revisions | Plan has structural issues that revision cannot fix | Log as accepted risk, proceed with awareness, or ask user to restructure |
| Regression detected | Current task broke prior task's verification | Identify the breaking change, repair without re-breaking prior task |
| Context entering DEGRADING zone | >50% context consumed with tasks remaining | Prioritize critical-path tasks, skip optional verification, warn user |
| Context entering POOR zone | >70% context consumed | Complete only in-progress task, create handoff artifacts, stop |

## Common Anti-Patterns

### Anti-Pattern 1: Skipping Brainstorm Phase

**Problem**: Jumping straight to creating tasks without clarifying requirements or exploring approaches.

**Why it fails**: No requirement clarification (OAuth? JWT?), no approach exploration, no constraint identification. Results in rework.

**Fix**: Complete all BRAINSTORM steps -- clarify requirements, generate 2-3 approaches, select with documented rationale -- before creating any tasks.

### Anti-Pattern 2: Vague Task Definitions

**Problem**: Tasks with descriptions like "Fix the database", file references like "database files", and verification like "check it".

**Why it fails**: No absolute file paths, no specific operations, impossible to verify, cannot be executed by independent subagent.

**Fix**: Every task must have absolute file paths, specific operations, and executable verification commands with clear success criteria.

### Anti-Pattern 3: Creating Unnecessary Orchestration

**Problem**: Using the full BRAINSTORM/WRITE-PLAN/EXECUTE-PLAN workflow for a typo fix or single-file edit.

**Why it fails**: Simple single-file edits don't need orchestration. Tasks under 2 minutes should use direct editing.

**Fix**: Only orchestrate when work spans multiple files/systems and requires coordination. Use direct editing for everything else.

### Anti-Pattern 4: Speculative Feature Addition

**Problem**: User asks for a login form, assistant plans a comprehensive auth system with OAuth, 2FA, role-based permissions, and audit logging.

**Why it fails**: Adding unrequested features violates "only implement what's requested". Massive scope increase without confirmation.

**Fix**: Implement exactly what was requested. If related features seem useful, ask the user before expanding scope.

### Anti-Pattern 5: Skipping Plan Validation

**Problem**: Proceeding directly from WRITE-PLAN to EXECUTE-PLAN without running plan-checker.

**Why it fails**: A plan that looks reasonable at a glance may have vague tasks, missing dependencies, or scope that exceeds the context budget. These defects are discovered mid-execution, wasting an entire execution cycle. Validation is cheaper than rework.

**Fix**: Always run VALIDATE-PLAN (Phase 2.5) between WRITE-PLAN and EXECUTE-PLAN. The bounded revision loop (max 3 iterations) prevents infinite planning while catching major issues.

### Anti-Pattern 6: Ignoring Regressions

**Problem**: Verifying only the current task without checking whether prior tasks' outputs remain valid.

**Why it fails**: Task N may silently break what Task N-2 built. Without regression checks, these breaks compound -- by the time they surface, the root cause is buried under subsequent changes.

**Fix**: Run regression gate checks on prior task groups before verifying the current group. For plans with 5 or fewer groups, check all prior groups. For larger plans, check at least the immediately preceding group.

### Anti-Pattern 7: Auto-Fixing Architectural Changes

**Problem**: Treating an architectural change (new service, altered API contract, data model change) as a simple bug fix and applying it autonomously.

**Why it fails**: Architectural changes have cascading effects the orchestrator cannot fully anticipate. A "quick fix" to a data model can break consumers, invalidate migrations, or create backward-compatibility issues.

**Fix**: Classify every autonomous fix by Deviation Rule number. If it's Rule 4 (architectural change), STOP and ask the user. When in doubt about the classification, escalate -- false escalation wastes seconds; false autonomy wastes hours.

## Validation

To validate a workflow execution:
1. All phase gates passed (requirements clarified, approach selected)
2. Plan saved to `plan/active/` with absolute file paths
3. Plan-checker validation completed (PASS, PASS-WITH-WARNINGS, or BLOCK-OVERRIDDEN with documented risks)
4. Each task has executable verification command
5. All verifications pass after execution
6. Regression checks pass for all prior task groups
7. All autonomous deviations logged with rule numbers

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Autonomous Repair](../shared-patterns/autonomous-repair.md) - Bounded self-repair with RETRY/DECOMPOSE/PRUNE/ESCALATE strategies

Related skills and ADRs:
- [Plan Checker](../plan-checker/SKILL.md) - Pre-execution plan validation (ADR-074)
- [ADR-076: Autonomous Repair Mechanism](../../adr/076-autonomous-repair-mechanism.md) - Repair strategies and budget enforcement
- [ADR-079: Workflow Orchestrator Enhancements](../../adr/079-workflow-orchestrator-enhancements.md) - Plan validation, context budget, deviation rules, regression gates
- [ADR-069: Session Handoff System](../../adr/069-session-handoff-system.md) - Handoff artifacts for POOR context zone

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Requirements are clear enough" | Ambiguity causes rework | Complete BRAINSTORM phase |
| "Tasks are roughly scoped" | Vague tasks can't be verified | Define exact file paths + verification |
| "Simple enough to skip planning" | Unplanned work has higher failure rate | Use BRAINSTORM -> WRITE-PLAN -> EXECUTE |
| "Let me just add this feature too" | Scope creep wastes time and tokens | Only implement what was requested |
| "Plan looks fine, skip validation" | Plans that look fine still have hidden dependency gaps and vague tasks | Run VALIDATE-PLAN -- it catches what eyeballing misses |
| "One more revision will perfect it" | Diminishing returns after 3 iterations; execution surfaces remaining issues faster | Stop at 3 iterations, log remaining issues as accepted risks |
| "This architectural change is small enough to auto-fix" | Small architectural changes still have cascading effects | Deviation Rule 4: STOP and ask. Always. |
| "Prior tasks are fine, no need to re-check" | Cross-task regressions are silent until they compound | Run regression gate between task groups |
| "Context is probably fine" | "Probably" is how you end up with degraded output and no handoff | Check context zone; act on DEGRADING/POOR transitions |
