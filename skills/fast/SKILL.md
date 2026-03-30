---
name: fast
description: "Zero-ceremony inline execution for 3 or fewer file edits."
effort: low
version: 1.0.0
user-invocable: false
argument-hint: "<fix description>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Skill
routing:
  force_route: true
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

The Fast tier sits at the bottom of the five-tier task hierarchy (Fast > Quick > Simple > Medium > Complex). It exists because the full ceremony of plan files, agent routing, and quality gates is wasteful for a typo fix. Execute inline without plans or subagents, commit the result, and log it.

---

## Instructions

### Phase 1: UNDERSTAND

**Goal**: Confirm the task is Fast-eligible and know exactly what to change.

**Step 1: Read CLAUDE.md**

Read and follow the repository CLAUDE.md before any other action, because repository-specific constraints may affect how the edit should be made.

**Step 2: Parse the request**

Identify from the user's request:
- Which file(s) need editing
- What specific change is needed
- Whether this is clearly a 1-3 edit task

If `--dry-run` was passed, show what would change without editing and stop.

**Step 3: Scope check**

Ask these questions silently (do not display to user):

| Question | If Yes |
|----------|--------|
| Does this need reading docs, investigating behavior, or understanding unfamiliar code? | Redirect to `/quick --research` because investigation means uncertainty, and uncertainty means this is not a Fast task |
| Does this touch more than 3 files? | Redirect to `/quick` because uncapped "fast" tasks silently grow into untracked large changes |
| Does this add imports from new packages, install libraries, or modify dependency files (go.mod, package.json, requirements.txt)? | Redirect to `/quick` because new dependencies carry risk that needs proper tracking |
| Is the change ambiguous or underspecified? | Ask user one clarifying question. If still ambiguous after one round, redirect to `/quick --discuss` |

If redirecting, say:
```
This task exceeds /fast scope ([reason]). Redirecting to /quick.
```
Then invoke the quick skill with the original request.

**Step 4: Locate target files**

Read the file(s) that need editing. Confirm the exact lines to change.

**GATE**: Task is confirmed Fast-eligible (1-3 edits, no research, no new deps). Target files identified and read.

### Phase 2: DO

**Goal**: Make the edits inline without spawning subagents, because subagents add latency and context setup cost that dwarfs the actual work at this tier.

Do not create `task_plan.md`, because the overhead of planning exceeds the task itself for a 1-3 edit change.

**Step 1: Execute edits**

Make the changes using the Edit tool. Track the number of files edited after each operation, because the 3-edit scope gate depends on an accurate count.

**Step 2: Mid-execution scope check**

After each edit, check: have we hit 3 edits? If the task needs MORE edits to complete, stop immediately — do not rationalize "just one more edit" because the 3-edit gate exists specifically to prevent silent scope creep:

```
Scope exceeded during execution (3+ edits needed). Preserving work done.
Redirecting remainder to /quick.
```

Hand off to `/quick` with context about what was already done. Do not start additional "while I'm here" fixes, because scope creep in fast mode produces untracked large changes with no plan or review.

**GATE**: All edits complete. Edit count is 1-3.

### Phase 3: COMMIT

**Goal**: Commit the changes with a clean message, because uncommitted fast edits are invisible to the audit trail and defeat the traceability that justifies using the system at all. Even one-line changes get commits because one-line changes cause one-line bugs that are invisible without commit history.

If `--no-commit` was passed, skip this phase (for when the user wants to batch changes).

**Step 1: Check branch**

If on main/master, create a feature branch first because even fast tasks get proper branches — never commit directly to main:
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

**Goal**: Record the task for auditability, because without logging fast tasks are invisible and the system loses its audit trail.

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
