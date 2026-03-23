---
name: resume-work
description: |
  Restore session state from handoff artifacts and route to the next action.
  Priority cascade: HANDOFF.json (highest) > .continue-here.md > incomplete
  task_plan.md > git log. Presents a status dashboard, then executes the next
  action. Use for "resume", "continue", "pick up where I left off", "what was
  I doing", "continue work". Do NOT use for starting new tasks (use /do),
  reviewing past sessions (use /retro), or reading task plans (read task_plan.md
  directly).
version: 1.0.0
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Skill
routing:
  triggers:
    - resume
    - continue
    - pick up where I left off
    - what was I doing
    - continue work
    - where did I leave off
    - what's next
  pairs_with:
    - pause-work
  complexity: Simple
  category: process
---

# /resume - Session State Restoration

## Operator Context

This skill reconstructs session state from handoff artifacts so work can continue without wasting time re-reading files and re-discovering decisions. It is the consumer half of the pause/resume pair — `/pause` creates the artifacts, `/resume` consumes them.

The priority cascade exists because handoff quality varies:
1. **HANDOFF.json** — Best case. Machine-readable, structured, created by explicit `/pause`. Contains reasoning context.
2. **.continue-here.md** — Good case. Human-readable prose. May exist without JSON if user wrote it manually.
3. **task_plan.md** — Fallback. Records task structure but not session reasoning. Better than nothing.
4. **git log + git status** — Last resort. Can infer recent activity but cannot reconstruct reasoning or rejected approaches.

Each level down the cascade loses more context, so the skill always starts from the top.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Priority Cascade**: Always check sources in order: HANDOFF.json > .continue-here.md > task_plan.md > git log. Never skip to a lower source if a higher one exists, because higher sources contain richer context that would be lost.
- **Stale Handoff Warning**: If HANDOFF.json exists and `created_at` is older than 24 hours, warn the user before proceeding. Stale handoffs may describe work that has been superseded by manual changes.
- **One-Shot Consumption**: Delete HANDOFF.json and .continue-here.md after successful state reconstruction and user confirmation. These are ephemeral session artifacts, not persistent state. Keeping them risks future `/resume` calls loading outdated context.
- **Status Dashboard**: Always present a status summary before taking action. The user needs to confirm the reconstructed state matches reality before the session proceeds — self-assessment of "what I was doing" is inherently fallible.
- **No Destructive Operations**: This skill reads and deletes handoff files. It never modifies code, resets git state, or discards uncommitted changes.

### Default Behaviors (ON unless disabled)
- **Quick Resume Mode**: If the user says just "continue" or "resume" with no qualifiers, skip the options menu and immediately execute the `next_action` from the handoff. This optimizes for the common case where the user trusts the handoff and wants to get back to work fast.
- **Uncommitted Work Alert**: If handoff reports uncommitted files, verify they still exist and alert if any have been lost (worktree cleanup, manual revert).
- **Route via /do**: When executing `next_action`, route through the `/do` system if the action matches a known skill trigger. This ensures proper agent/skill selection for the resumed work.

### Optional Behaviors (OFF unless enabled)
- **Dry Run** (`--dry-run`): Show reconstructed state and planned next action without executing. For reviewing what `/resume` would do.
- **Keep Handoff** (`--keep`): Do not delete handoff files after consumption. For debugging or when the user wants to re-resume.

## What This Skill CAN Do
- Read and parse HANDOFF.json for structured state reconstruction
- Read .continue-here.md for prose-based state reconstruction
- Fall back to task_plan.md and git log when no handoff files exist
- Present a status dashboard with completed work, remaining tasks, and next action
- Route to the next action via /do or direct execution
- Delete consumed handoff files to prevent stale state

## What This Skill CANNOT Do
- Create handoff artifacts — that is the `pause-work` skill
- Recover uncommitted changes that were lost — it can detect the loss but cannot undo it
- Guarantee state accuracy — reconstructed state is only as good as the handoff that created it
- Replace task_plan.md — the plan is the persistent record; handoff is the ephemeral session context

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Find the best available state source using the priority cascade.

**Step 1: Identify project root**

```bash
git rev-parse --show-toplevel
```

**Step 2: Check for HANDOFF.json (Priority 1)**

