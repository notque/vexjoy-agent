---
name: fast
description: |
  Zero-ceremony inline execution for tasks completable in 3 or fewer file
  edits. No plan, no subagent, no research — just understand, do, commit, log.
  Use for "quick fix", "typo fix", "one-line change", "trivial fix", "rename
  this variable", "update this value", "fix this import". Do NOT use for tasks
  requiring research, planning, new dependencies, or more than 3 file edits —
  redirect to /quick instead.
version: 1.0.0
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
routing:
  triggers:
    - quick fix
    - typo fix
    - one-line change
    - trivial fix
    - rename variable
    - update value
    - fix import
  pairs_with: []
  complexity: Simple
  category: process
---

# /fast - Zero-Ceremony Execution

## Operator Context

This skill implements the Fast tier from the five-tier task hierarchy (Fast > Quick > Simple > Medium > Complex). It exists because the full ceremony of plan files, agent routing, and quality gates is wasteful for a typo fix. The process should scale down to match the task.

### Hardcoded Behaviors (Always Apply)
- **3-Edit Scope Limit**: If the task requires more than 3 file edits, STOP and redirect to `/quick`. The work done so far is preserved — do not restart. This gate exists because uncapped "fast" tasks silently grow into untracked large changes.
- **No Plan File**: Do not create `task_plan.md`. The overhead of planning exceeds the task itself at this tier.
- **No Subagent Spawning**: Execute inline. Subagents add latency and context setup cost that dwarfs the actual work.
- **No Research Phase**: If the task requires reading documentation, investigating behavior, or understanding unfamiliar code, it is not a Fast task. Redirect to `/quick --research`.
- **No New Dependencies**: If the task requires adding imports from new packages, installing libraries, or modifying dependency files (go.mod, package.json, requirements.txt), redirect to `/quick`.
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution.
- **Branch Safety**: Create a feature branch if currently on main/master. Even fast tasks get proper branches.
- **Commit After Edit**: Every fast task ends with a commit. Uncommitted fast edits defeat the auditability that justifies using the system at all.

### Default Behaviors (ON unless disabled)
- **STATE.md Logging**: Append completed task to STATE.md quick tasks table (create if absent)
- **Conventional Commits**: Use conventional commit format for the commit message
- **Edit Counting**: Track edits during execution to enforce the 3-edit scope gate

### Optional Behaviors (OFF unless enabled)
- **No Commit Mode** (`--no-commit`): Skip the commit step (for when the user wants to batch changes)
- **Dry Run** (`--dry-run`): Show what would change without editing

## What This Skill CAN Do
- Fix typos, rename variables, update config values, fix imports
- Make 1-3 targeted file edits and commit them
- Log the action to STATE.md for auditability

## What This Skill CANNOT Do
- Research unfamiliar code or APIs (redirect to `/quick --research`)
- Add new dependencies (redirect to `/quick`)
- Edit more than 3 files (redirect to `/quick`)
- Run quality gates or parallel reviews (those belong to Simple+ tiers)
- Create plans or spawn subagents

---

## Instructions

### Phase 1: UNDERSTAND

**Goal**: Confirm the task is Fast-eligible and know exactly what to change.

**Step 1: Read the request**

Parse the user's request to identify:
- Which file(s) need editing
- What specific change is needed
- Whether this is clearly a 1-3 edit task

**Step 2: Scope check**

Ask these questions silently (do not display to user):
- Does this need research or investigation? If yes -> redirect to `/quick --research`
- Does this touch more than 3 files? If yes -> redirect to `/quick`
- Does this add new dependencies? If yes -> redirect to `/quick`
- Is the change ambiguous or underspecified? If yes -> ask user for clarification

If redirecting, say:
```
This task exceeds /fast scope ([reason]). Redirecting to /quick.
```
Then invoke the quick skill with the original request.

**Step 3: Locate target files**

