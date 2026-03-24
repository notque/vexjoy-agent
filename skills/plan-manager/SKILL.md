---
name: plan-manager
description: |
  Deterministic plan lifecycle management via scripts/plan-manager.py CLI.
  Use when user asks to list, show, create, check, complete, or abandon plans,
  or when session starts and stale plans need surfacing. Use for "check plans",
  "what's on our plan", "mark task done", "finish this plan", or "create a plan".
  Do NOT use for executing plan tasks, modifying plan content directly, or
  performance/refactoring work unrelated to plan tracking.
version: 2.0.0
user-invocable: false
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

## Operator Context

This skill operates as an operator for plan lifecycle management, configuring Claude's behavior for consistent, deterministic plan operations that prevent stale plan execution and context drift. It implements the **CLI-First** pattern -- all lifecycle operations go through `scripts/plan-manager.py`, never manual file edits.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Over-Engineering Prevention**: Only perform requested plan operations. No speculative plan creation, no "while I'm here" cleanup of other plans
- **Staleness Check Required**: ALWAYS run `list --stale` before executing any plan tasks
- **Re-read Before Decisions**: Re-read plan via `show` before any decision that affects task direction
- **Show Before Modify**: ALWAYS run `show PLAN_NAME` before completing or abandoning a plan
- **Complete Output Display**: Show full script output to user; never summarize as "plan updated"
- **CLI-Only Lifecycle**: Use `check`, `complete`, `abandon` commands; never edit plan files directly for lifecycle changes
- **Error Logging to Plan**: When errors occur during plan work, log them to the plan's "Errors Encountered" section

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it
- **Warning Escalation**: Surface all staleness warnings prominently to user before proceeding
- **Confirmation Required**: Ask for explicit confirmation before lifecycle changes (complete/abandon)
- **Task Context Display**: When checking off tasks, show which task was marked and remaining count
- **Audit Trail**: Always provide `--reason` with abandonment operations
- **Re-validation After Changes**: Run `show` after any `check`, `complete`, or `create` to confirm state

### Optional Behaviors (OFF unless enabled)
- **Batch Operations**: Process multiple plans in sequence (only if explicitly requested)
- **Auto-create Plans**: Create plans only when user explicitly requests plan creation
- **Skip Confirmation**: Skip confirmation dialogs only when user requests fast mode

## What This Skill CAN Do
- List all active plans with staleness warnings
- Show plan details, remaining tasks, and status
- Check off completed tasks within plans
- Move plans to completed or abandoned states
- Create new plans with proper structure
- Audit plan directory for structural issues

## What This Skill CANNOT Do
- Execute plan tasks (only tracks completion status)
- Modify plan content directly (only lifecycle operations via CLI)
- Auto-complete stale plans without user approval
- Delete plans permanently (only move to abandoned)
- Skip the staleness check at session start

---

## Instructions

### Phase 1: ASSESS

**Goal**: Establish current plan state before any operations.

**Step 1: Check for stale plans**

```bash
python3 ~/.claude/scripts/plan-manager.py list --stale
```

Surface any staleness warnings to user immediately. If stale plans exist, address them before proceeding with other operations.

**Step 2: List active plans**

```bash
python3 ~/.claude/scripts/plan-manager.py list --human
```

Show complete output to user. Never summarize.

**Gate**: Staleness check complete. User informed of plan state. Proceed only when gate passes.

### Phase 2: OPERATE

**Goal**: Execute the requested plan operation with full validation.

**For showing a plan:**

```bash
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks
```

**For checking off a task:**

```bash
# Re-read plan first (keeps goals in recency window)
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
# Mark task complete
python3 ~/.claude/scripts/plan-manager.py check PLAN_NAME TASK_NUMBER
# Confirm updated state
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME --tasks
```

**For completing a plan:**

```bash
# Show full status first (MANDATORY)
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
# Ask user: "Complete this plan? (y/n)"
# On confirmation:
python3 ~/.claude/scripts/plan-manager.py complete PLAN_NAME
```

**For abandoning a plan:**

```bash
# Show full status first (MANDATORY)
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
# Ask user for reason
python3 ~/.claude/scripts/plan-manager.py abandon PLAN_NAME --reason "User requested: [reason]"
```

**For creating a plan:**

```bash
# Confirm name (lowercase-kebab-case) and title with user first
python3 ~/.claude/scripts/plan-manager.py create PLAN_NAME --title "Descriptive title"
python3 ~/.claude/scripts/plan-manager.py show PLAN_NAME
```

**Gate**: Operation executed via CLI. Output shown to user in full. State confirmed with follow-up `show`. Proceed only when gate passes.

### Phase 3: VERIFY

**Goal**: Confirm operation succeeded and state is consistent.

**Step 1**: Run `show` on the affected plan to confirm changes took effect.

**Step 2**: If lifecycle change (complete/abandon), verify the plan moved:

