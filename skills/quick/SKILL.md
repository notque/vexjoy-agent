---
name: quick
description: "Tracked lightweight execution with composable rigor flags: --discuss, --research, --full."
version: 1.0.0
user-invocable: true
argument-hint: "[--discuss] [--research] [--full] <task>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  force_route: true
  triggers:
    - quick task
    - small change
    - ad hoc task
    - add a flag
    - small refactor
    - targeted fix
  pairs_with:
    - fast
  complexity: Simple
  category: process
---

# /quick - Tracked Lightweight Execution

Quick fills the gap between zero-ceremony `/fast` (1-3 edits, no plan) and full-ceremony Simple+ (task_plan.md, agent routing, quality gates). The key design principle is **composable rigor**: the base mode is minimal (plan + execute), and users add process incrementally via flags rather than getting all-or-nothing ceremony.

**Flags** (all OFF by default):

| Flag | Effect |
|------|--------|
| `--discuss` | Add a pre-planning discussion phase to resolve ambiguities |
| `--research` | Add a research phase before planning to build context on unfamiliar code |
| `--full` | Add plan verification + full quality gates (tests, lint, diff review) |
| `--no-branch` | Skip feature branch creation, work on current branch |
| `--no-commit` | Skip the commit step (for batching multiple quick tasks) |

## Instructions

### Phase 0: SETUP

**Step 1: Read CLAUDE.md**

Read and follow the repository's CLAUDE.md before doing anything else, because repo-specific conventions override defaults and skipping this causes style/tooling mismatches.

**Step 2: Parse flags**

Extract `--discuss`, `--research`, `--full`, `--no-branch`, and `--no-commit` from the invocation. Everything remaining after flag extraction is the task description.

**Step 3: Scope check**

If the task involves multiple components, architectural changes, or needs parallel execution, redirect to `/do` instead because quick tasks are single-threaded by design -- parallelism means the task has outgrown this tier.

### Phase 1: DISCUSS (only with --discuss flag)

This phase activates when the user passes `--discuss` or the request contains signals of uncertainty ("not sure", "maybe", "could be", "what do you think").

**Step 1: Identify ambiguities**

Read the request and list specific questions:
- What exactly should change? (if underspecified)
- Which approach among alternatives? (if multiple valid paths)
- What are the acceptance criteria? (if success is unclear)

**Step 2: Present questions**

```
===================================================================
 QUICK DISCUSS: <task summary>
===================================================================

 Before planning, I need to resolve:

 1. <question>
 2. <question>

===================================================================
```

Wait for user response. Do not proceed until ambiguities are resolved.

**GATE**: All ambiguities resolved. Proceed to Phase 2 or Phase 3.

### Phase 2: RESEARCH (only with --research flag)

This phase activates when the user passes `--research` or the task touches code that needs investigation. Use `--research` when touching unfamiliar code because confidence about code behavior is not the same as correctness -- `/fast` exists for when you truly know.

**Step 1: Identify scope**

Determine which files and patterns need reading to understand the change.

**Step 2: Read and analyze**

Read relevant source files, tests, and configuration. Build a mental model of:
- Current behavior
- Where the change fits
- What might break

**Step 3: Summarize findings**

Present a brief (3-5 line) summary of what you learned and how it affects the plan.

**GATE**: Sufficient understanding to plan the change. Proceed to Phase 3.

### Phase 3: PLAN

**Step 1: Generate task ID**

Assign the task ID now, not later, because untracked tasks become invisible and "later" never comes.

Format: `YYMMDD-xxx` where xxx is Base36 sequential (0-9, a-z).

```bash
# Check STATE.md for today's tasks to determine next sequence
date_prefix=$(date +%y%m%d)
```

If STATE.md exists in the repo root, find the highest sequence number for today's date prefix and increment. If no tasks today, start at `001`. Use Base36 for the sequence: 001, 002, ... 009, 00a, 00b, ... 00z, 010, ...

If STATE.md is corrupted, scan git log for `Quick task YYMMDD-` patterns to find the true next ID. If a branch name collision occurs, increment the sequence number and try again.

**Step 2: Create inline plan**

Always display the inline plan, even for obvious tasks, because the plan catches misunderstandings before they become wrong edits and confirms alignment in 10 seconds that saves minutes. Do NOT write a task_plan.md file -- that is Simple+ tier, and using an inline plan here is the minimum viable ceremony.

```
===================================================================
 QUICK [task-id]: <description>
===================================================================

 Plan:
   1. <what to change in file X>
   2. <what to change in file Y>
   3. <why: brief rationale>

 Files: <file1>, <file2>
 Estimated edits: <N>

===================================================================
```

If estimated edits exceed 15, suggest upgrading because edit count is a scope signal regardless of difficulty:
```
This task estimates 15+ edits. Consider using /do for full planning
and agent routing. Proceed with /quick anyway? [Y/n]
```

If the task involves security, payments, or data migration, recommend `--full` because a one-line auth change can be catastrophic and risk is about impact, not size.

**Step 3: Create feature branch** (unless --no-branch)

Create a feature branch because small changes on main break the same as big ones:

```bash
git checkout -b quick/<task-id>-<brief-kebab-description>
```

If already on a non-main feature branch and `--no-branch` is set, stay on the current branch.

