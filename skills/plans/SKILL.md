---
name: plans
description: |
  Deterministic plan lifecycle management via scripts/plan-manager.py: create,
  track, check, complete, and abandon task plans. Use when user says "/plans",
  needs to create a multi-phase plan, track progress on active plans, or manage
  plan lifecycle (complete, abandon, audit). Do NOT use for one-off tasks that
  need no tracking, feature implementation, or debugging workflows.
version: 2.0.0
user-invocable: true
argument-hint: "[status|list|show|check|complete|abandon]"
allowed-tools:
  - Read
  - Bash
  - Glob
routing:
  triggers:
    - "manage plans"
    - "plan lifecycle"
  category: process
---

> **Deprecated**: This skill is superseded by [plan-manager](../plan-manager/SKILL.md). Use `/plan-manager` instead.

# Plans - Plan Lifecycle Management

## Overview

This skill manages the full lifecycle of task plans through deterministic commands in `scripts/plan-manager.py`. Plans track multi-phase work with task-level granularity, enabling progress tracking, stale-plan detection, and structured completion. The skill routes all mutations through the script—never edit plan files directly—and enforces gates at key decision points.

**Scope**: Creating, listing, inspecting, checking off tasks, completing, and abandoning plans. Does NOT execute the tasks themselves (other skills do that) or replace Claude Code's built-in `/plan` command.

---

## Instructions

### Phase 1: CHECK (Stale Plans Gate)

Before any action, discover what plans exist and surface any that are stale (>7 days old). Always use `--human` flag for readable output.

```bash
python3 ~/.claude/scripts/plan-manager.py list --human
python3 ~/.claude/scripts/plan-manager.py list --stale --human
```

**Constraint**: If stale plans exist, warn the user and ask whether to proceed, abandon, or update the timeline. Never skip this gate.

### Phase 2: INSPECT (Show Before Modify)

Before any mutation (check, complete, abandon), display the plan's current state to the user.

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks --human
```

This surfaces task descriptions, remaining work, completion status, and staleness info. **Constraint**: Always run `show` before mutation—marking the wrong task or completing with remaining work is a critical error.

### Phase 3: MUTATE (Script-Only)

Apply the exact requested action via the script:

| Action | Command |
|--------|---------|
| Create | `python3 ~/.claude/scripts/plan-manager.py create NAME` |
| Check task | `python3 ~/.claude/scripts/plan-manager.py check NAME TASK_NUM` |
| Complete | `python3 ~/.claude/scripts/plan-manager.py complete NAME` |
| Abandon | `python3 ~/.claude/scripts/plan-manager.py abandon NAME --reason "reason"` |

**Constraint**: NEVER edit plan files with Read/Write/Edit tools. All mutations go through the script to maintain audit trail and validation. **Constraint**: For `complete` and `abandon`, require explicit user confirmation before executing—these are high-consequence actions.

**Gate**: Mutation succeeds (exit code 0) or fails cleanly with a clear error message.

### Phase 4: CONFIRM (Post-Mutation Verification)

Display the updated plan state to verify the mutation worked as expected.

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --human
```

**Constraint**: NEVER summarize or truncate script output—show the complete output to the user so they see task lists, completion status, and any warnings. If exit code != 0, report the error and stop.

---

## Error Handling

### Error: "Plan Not Found"
**Cause**: Typo in plan name or plan was already archived to `completed/` or `abandoned/`.

**Solution**:
1. Run `python3 ~/.claude/scripts/plan-manager.py list --human` to list all active plans
2. Check the `completed/` and `abandoned/` directories for archived plans
3. Confirm the correct plan name with the user before retrying

---

### Error: "Stale Plan Detected" (>7 Days Without Update)
**Cause**: Plan hasn't been modified in over 7 days and may no longer reflect current work.

**Solution**:
1. Display the stale plan's current state to the user using `show`
2. Ask explicitly: Continue working? Abandon? Update the plan timeline?
3. **Constraint**: Do NOT execute tasks from stale plans without explicit user confirmation

---

### Error: "Script Exit Code Non-Zero"
**Cause**: Invalid arguments, missing plan, filesystem permissions, or missing script file.

**Solution**:
1. Show the full error output to the user (never summarize)
2. Check that script arguments match expected format
3. Verify `scripts/plan-manager.py` exists and is executable
4. If persist: ask user to diagnose environment issue

---

### Common Anti-Patterns (Constraint Violations)

**Anti-Pattern: Editing Plan Files Directly**
- **Wrong**: Using Read/Write/Edit to modify a plan markdown file
- **Why**: Bypasses script validation, breaks audit trail, corrupts format
- **Correct**: All mutations through `plan-manager.py`

**Anti-Pattern: Skipping Show Before Mutation**
- **Wrong**: Running `check` or `complete` without first running `show`
- **Why**: Risk marking the wrong task, completing with remaining work, or acting on stale data
- **Correct**: Always Phase 2 (INSPECT) before Phase 3 (MUTATE)

**Anti-Pattern: Summarizing Script Output**
- **Wrong**: "The plan has 3 remaining tasks" instead of showing full output
- **Why**: User loses task descriptions, staleness info, completion details, and audit trail
- **Correct**: Display complete script output; let user read it

**Anti-Pattern: Auto-Completing Without Confirmation**
- **Wrong**: Detecting all tasks done and running `complete` automatically
- **Why**: User may want to add tasks, review work, or keep the plan active for tracking
- **Correct**: Suggest completion after all tasks checked; wait for explicit user confirmation

---

## References

### Script Reference
- **Location**: `scripts/plan-manager.py`
- **Exit codes**: 0 = success, 1 = error, 2 = warnings (e.g., stale plans detected)
- **Output format**: JSON by default; add `--human` flag for readable format
- **Mutations**: All plan changes must go through this script; direct file editing is forbidden
