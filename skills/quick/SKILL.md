---
name: quick
description: |
  Tracked lightweight execution with composable rigor flags for tasks between
  a typo fix and a full feature. Plan + execute with optional --discuss,
  --research, and --full flags to add rigor incrementally. Use for "quick task",
  "small change", "ad hoc task", "add a flag", "extract function", "small
  refactor", "fix bug in X". Do NOT use for multi-component features,
  architectural changes, or anything needing wave-based parallel execution —
  those are Simple+ tier.
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
  triggers:
    - quick task
    - small change
    - ad hoc task
    - add a flag
    - extract function
    - small refactor
    - targeted fix
  pairs_with:
    - fast
  complexity: Simple
  category: process
---

# /quick - Tracked Lightweight Execution

## Operator Context

This skill implements the Quick tier from the five-tier task hierarchy (Fast > Quick > Simple > Medium > Complex). It fills the gap between zero-ceremony `/fast` (1-3 edits, no plan) and full-ceremony Simple+ (task_plan.md, agent routing, quality gates). Quick tasks get a lightweight plan and tracking without the overhead of the full pipeline.

The key design principle is **composable rigor**: the base mode is minimal (plan + execute), and users add process incrementally via flags rather than getting all-or-nothing ceremony.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution.
- **Task ID Assignment**: Every quick task gets a unique ID in YYMMDD-xxx format (Base36 sequence). This enables tracking and cross-referencing.
- **Inline Plan**: Create a brief inline plan (not a full task_plan.md) before executing. The plan is 3-5 lines: what changes, which files, why. This is the minimum viable plan — enough to catch misunderstandings before editing.
- **STATE.md Logging**: Log task ID, description, status, and commit hash to STATE.md.
- **Branch Safety**: Create a feature branch if on main/master.
- **Commit After Execute**: Every quick task ends with a commit.
- **No Parallel Execution**: Quick tasks are single-threaded. If parallelism is needed, upgrade to Simple+.

### Default Behaviors (ON unless disabled)
- **Feature Branch Per Task**: Create `quick/<task-id>-<description>` branch for each task. This keeps quick work isolated and reviewable.
- **Conventional Commits**: Use conventional commit format.
- **Edit Tracking**: Count edits for scope awareness (warn at 10+, suggest upgrade at 15+).

### Optional Behaviors (OFF unless enabled)
- **`--discuss`**: Add a pre-planning discussion phase to resolve ambiguities before committing to a plan. Use when requirements are unclear or the user says "I'm not sure exactly what I want."
- **`--research`**: Add a research phase before planning to understand existing code, read related files, and build context. Use when the change touches unfamiliar code.
- **`--full`**: Add plan verification + full quality gates after execution. Use when the change is small but high-risk (auth, payments, data migration).
- **`--no-branch`**: Skip feature branch creation, work on current branch. Use when contributing to an existing feature branch.
- **`--no-commit`**: Skip the commit step. Use when batching multiple quick tasks into one commit.

## What This Skill CAN Do
- Plan and execute targeted code changes (4-15 file edits)
- Track tasks with unique IDs for auditability
- Compose rigor levels via flags (--discuss, --research, --full)
- Create isolated feature branches per task
- Escalate from /fast when scope is exceeded

## What This Skill CANNOT Do
- Spawn subagents or parallel workers (upgrade to Simple+)
- Manage multi-component features (use feature lifecycle skills)
- Run wave-based parallel execution (use dispatching-parallel-agents)
- Replace full task_plan.md planning (that is Simple+ tier)

---

## Instructions

### Phase 0: DISCUSS (only with --discuss flag)

**Goal**: Resolve ambiguities before planning.

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

**GATE**: All ambiguities resolved. Proceed to Phase 0.5 or Phase 1.

### Phase 0.5: RESEARCH (only with --research flag)

**Goal**: Build understanding of the relevant code before planning.

This phase activates when the user passes `--research` or the task touches code that needs investigation.

**Step 1: Identify scope**

Determine which files and patterns need reading to understand the change.

**Step 2: Read and analyze**

Read relevant source files, tests, and configuration. Build a mental model of:
- Current behavior
- Where the change fits
- What might break

**Step 3: Summarize findings**

Present a brief (3-5 line) summary of what you learned and how it affects the plan.

**GATE**: Sufficient understanding to plan the change. Proceed to Phase 1.

### Phase 1: PLAN

**Goal**: Create a lightweight inline plan.

**Step 1: Generate task ID**

Format: `YYMMDD-xxx` where xxx is Base36 sequential.

To determine the next sequence number:
```bash
# Check STATE.md for today's tasks to determine next sequence
date_prefix=$(date +%y%m%d)
```

If STATE.md exists in the repo root, find the highest sequence number for today's date prefix and increment. If no tasks today, start at `001`. Use Base36 (0-9, a-z) for the sequence: 001, 002, ... 009, 00a, 00b, ... 00z, 010, ...

**Step 2: Create inline plan**

Display the plan — do NOT write a task_plan.md file:

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

If estimated edits exceed 15, suggest upgrading:
```
This task estimates 15+ edits. Consider using /do for full planning
and agent routing. Proceed with /quick anyway? [Y/n]
```