Read the file(s) that need editing. Confirm the exact lines to change.

**GATE**: Task is confirmed Fast-eligible (1-3 edits, no research, no new deps). Target files identified and read.

### Phase 2: DO

**Goal**: Make the edits.

**Step 1: Execute edits**

Make the changes using Edit tool. Track the number of files edited.

**Step 2: Mid-execution scope check**

After each edit, check: have we hit 3 edits? If the task needs MORE edits to complete:

```
Scope exceeded during execution (3+ edits needed). Preserving work done.
Redirecting remainder to /quick.
```

Hand off to `/quick` with context about what was already done.

**GATE**: All edits complete. Edit count is 1-3.

### Phase 3: COMMIT

**Goal**: Commit the changes with a clean message.

**Step 1: Check branch**

If on main/master, create a feature branch first:
```bash
git checkout -b fast/<brief-description>
```

**Step 2: Stage and commit**

```bash
git add <specific-files>
git commit -m "$(cat <<'EOF'
<type>: <description>
EOF
)"
```

Use conventional commit format. The type is usually `fix:`, `chore:`, or `refactor:` for fast tasks.

**GATE**: Commit succeeded. Verify with `git log -1 --oneline`.

### Phase 4: LOG

**Goal**: Record the task for auditability.

**Step 1: Append to STATE.md**

If STATE.md exists in the repo root, append to the quick tasks table. If it does not exist, create it.

Format:
```markdown
## Quick Tasks

| Date | ID | Description | Commit | Tier |
|------|----|-------------|--------|------|
| YYYY-MM-DD | - | <description> | <short-hash> | fast |
```

Fast tasks do not get task IDs (that is a Quick-tier feature). Use `-` for the ID column.

**Step 2: Display summary**

```
===================================================================
 FAST: <description>
===================================================================

 Files edited: <N>
 Commit: <hash> on <branch>
 Logged: STATE.md

===================================================================
```

---

## Error Handling

### Error: Scope Exceeded Mid-Execution
**Cause**: Task turned out to need more than 3 edits
**Solution**: Stop, preserve work, redirect to `/quick` with context about completed edits. Do not undo work already done.

### Error: Ambiguous Request
**Cause**: Cannot determine exact files or changes from the request
**Solution**: Ask user one clarifying question. If still ambiguous after one round, redirect to `/quick --discuss`.

### Error: On Main Branch
**Cause**: Currently on main/master
**Solution**: Create `fast/<description>` branch before editing. Never commit directly to main.

---

## Anti-Patterns

### Anti-Pattern 1: Using Fast for Investigation
**What it looks like**: Reading 5 files to understand a bug before fixing it
**Why wrong**: Investigation is research. Fast is for when you already know what to change.
**Do instead**: Use `/quick --research` for tasks that need understanding first.

### Anti-Pattern 2: Skipping the Commit
**What it looks like**: Making fast edits but not committing because "it's just a small change"
**Why wrong**: Uncommitted changes are invisible to the audit trail. The whole point of /fast over raw editing is traceability.
**Do instead**: Always commit. Use `--no-commit` only when explicitly batching.

### Anti-Pattern 3: Stretching Scope
**What it looks like**: "While I'm here, let me also fix this other thing" — turning 2 edits into 6
**Why wrong**: Scope creep in fast mode produces untracked large changes with no plan or review
**Do instead**: Stop at 3 edits. Open a new `/fast` or `/quick` for additional work.

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Just one more edit won't hurt" | The 3-edit gate exists to prevent silent scope creep | Redirect to /quick at edit 4 |
| "This is basically fast, just needs a little research" | Research means uncertainty; uncertainty means /quick | Redirect to /quick --research |
| "No need to commit a one-line change" | One-line changes cause one-line bugs that are invisible without commits | Commit every fast task |
| "STATE.md logging is overhead" | Without logging, fast tasks are invisible — defeating auditability | Always log to STATE.md |
