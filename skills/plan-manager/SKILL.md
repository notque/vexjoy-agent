---
name: plan-manager
description: "Plan lifecycle management via plan-manager.py: list, create, check, complete, abandon plans."
version: 2.0.0
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "list plans"
    - "show plan"
    - "complete plan"
  category: process
---

# Plan Manager Skill

## Overview

This skill manages the complete lifecycle of task plans using a deterministic CLI-first pattern: all operations flow through `scripts/plan-manager.py`, never through manual file edits. This prevents stale plan execution, context drift, and loss of audit trails. Use this skill when the user needs to list, create, show, track, complete, or abandon plans — not for executing the tasks within plans themselves.

## Instructions

### Phase 1: ASSESS Plan State

**Goal**: Establish current plan state and surface any stale plans before proceeding with operations.

**Always start with staleness check** (because stale plans waste effort on obsolete work):

```bash
python3 ~/.claude/scripts/plan-manager.py list --stale
```

Surface any staleness warnings to user immediately. If stale plans exist, address them before proceeding with other operations.

**Then list active plans** (because you need context before making decisions):

```bash
python3 ~/.claude/scripts/plan-manager.py list --human
```

Show complete output to user. Never summarize or abbreviate — the raw output contains critical details about plan age, task counts, and status that the user needs to see.

**Gate**: Staleness check complete. User informed of plan state. Proceed only when gate passes.

### Phase 2: OPERATE - Execute the Requested Plan Action

**Goal**: Execute the requested plan operation with full context and validation.

**For showing a plan:**

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks
```

**For checking off a task:**

Re-read the plan first before marking tasks (because this keeps the plan's goals in your recency window and prevents context drift):

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
python3 ~/.claude/scripts/plan-manager.py check PLAN_NAME TASK_NUMBER
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks
```

Then show updated state to user, including which task was marked and remaining count.

**For completing a plan:**

Show full status first before completing (because you must verify all checked tasks and understand what you're completing):

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
# Ask user: "Complete this plan? (y/n)"
# On confirmation:
python3 ~/.claude/scripts/plan-manager.py complete PLAN_NAME
```

**For abandoning a plan:**

Show full status first (because context prevents premature abandonment), then request explicit reason (because the audit trail requires documented rationale):

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
# Ask user: "Why abandon this plan?"
python3 ~/.claude/scripts/plan-manager.py abandon PLAN_NAME --reason "User requested: [reason]"
```

**For creating a plan:**

Confirm the plan name (lowercase-kebab-case) and descriptive title with user first (because speculative plan creation creates clutter; only create when explicitly requested):

```bash
python3 ~/.claude/scripts/plan-manager.py create PLAN_NAME --title "Descriptive title"
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
```

**Gate**: Operation executed via CLI, never via manual file edit. Full output shown to user. State confirmed with follow-up `show`. Proceed only when gate passes.

### Phase 3: VERIFY - Confirm Successful State Change

**Goal**: Confirm operation succeeded and state is consistent.

**Step 1**: Run `show` on the affected plan to confirm changes took effect (because CLI operations must be validated).

**Step 2**: If lifecycle change (complete/abandon), verify the plan moved to the correct directory:

```bash
ls plan/completed/   # or plan/abandoned/
```

**Step 3**: Report final state to user with full output.

When errors occur during plan work, log them to the plan's "Errors Encountered" section (because this maintains a record for future sessions and prevents knowledge loss).

**Gate**: Plan state verified. User informed. Operation complete.

### Error: "Plan not found"
**Cause**: Plan name misspelled or plan already moved to completed/abandoned

**Solution**:
1. Run `list` to see available active plans
2. Check `plan/completed/` and `plan/abandoned/` directories
3. Verify spelling matches exactly (kebab-case)

### Error: "Task number out of range"
**Cause**: Task number does not exist in the plan

**Solution**:
1. Run `show PLAN_NAME --tasks` to see valid task numbers
2. Task numbers are 1-indexed; verify the correct number
3. Re-read plan to confirm task list hasn't changed

### Error: "Cannot complete: unchecked tasks"
**Cause**: Attempting to complete a plan with remaining tasks

**Solution**:
1. Run `show PLAN_NAME --tasks` to see remaining tasks
2. Either check remaining tasks first or ask user if they want to force-complete
3. Document why unchecked tasks are acceptable if force-completing

### Error: "Reason required for abandonment"
**Cause**: Missing `--reason` flag on abandon command

**Solution**: Always provide `--reason "..."` when abandoning — this is mandatory for the audit trail

---

## References

- **Plan format documentation**: `plan/README.md`
- **CLI implementation**: `scripts/plan-manager.py`
