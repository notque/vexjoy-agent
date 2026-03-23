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
version: 2.0.0
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

## What This Skill CANNOT Do
- Execute tasks without a plan (must complete BRAINSTORM and WRITE-PLAN first)
- Skip phase gates (all gates must pass before proceeding)
- Create tasks without absolute file paths and verification commands
- Handle trivial single-file edits (use direct editing instead)
- Proceed past blockers without user input

## Instructions

### Three-Phase Workflow Overview

1. **BRAINSTORM**: Refine requirements, explore approaches, select best option
2. **WRITE-PLAN**: Create detailed task breakdown with verification steps
3. **EXECUTE-PLAN**: Execute tasks sequentially or in parallel, verify each step

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

Prefer **multiple choice questions** when possible — easier to answer than open-ended. Open-ended only when truly necessary.

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

**PHASE GATE: Do NOT proceed to EXECUTE-PLAN phase until:**
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
T1 → T2 → T4
  ↘ T3 ↗
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
T1 → T2

## Notes
(Add notes during execution)
```

**Save location**: `plan/active/{descriptive-name}.md`

### Phase 3: EXECUTE-PLAN

**PHASE GATE: Do NOT mark workflow complete until:**
- [ ] All tasks have been attempted
- [ ] All verification commands have been run
- [ ] All passing tasks are logged with status
- [ ] Any failures have been documented with root cause
- [ ] Final status report has been generated

**Purpose**: Execute tasks from the plan, verify each step, handle blockers.

#### Step 1: Load and Validate Plan

Read the plan from `plan/active/{plan-name}.md` and verify:
- All tasks have absolute file paths
- All tasks have verification commands
- Dependencies are valid (no circular refs)
- Plan status is "Draft" or "In Progress"

Update plan status to "In Progress".

#### Step 2: Execute Tasks in Order

**For each task**:
1. **Check Dependencies**: Verify all prerequisite tasks completed successfully
2. **Report Start**: Log task start
3. **Execute Operations**: Perform the task operations
4. **Run Verification**: Execute verification command
5. **Evaluate Result**: Check against success criteria
6. **Report Completion**: Log task status and overall progress (e.g., "2/6 tasks complete")

#### Step 3: Handle Verification Failures

If verification fails, apply the [Autonomous Repair](../shared-patterns/autonomous-repair.md) pattern:

1. **Report Failure**: Document the error output and analysis
2. **Select Strategy** (decision tree):
   - **RETRY**: Error is specific and actionable (typo, missing import, wrong arg) — fix and re-verify. Consumes 1 repair attempt.
   - **DECOMPOSE**: Retry failed and task has independent sub-parts — break into sub-tasks (in-memory only, never modify the plan file). Consumes 1 repair attempt.
   - **PRUNE**: Task is genuinely unnecessary or already satisfied by prior task — skip with documented justification.
   - **ESCALATE**: Error is vague/systemic, budget exhausted, or sub-tasks also failed — ask user. Mandatory when repair budget (default: 2 attempts) is exhausted.
3. **Log Deviation**: Record every repair action (strategy, error, outcome, attempts consumed) in the execution summary.

#### Step 4: Handle Blockers

When encountering a blocker that cannot be automatically resolved, document the blocker type, details, and impact on downstream tasks. Ask user for resolution before proceeding.

#### Step 5: Report Final Status

After all tasks attempted, report:
- Total tasks, completed, failed, blocked counts
- Per-task summary with status
- Overall execution result

After successful execution, prompt user about plan lifecycle:
1. **Archive** to `plan/completed/YYYY-MM/` — work is done
2. **Keep active** — more work needed or waiting for merge
3. **Abandon** to `plan/abandoned/` — decided not to proceed (ask for reason)

## Error Handling

### Verification Failure Strategy

**Level 1: Auto-Fix** (if issue is obvious):
- Missing import, syntax error, simple typo
- Fix and retry verification

**Level 2: Rollback** (if changes broke something):
- Execute rollback commands from task definition
- Restore to pre-task state

**Level 3: User Escalation** (if unclear how to proceed):
- Document the failure and what was attempted
- Request user guidance

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Task verification timeout | Verification command took >2 minutes | Break task into smaller subtasks |
| Circular dependency detected | Tasks form a dependency cycle | Restructure tasks to remove cycle |
| File path is relative | Task used `./` path | Convert to absolute path |
| Task duration exceeds 5 min | Task too large for atomic execution | Break into multiple smaller tasks |

## Common Anti-Patterns

### Anti-Pattern 1: Skipping Brainstorm Phase

**Problem**: Jumping straight to creating tasks without clarifying requirements or exploring approaches.

**Why it fails**: No requirement clarification (OAuth? JWT?), no approach exploration, no constraint identification. Results in rework.

**Fix**: Complete all BRAINSTORM steps — clarify requirements, generate 2-3 approaches, select with documented rationale — before creating any tasks.

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

## Validation

To validate a workflow execution:
1. All phase gates passed (requirements clarified, approach selected)
2. Plan saved to `plan/active/` with absolute file paths
3. Each task has executable verification command
4. All verifications pass after execution

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Autonomous Repair](../shared-patterns/autonomous-repair.md) - Bounded self-repair with RETRY/DECOMPOSE/PRUNE/ESCALATE strategies

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Requirements are clear enough" | Ambiguity causes rework | Complete BRAINSTORM phase |
| "Tasks are roughly scoped" | Vague tasks can't be verified | Define exact file paths + verification |
| "Simple enough to skip planning" | Unplanned work has higher failure rate | Use BRAINSTORM → WRITE-PLAN → EXECUTE |
| "Let me just add this feature too" | Scope creep wastes time and tokens | Only implement what was requested |
