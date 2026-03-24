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
---

# Plans - Plan Lifecycle Management

## Operator Context

This skill operates as an operator for deterministic plan management, configuring Claude's behavior for structured task tracking through `scripts/plan-manager.py`. All plan mutations flow through the script; the LLM orchestrates but never edits plan files directly.

### Hardcoded Behaviors (Always Apply)
- **Script-Only Mutations**: ALL plan changes go through `plan-manager.py` -- never edit plan files by hand
- **Show Before Modify**: ALWAYS run `show` on a plan before any mutation (check, complete, abandon)
- **Stale Check on Entry**: ALWAYS run `list --stale` before executing any plan tasks
- **Full Output**: NEVER summarize or truncate script output -- show it completely to the user
- **User Confirmation**: NEVER complete or abandon a plan without explicit user confirmation

### Default Behaviors (ON unless disabled)
- **Human-Readable Output**: Pass `--human` flag for all display commands
- **Stale Plan Warnings**: Warn user about plans older than 7 days before proceeding
- **Task-Order Enforcement**: Work tasks in listed order unless user specifies otherwise
- **Status Logging**: Report current plan state after every mutation

### Optional Behaviors (OFF unless enabled)
- **Audit on Session Start**: Run `audit` across all active plans at session open
- **Auto-Complete Detection**: Suggest completing plans when all tasks are checked
- **Cross-Plan Dependencies**: Track dependencies between related plans

## What This Skill CAN Do
- Create new plans with structured phases and tasks
- List active plans, filter by staleness, show details
- Mark individual tasks as complete within a plan
- Archive completed plans to `completed/` directory
- Move abandoned plans to `abandoned/` with documented reason
- Audit all active plans for structural issues

## What This Skill CANNOT Do
- Execute plan tasks (it tracks them; other skills execute)
- Edit plan files directly (all mutations go through the script)
- Skip the stale-check gate before working on plans
- Complete or abandon plans without user confirmation
- Replace Claude Code's built-in `/plan` command (this is `/plans`)

---

## Instructions

### Phase 1: CHECK

**Goal**: Understand current plan landscape before any action.

```bash
python3 ~/.claude/scripts/plan-manager.py list --human
python3 ~/.claude/scripts/plan-manager.py list --stale --human
```

If stale plans exist (>7 days), warn user before proceeding.

**Gate**: Plan landscape is known. Stale plans are surfaced. Proceed only when gate passes.

### Phase 2: INSPECT

**Goal**: Understand the target plan's current state before mutation.

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks --human
```

Review remaining tasks, completed tasks, and overall progress.

**Gate**: Plan state is displayed to user. Proceed only when gate passes.

### Phase 3: MUTATE

**Goal**: Apply exactly the requested change.

| Action | Command |
|--------|---------|
| Create | `python3 ~/.claude/scripts/plan-manager.py create NAME` |
| Check task | `python3 ~/.claude/scripts/plan-manager.py check NAME TASK_NUM` |
| Complete | `python3 ~/.claude/scripts/plan-manager.py complete NAME` |
| Abandon | `python3 ~/.claude/scripts/plan-manager.py abandon NAME --reason "reason"` |

For **complete** and **abandon**: require explicit user confirmation before executing.

**Gate**: Mutation succeeded (exit code 0). Proceed only when gate passes.

### Phase 4: CONFIRM

**Goal**: Verify mutation applied correctly.

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --human
```

Display updated state to user. If exit code != 0, report error and stop.

**Gate**: Post-mutation state matches expectation. User sees final result.

---

## Error Handling

### Error: "Plan Not Found"
Cause: Typo in plan name or plan already archived
Solution:
1. Run `list --human` to show all active plans
2. Check `completed/` and `abandoned/` directories for archived plans
3. Confirm correct name with user before retrying

### Error: "Stale Plan Detected"
Cause: Plan has not been updated in >7 days
Solution:
1. Display the stale plan's current state to user
2. Ask: continue working, abandon, or update timeline?
3. Do NOT execute tasks from stale plans without explicit confirmation

### Error: "Script Exit Code Non-Zero"
Cause: Invalid arguments, missing plan, or filesystem issue
Solution:
1. Show the full error output to user (never summarize)
2. Check script arguments match expected format
3. Verify `scripts/plan-manager.py` exists and is executable

---

## Anti-Patterns

### Anti-Pattern 1: Editing Plan Files Directly
**What it looks like**: Using Write/Edit to modify a plan markdown file
**Why wrong**: Bypasses script validation, breaks audit trail, may corrupt format
**Do instead**: All mutations through `plan-manager.py`

### Anti-Pattern 2: Skipping Show Before Modify
**What it looks like**: Running `check` or `complete` without first running `show`
**Why wrong**: May mark wrong task, complete plan with remaining work, or act on stale state
**Do instead**: Always Phase 2 (INSPECT) before Phase 3 (MUTATE)

### Anti-Pattern 3: Summarizing Script Output
**What it looks like**: "The plan has 3 remaining tasks" instead of showing full output
**Why wrong**: User loses details, task descriptions, staleness info, and audit data
**Do instead**: Display complete script output, let user read it

### Anti-Pattern 4: Auto-Completing Without Confirmation
**What it looks like**: Detecting all tasks done and running `complete` automatically
**Why wrong**: User may want to add tasks, review work, or keep plan active
**Do instead**: Suggest completion, wait for explicit user confirmation

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Script Reference
- `scripts/plan-manager.py` - All plan CRUD operations
- Exit codes: 0 = success, 1 = error, 2 = warnings (e.g., stale plans)
- Default output is JSON; add `--human` for readable format