Look for `{project_root}/HANDOFF.json`. If found:
- Read and parse the JSON
- Check `created_at` timestamp — if older than 24 hours, set `stale_warning = true`
- This is the richest source: proceed to Phase 2 with full structured data
- Also read `.continue-here.md` if it exists (for supplementary prose context)

**Step 3: Check for .continue-here.md (Priority 2)**

If no HANDOFF.json but `.continue-here.md` exists:
- Read the prose content
- Extract what you can: task description, completed items, next action, decisions
- Note that reasoning context may be limited compared to JSON handoff

**Step 4: Check for task_plan.md (Priority 3)**

If neither handoff file exists but `task_plan.md` exists:
- Read the plan
- Extract: completed phases `[x]`, remaining phases `[ ]`, decisions, errors, current status
- Note: this source captures task structure but not session reasoning

**Step 5: Fall back to git reconstruction (Priority 4)**

If no handoff files and no task_plan.md:

```bash
# Recent activity
git log --oneline -20

# Current branch context
git branch --show-current

# Uncommitted work
git status --short

# What's changed
git diff --stat
```

Synthesize a best-effort summary from git state. This is the least precise reconstruction — it shows WHAT happened but not WHY.

**Step 6: Set reconstruction quality indicator**

| Source | Quality | Missing |
|--------|---------|---------|
| HANDOFF.json | Full | Nothing — richest source |
| .continue-here.md | Good | Structured data, may lack reasoning detail |
| task_plan.md | Partial | Session reasoning, rejected approaches, mental model |
| git log | Minimal | All reasoning context, decisions rationale, next action specifics |

**GATE**: At least one state source found and read. If ALL sources are empty (no handoff, no plan, no git history), inform user: "No session state found. Use /do to start a new task."

### Phase 2: RECONSTRUCT

**Goal**: Build a coherent state picture from available sources.

**Step 1: Verify uncommitted files**

If the handoff reports `uncommitted_files`, check whether they still exist:

```bash
# For each file in uncommitted_files list
git status --short -- <file>
```

Flag any files that were listed as uncommitted but are now missing — these represent potential work loss.

**Step 2: Check for false completions**

If the handoff reports `false_completions`, verify those placeholder markers still exist in the codebase. They may have been fixed by manual intervention between sessions.

**Step 3: Synthesize status dashboard**

Build the dashboard from available data:

```
===================================================================
 SESSION RESUMED
===================================================================

 Source: HANDOFF.json (created: <timestamp>) [STALE WARNING if applicable]
 Branch: <branch> (base: <base_branch>)

 Task: <task_summary>

 Completed:
   - <completed item 1>
   - <completed item 2>

 Remaining:
   - <remaining item 1>
   - <remaining item 2>

 Blockers: <blockers or "None">

 Key Decisions:
   - <decision>: <reasoning>

 Uncommitted Work: <N file(s)> [WARNING: N file(s) missing if applicable]

 False Completions: <N placeholder(s)> [or "None detected"]

 Next Action:
   <next_action description>

===================================================================
```

**GATE**: Status dashboard constructed. Ready to present to user.

### Phase 3: PRESENT

**Goal**: Show the user what was reconstructed and confirm before proceeding.

**Step 1: Display status dashboard**

Show the dashboard from Phase 2.

**Step 2: Handle stale handoff warning**

If `stale_warning` is true:
```
WARNING: Handoff is from <timestamp> (>24 hours ago).
State may not reflect manual changes made since then.
Proceed with this handoff or discard it? [proceed/discard]
```

If user discards, fall to next priority level in cascade.

**Step 3: Determine action mode**

- **Quick resume** (user said "continue", "resume", or similar with no qualifiers): Skip options, proceed directly to Phase 4 to execute `next_action`
- **Review mode** (user said "what was I doing", "where did I leave off", or asked a question): Display dashboard only, wait for user to choose what to do next

**GATE**: User has seen the dashboard. In quick resume mode, proceed to Phase 4. In review mode, wait for user direction.

### Phase 4: EXECUTE

**Goal**: Route to the next action and clean up handoff files.

**Step 1: Execute next action**

Take the `next_action` from the handoff and execute it:
- If it matches a skill trigger (e.g., "run tests" -> /vitest-runner), invoke that skill
- If it describes a code change, proceed with the implementation directly
- If it requires user input (e.g., "need clarification on threshold"), present the question