**Step 3: Create feature branch** (unless --no-branch)

```bash
git checkout -b quick/<task-id>-<brief-kebab-description>
```

**GATE**: Task ID assigned, plan displayed, branch created. Proceed to Phase 2.

### Phase 2: EXECUTE

**Goal**: Implement the plan.

**Step 1: Make edits**

Execute the changes described in the plan. Track edit count.

**Step 2: Scope monitoring**

- At 10 edits: display a warning — "10 edits reached. Quick tasks typically stay under 15."
- At 15 edits: suggest upgrade — "15 edits reached. This may benefit from /do with full planning. Continue? [Y/n]"
- No hard cap — the user decides. Quick's scope is advisory, not enforced like Fast's 3-edit gate.

**Step 3: Verify changes** (base mode)

Run a quick sanity check:
```bash
# Check for syntax errors in edited files (language-appropriate)
# e.g., python3 -m py_compile file.py, go build ./..., tsc --noEmit
```

If `--full` flag is set, run the full quality gate instead (see Phase 2.5).

**GATE**: All planned edits complete. Sanity check passes.

### Phase 2.5: VERIFY (only with --full flag)

**Goal**: Run full quality gates on the changes.

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

**GATE**: Tests pass, lint clean, diff reviewed. Proceed to Phase 3.

### Phase 3: COMMIT

**Goal**: Commit with a clean message.

**Step 1: Stage changes**

```bash
git add <specific-files>
```

**Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
<type>: <description>

Quick task <task-id>
EOF
)"
```

Include the task ID in the commit body for traceability.

**GATE**: Commit succeeded. Verify with `git log -1 --oneline`.

### Phase 4: LOG

**Goal**: Record the task in STATE.md.

**Step 1: Update STATE.md**

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
   - Push: /pr-sync
   - More work: /quick <next task>
   - Merge to parent: git merge quick/<task-id>-...

===================================================================
```

---

## Examples

### Example 1: Base Mode
User says: `/quick add --verbose flag to the CLI`
1. Generate ID: 260322-001
2. Plan: add flag definition, wire to handler, update help text (3 edits)
3. Create branch: `quick/260322-001-add-verbose-flag`
4. Execute edits, commit, log to STATE.md

### Example 2: With Research
User says: `/quick --research fix the timeout bug in auth middleware`
1. RESEARCH: Read auth middleware, identify timeout source, trace call path
2. PLAN: change timeout value in config, update middleware to use it (2 edits)
3. EXECUTE, COMMIT, LOG

### Example 3: Escalated from Fast
`/fast` hit 3-edit limit while fixing a bug across 5 files.
1. Quick picks up with context: "Continuing from /fast — 3 files already edited"
2. PLAN: remaining 2 files to edit
3. EXECUTE remaining edits, COMMIT all changes, LOG as tier `fast->quick`

### Example 4: Full Rigor
User says: `/quick --full update payment amount rounding logic`
1. PLAN: identify rounding function, change to banker's rounding
2. EXECUTE the edit
3. VERIFY: run payment tests, lint, review diff
4. COMMIT, LOG

---

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

---

## Anti-Patterns

### Anti-Pattern 1: Skipping the Plan
**What it looks like**: Jumping straight to edits without displaying the inline plan
**Why wrong**: The plan catches misunderstandings before they become wrong edits. It takes 10 seconds and saves minutes.
**Do instead**: Always display the inline plan. Even for obvious tasks — it confirms alignment.

### Anti-Pattern 2: Using Quick for Features
**What it looks like**: Building a multi-component feature as a series of `/quick` tasks
**Why wrong**: Features need design docs, coordinated implementation, and integration testing. Quick tasks are isolated units.
**Do instead**: Use the feature lifecycle (`/feature-design` -> `/feature-plan` -> `/feature-implement`).

### Anti-Pattern 3: Never Using Flags
**What it looks like**: Always running base `/quick` even when research or verification is clearly needed
**Why wrong**: Base mode assumes you know exactly what to change. When you don't, you make wrong changes faster.
**Do instead**: Use `--research` when touching unfamiliar code, `--discuss` when requirements are unclear, `--full` when the change is high-risk.

### Anti-Pattern 4: Using Quick to Avoid Planning
**What it looks like**: Classifying a Simple+ task as "quick" to skip task_plan.md
**Why wrong**: The inline plan is not a substitute for full planning. Complex tasks need full plans.
**Do instead**: If the task genuinely needs a full plan, use `/do` and let the router classify properly.

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This is quick, no need for a plan" | Quick's inline plan IS the minimum — skipping it means no plan at all | Display the inline plan |
| "15 edits but it's all simple stuff" | Edit count is a scope signal, not a difficulty signal | Show the upgrade suggestion at 15 |
| "I'll add the task ID later" | Later never comes; untracked tasks are invisible | Assign ID in Phase 1 |
| "No need for a branch, it's small" | Small changes on main break the same as big ones | Create feature branch (or use --no-branch explicitly) |
| "Skip --research, I know this code" | Confidence != correctness; /fast exists for when you truly know | Use --research when touching unfamiliar code |
| "Don't need --full for this" | Risk is about impact, not size; a one-line auth change can be catastrophic | Use --full for any security/payment/data change |