**GATE**: Task ID assigned, plan displayed, branch created. Proceed to Phase 4.

### Phase 4: EXECUTE

**Step 1: Make edits**

Execute the changes described in the plan. Track edit count throughout.

**Step 2: Scope monitoring**

- At 10 edits: display a warning -- "10 edits reached. Quick tasks typically stay under 15."
- At 15 edits: suggest upgrade -- "15 edits reached. This may benefit from /do with full planning. Continue? [Y/n]"
- No hard cap -- the user decides. Quick's scope is advisory, not enforced like Fast's 3-edit gate.

**Step 3: Verify changes** (base mode)

Run a quick sanity check:
```bash
# Check for syntax errors in edited files (language-appropriate)
# e.g., python3 -m py_compile file.py, go build ./..., tsc --noEmit
```

If `--full` flag is set, run the full quality gate instead (see Phase 5).

**GATE**: All planned edits complete. Sanity check passes.

### Phase 5: VERIFY (only with --full flag)

**Step 1: Run tests**

```bash
# Run tests for affected packages/modules only
# Do not run full test suite unless explicitly requested
```

**Step 2: Lint check**

Run the repo's configured linter on changed files.

**Step 3: Review changes**

```bash
git diff
```

Review the diff for:
- Unintended changes
- Missing error handling
- Broken imports

**GATE**: Tests pass, lint clean, diff reviewed. Proceed to Phase 6.

### Phase 6: COMMIT (skip with --no-commit)

**Step 1: Stage changes**

```bash
git add <specific-files>
```

Stage specific files, not `git add .`, to avoid accidental inclusions.

**Step 2: Commit**

Use conventional commit format because it enables automated changelogs and consistent history:

```bash
git commit -m "$(cat <<'EOF'
<type>: <description>

Quick task <task-id>
EOF
)"
```

Include the task ID in the commit body for traceability.

**GATE**: Commit succeeded. Verify with `git log -1 --oneline`.

### Phase 7: LOG

**Step 1: Update STATE.md**

Log the task to STATE.md because this is how tasks stay visible and cross-referenceable.

If STATE.md does not exist in the repo root, create it:

```markdown
# Task State

## Quick Tasks

| Date | ID | Description | Commit | Branch | Tier | Status |
|------|----|-------------|--------|--------|------|--------|
```

Append the new task:

```markdown
| YYYY-MM-DD | <task-id> | <description> | <short-hash> | <branch> | quick | done |
```

If the task was escalated from `/fast`, note the tier as `fast->quick`.

**Step 2: Display summary**

```
===================================================================
 QUICK [task-id]: COMPLETE
===================================================================

 Description: <description>
 Files edited: <N>
 Commit: <hash> on <branch>
 Flags: <--discuss, --research, --full, or "base">
 Logged: STATE.md

 Next steps:
   - Push: /pr-workflow
   - More work: /quick <next task>
   - Merge to parent: git merge quick/<task-id>-...

===================================================================
```

## Reference Material

### Examples

**Example 1: Base Mode**

User says: `/quick add --verbose flag to the CLI`
1. Generate ID: 260322-001
2. Plan: add flag definition, wire to handler, update help text (3 edits)
3. Create branch: `quick/260322-001-add-verbose-flag`
4. Execute edits, commit, log to STATE.md

**Example 2: With Research**

User says: `/quick --research fix the timeout bug in auth middleware`
1. RESEARCH: Read auth middleware, identify timeout source, trace call path
2. PLAN: change timeout value in config, update middleware to use it (2 edits)
3. EXECUTE, COMMIT, LOG

**Example 3: Escalated from Fast**

`/fast` hit 3-edit limit while fixing a bug across 5 files.
1. Quick picks up with context: "Continuing from /fast -- 3 files already edited"
2. PLAN: remaining 2 files to edit
3. EXECUTE remaining edits, COMMIT all changes, LOG as tier `fast->quick`

**Example 4: Full Rigor**

User says: `/quick --full update payment amount rounding logic`
1. PLAN: identify rounding function, change to banker's rounding
2. EXECUTE the edit
3. VERIFY: run payment tests, lint, review diff
4. COMMIT, LOG

### Task ID Format

Base36 sequence: `001, 002, ... 009, 00a, 00b, ... 00z, 010, ...`

Full ID: `YYMMDD-xxx` (e.g., `260322-001`, `260322-00a`)

## Error Handling

### Error: Task ID Collision
**Cause**: Two quick tasks started in the same second with the same sequence
**Solution**: Increment the sequence number. If STATE.md is corrupted, scan git log for `Quick task YYMMDD-` patterns to find the true next ID.

### Error: Scope Exceeds Quick Tier
**Cause**: Task requires 15+ edits, multiple components, or parallel work
**Solution**: Display upgrade suggestion. If user confirms, continue in quick mode. If user wants full ceremony, invoke `/do` with the original request.

### Error: Test Failure in --full Mode
**Cause**: Quality gate found issues with the changes
**Solution**: Fix the failing tests. If the fix requires significant additional work, note it in STATE.md and suggest a follow-up `/quick` task rather than expanding scope.

### Error: Branch Conflict
**Cause**: Branch `quick/<task-id>-...` already exists
**Solution**: Increment the task ID sequence number and try again.