Carry forward all context from the handoff: decisions made, approaches rejected, gotchas to avoid. This context should inform the execution, not just the dashboard.

**Step 2: Clean up handoff files**

After the next action has been initiated (not necessarily completed — just successfully started):

```bash
# Remove one-shot handoff artifacts
rm -f HANDOFF.json .continue-here.md
```

If `--keep` flag was provided, skip deletion.

**Step 3: Update task_plan.md if present**

If `task_plan.md` exists, update its status line to reflect that the session has resumed:
```
**Status**: Resumed from handoff — executing: <next_action summary>
```

**GATE**: Next action initiated. Handoff files cleaned up. Session is now in active work mode.

---

## Error Handling

### Error: No State Sources Found
**Cause**: No HANDOFF.json, no .continue-here.md, no task_plan.md, and git log is empty or on a fresh branch
**Solution**: Inform user: "No session state found to resume from. Use /do to start a new task, or describe what you were working on and I'll reconstruct manually."

### Error: HANDOFF.json Parse Failure
**Cause**: HANDOFF.json exists but contains invalid JSON (corrupted, partially written, manually edited badly)
**Solution**: Warn user about the parse error. Fall through to .continue-here.md if it exists, otherwise fall to task_plan.md. Do not silently ignore the error — the user should know their handoff was corrupted.

### Error: Uncommitted Files Missing
**Cause**: Handoff reports uncommitted files that no longer exist (worktree cleanup, manual deletion, git checkout)
**Solution**: Alert the user with specific file names. These changes are likely lost. The user may need to recreate them — the handoff's `context_notes` and `decisions` can help guide reconstruction.

### Error: Stale Handoff Rejected
**Cause**: User chose to discard a stale (>24h) handoff
**Solution**: Delete the stale handoff files and fall through to the next priority level in the cascade (task_plan.md or git log). Proceed with the lower-quality reconstruction.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping the Dashboard
**What it looks like**: Reading HANDOFF.json and immediately executing next_action without showing the user what was reconstructed
**Why wrong**: Self-assessment of session state is inherently fallible. The user needs to confirm the reconstruction matches reality before the session acts on potentially stale or incorrect assumptions.
**Do instead**: Always show the dashboard. In quick resume mode, show it briefly then proceed — but never skip it entirely.

### Anti-Pattern 2: Keeping Handoff Files Forever
**What it looks like**: Never deleting HANDOFF.json after consumption, or using `--keep` by default
**Why wrong**: Stale handoff files cause future `/resume` calls to load outdated context, potentially overriding the user's actual current state with a previous session's snapshot.
**Do instead**: Delete after successful reconstruction. Use `--keep` only for debugging.

### Anti-Pattern 3: Ignoring Lower-Priority Sources
**What it looks like**: Finding HANDOFF.json and not checking task_plan.md at all
**Why wrong**: task_plan.md may have been updated manually between sessions. It provides the task structure that supplements the handoff's session reasoning.
**Do instead**: Use HANDOFF.json as primary source but also read task_plan.md if it exists for supplementary context.

### Anti-Pattern 4: Re-Exploring Rejected Approaches
**What it looks like**: The handoff says "tried X, rejected because Y" but the new session tries X again
**Why wrong**: This is the exact waste handoff was designed to prevent. Re-exploring dead ends burns context on work already done.
**Do instead**: Read `decisions` and `context_notes` carefully. Honor previous session's findings unless circumstances have changed.

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I'll just start fresh, it's faster" | Reconstruction from handoff takes seconds; re-discovery takes minutes to hours | Check handoff files first |
| "The handoff is stale, I'll ignore it" | Stale handoff still contains decisions and rejected approaches worth knowing | Read it, warn about staleness, let user decide |
| "I know what to do, don't need the dashboard" | You're a new session — you know nothing yet. The dashboard IS your knowledge. | Always display the dashboard |
| "I'll keep the handoff files just in case" | Stale files cause worse problems than missing files | Delete after successful consumption |
| "The git log tells me everything" | Git log shows WHAT changed but not WHY, what was rejected, or what's next | Use handoff files when available; git log is last resort |

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Related Skills
- `pause-work` — Creates the handoff artifacts this skill consumes
- `do` — Routes next_action to appropriate agent/skill for execution
- `workflow-orchestrator` — For complex multi-phase tasks that benefit from handoff between phases