```bash
ls plan/completed/   # or plan/abandoned/
```

**Step 3**: Report final state to user with full output.

**Gate**: Plan state verified. User informed. Operation complete.

---

## Command Reference

| User Intent | Command | Example |
|-------------|---------|---------|
| "what's on our plan" | `list` | `python3 ~/.claude/scripts/plan-manager.py list --human` |
| "check for stale plans" | `list --stale` | `python3 ~/.claude/scripts/plan-manager.py list --stale` |
| "show me plan X" | `show PLAN_NAME` | `python3 ~/.claude/scripts/plan-manager.py show add-auth` |
| "what tasks remain" | `show --tasks` | `python3 ~/.claude/scripts/plan-manager.py show add-auth --tasks` |
| "mark task done" | `check PLAN_NAME N` | `python3 ~/.claude/scripts/plan-manager.py check add-auth 3` |
| "finish this plan" | `complete PLAN_NAME` | `python3 ~/.claude/scripts/plan-manager.py complete add-auth` |
| "stop this plan" | `abandon PLAN_NAME` | `python3 ~/.claude/scripts/plan-manager.py abandon add-auth --reason "..."` |
| "create a plan for X" | `create PLAN_NAME` | `python3 ~/.claude/scripts/plan-manager.py create add-auth --title "..."` |
| "audit plans" | `audit` | `python3 ~/.claude/scripts/plan-manager.py audit` |

### Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Continue normally |
| 1 | Error | Stop and report error message to user |
| 2 | Warning | Continue but inform user of warnings |

---

## Error Handling

### Error: "Plan not found"
Cause: Plan name misspelled or plan already moved to completed/abandoned
Solution:
1. Run `list` to see available active plans
2. Check `plan/completed/` and `plan/abandoned/` directories
3. Verify spelling matches exactly (kebab-case)

### Error: "Task number out of range"
Cause: Task number does not exist in the plan
Solution:
1. Run `show PLAN_NAME --tasks` to see valid task numbers
2. Task numbers are 1-indexed; verify the correct number
3. Re-read plan to confirm task list hasn't changed

### Error: "Cannot complete: unchecked tasks"
Cause: Attempting to complete a plan with remaining tasks
Solution:
1. Run `show PLAN_NAME --tasks` to see remaining tasks
2. Either check remaining tasks first or ask user if they want to force-complete
3. Document why unchecked tasks are acceptable if force-completing

### Error: "Reason required for abandonment"
Cause: Missing `--reason` flag on abandon command
Solution: Always provide `--reason "..."` when abandoning -- this is mandatory for the audit trail

---

## Anti-Patterns

### Anti-Pattern 1: Executing Without Staleness Check
**What it looks like**: User says "let's work on the auth plan" and assistant immediately starts tasks
**Why wrong**: Plan may be 30 days old with outdated requirements. Stale plans waste effort on obsolete work.
**Do instead**: Run `list --stale` first. Surface warnings. Then proceed.

### Anti-Pattern 2: Completing Without Showing
**What it looks like**: Running `complete auth-plan` without first running `show auth-plan`
**Why wrong**: May complete plan with unchecked tasks, losing track of incomplete work.
**Do instead**: Always `show` before `complete` or `abandon`. Review output. Then proceed.

### Anti-Pattern 3: Summarizing Script Output
**What it looks like**: "You have 3 active plans and 1 is stale" instead of showing full CLI output
**Why wrong**: Hides which plan is stale, how stale, what tasks remain. User loses critical detail.
**Do instead**: Show complete script output. Let the user read the details.

### Anti-Pattern 4: Manual Plan File Editing
**What it looks like**: Using Edit tool to modify `plan/active/auth-plan.md` directly for lifecycle changes
**Why wrong**: Bypasses CLI validation. May corrupt plan format. Loses audit trail.
**Do instead**: Use `check`, `complete`, `abandon` commands. Only edit directly when adding new tasks to plan content.

### Anti-Pattern 5: Creating Plans Without User Confirmation
**What it looks like**: User says "we should add authentication" and assistant immediately creates a plan
**Why wrong**: User may want to discuss scope first. Creates clutter with unwanted plans.
**Do instead**: Ask "Would you like me to create a plan for this? What should it be called and what tasks should it include?"

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Plan looks current enough" | Staleness dates matter, not appearance | Run `list --stale` first |
| "Tasks seem mostly done" | Check marks are source of truth | Run `show --tasks` first |
| "I'll mark it complete later" | Lifecycle drift causes stale plans | Complete or abandon promptly |
| "The script is slow, I'll check manually" | Manual checks miss edge cases | Always use the CLI |
| "Plan is obvious, no need to show first" | Context prevents mistakes | Always `show` before `complete`/`abandon` |

### Reference Files
- Plan format documentation: `plan/README.md`
- CLI implementation: `scripts/plan-manager.py`
