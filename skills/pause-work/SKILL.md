---
name: pause-work
description: |
  Create session handoff artifacts (HANDOFF.json + .continue-here.md) that capture
  completed work, remaining tasks, decisions, uncommitted files, and reasoning context
  so the next session can resume without reconstruction overhead. Use for "pause",
  "save progress", "handoff", "stopping for now", "end session", "pick this up later".
  Do NOT use for task planning (use task_plan.md), session summaries (use /retro),
  or committing work (use /commit or git directly).
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - pause
    - save progress
    - handoff
    - stopping for now
    - end session
    - pick this up later
    - session handoff
    - wrap up session
  pairs_with:
    - resume-work
  complexity: Simple
  category: process
---

# /pause - Session Handoff

## Operator Context

This skill captures ephemeral session reasoning into durable artifacts so the next session can resume without wasting time on context reconstruction. It solves a specific gap: `task_plan.md` records WHAT tasks exist, but not WHY the current session chose a particular approach, what it rejected, or what it planned to do next.

The two output files serve different audiences:
- `HANDOFF.json` — machine-readable, consumed by `/resume` for automated state reconstruction
- `.continue-here.md` — human-readable, for users who want to understand session state without starting a new session

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Dual-Format Output**: Always produce BOTH `HANDOFF.json` and `.continue-here.md`. The machine format enables automated resume; the human format enables manual inspection. Skipping either breaks half the use case.
- **Uncommitted Work Detection**: Always run `git status` and `git diff --stat` to identify uncommitted changes. Uncommitted work is the highest-risk information to lose across sessions.
- **False Completion Detection**: Grep for placeholder markers (TODO, FIXME, PLACEHOLDER, TBD, XXX, HACK, stub, not yet implemented) in uncommitted files. These indicate work that looks done but is not — the most dangerous handoff failure mode.
- **Project Root Placement**: Write both files to the project root (where `.git/` lives), not the current working directory if different. This ensures `/resume` can find them reliably.
- **No Destructive Operations**: This skill only creates files. It never deletes, modifies existing code, or runs destructive git commands.

### Default Behaviors (ON unless disabled)
- **WIP Commit Suggestion**: If uncommitted changes exist, suggest a WIP commit before pausing. Uncommitted work can be lost if the worktree is cleaned up. Do not auto-commit — suggest and let the user decide.
- **task_plan.md Integration**: If `task_plan.md` exists, read it and incorporate its phase status into the handoff. The handoff supplements the plan, it does not replace it.
- **Timestamp in ISO 8601**: All timestamps use UTC ISO 8601 format for unambiguous parsing.

### Optional Behaviors (OFF unless enabled)
- **Auto-Commit Handoff** (`--commit`): Commit the handoff files on the current branch. Default is to leave them uncommitted so the user can review first.
- **Quiet Mode** (`--quiet`): Skip the confirmation summary. For automated/scripted usage.

## What This Skill CAN Do
- Capture completed tasks, remaining work, blockers, and decisions into structured handoff files
- Detect uncommitted work and suggest WIP commits
- Detect false completions (placeholder markers in modified files)
- Synthesize the session's reasoning context (approach chosen, alternatives rejected, mental model)
- Optionally commit handoff artifacts to the current branch

## What This Skill CANNOT Do
- Replace `task_plan.md` — handoffs capture session reasoning, plans capture task structure
- Auto-commit code changes — it only suggests WIP commits, never executes them without user consent
- Guarantee reasoning accuracy — handoff quality depends on the session's self-awareness (same limitation as any self-assessment)
- Resume from handoff files — that is the `resume-work` skill

---

## Instructions

### Phase 1: GATHER

**Goal**: Collect all state needed for the handoff.

**Step 1: Identify project root**

Find the git root directory:
```bash
git rev-parse --show-toplevel
```

All subsequent paths and file writes are relative to this root.

**Step 2: Collect git state**

Run these commands to capture the current state:

```bash
# Current branch
git branch --show-current

# Uncommitted files (staged and unstaged)
git status --short

# Summary of uncommitted changes
git diff --stat
git diff --cached --stat

# Recent commits on this branch (for context)
git log --oneline -10
```

**Step 3: Check for false completions**

Search uncommitted/modified files for placeholder markers:

```bash
# Get list of modified files
git diff --name-only
git diff --cached --name-only
```

Use the Grep tool to search those files for these patterns: `TODO`, `FIXME`, `PLACEHOLDER`, `TBD`, `XXX`, `HACK`, `stub`, `not yet implemented`.

Record any findings — these are items that look complete but are not.

**Step 4: Read task_plan.md if present**

If `task_plan.md` exists in the project root, read it to extract:
- Which phases are complete (marked `[x]`)
- Which phases remain (marked `[ ]`)
- Current status line
- Decisions and errors logged

**Step 5: Read .adr-session.json if present**

If `.adr-session.json` exists, note the active ADR for context in the handoff.

**GATE**: Git state collected. Modified file list available. Placeholder scan complete. Ready to synthesize.

### Phase 2: SYNTHESIZE

**Goal**: Combine gathered state with session reasoning into handoff content.

**Step 1: Construct completed_tasks**

List what was accomplished this session. Draw from:
- Git commits made during the session
- Phases marked complete in task_plan.md
- Work the session performed (files created, edited, reviewed)

Be specific: "Implemented scoring module in scripts/quality-score.py" not "Did some work on scoring."

**Step 2: Construct remaining_tasks**

List what still needs to be done. Draw from:
- Unchecked phases in task_plan.md
- Placeholder markers found in Phase 1 Step 3
- Known incomplete work from session context

**Step 3: Construct decisions**

Record key decisions made during the session and WHY. This is the highest-value handoff content because it prevents the next session from re-exploring dead ends.

Format: `{"decision description": "reasoning for the decision"}`

**Step 4: Construct next_action**

Write a specific, actionable description of what the next session should do first. Include:
- The exact action (not vague "continue working")
- Relevant file paths and function names
- Integration points or dependencies
- Why this is the right next step

**Step 5: Construct context_notes**

Capture the session's mental model — the reasoning context that is NOT captured in code or commits:
- Approaches tried and rejected (and why)
- Assumptions being made
- Gotchas discovered
- Performance or design trade-offs considered

**GATE**: All handoff fields populated with specific, actionable content. No vague entries like "continue work" or "finish implementation."

### Phase 3: WRITE

**Goal**: Write both handoff files to the project root.

**Step 1: Write HANDOFF.json**

Write to `{project_root}/HANDOFF.json`:

```json
{
  "created_at": "<ISO 8601 UTC timestamp>",
  "task_summary": "<Brief description of the overall task>",
  "completed_tasks": [
    "<Specific completed item 1>",
    "<Specific completed item 2>"
  ],
  "remaining_tasks": [
    "<Specific remaining item 1>",
    "<Specific remaining item 2>"
  ],
  "blockers": [
    "<Blocker if any, or empty array>"
  ],
  "decisions": {
    "<Decision 1>": "<Reasoning>",
    "<Decision 2>": "<Reasoning>"
  },
  "uncommitted_files": [
    "<file1>",
    "<file2>"
  ],
  "next_action": "<Specific next action with file paths and integration points>",
  "context_notes": "<Mental model, rejected approaches, gotchas, assumptions>",
  "branch": "<current branch name>",
  "base_branch": "main",
  "false_completions": [
    "<file:line — placeholder marker found, if any>"
  ]
}
```

**Step 2: Write .continue-here.md**

Write to `{project_root}/.continue-here.md`:

```markdown
# Continue Here

## What I was doing
[Prose description of the task, current state, and approach being taken]

## What's done
- [Completed item 1]
- [Completed item 2]

## What's next
[Specific next action — what to do, which files, why this step]

## Key decisions
- [Decision 1]: [Why]
- [Decision 2]: [Why]

## Watch out for
- [Blockers, gotchas, dead ends already explored]
- [False completions found: file:line — marker]

## Uncommitted work
- [file1 — brief description of changes]
- [file2 — brief description of changes]
```

**Step 3: Suggest WIP commit if needed**

If there are uncommitted changes (from Phase 1 Step 2), display:

```
WARNING: Uncommitted changes detected in N file(s):
  - file1
  - file2

Consider a WIP commit before ending the session:
  git add <files> && git commit -m "wip: <description>"

Uncommitted work can be lost if the worktree is cleaned up.
```

Do NOT auto-commit. The user decides.

**Step 4: Optional commit of handoff files**

If `--commit` flag was provided:
```bash
git add HANDOFF.json .continue-here.md
git commit -m "chore: session handoff artifacts"
```

**GATE**: Both files written to project root. User notified of uncommitted work if any.

### Phase 4: CONFIRM

**Goal**: Display summary and confirm handoff was captured.

Display the handoff summary:

```
===================================================================
 SESSION PAUSED
===================================================================

 Handoff files created:
   - HANDOFF.json (machine-readable)
   - .continue-here.md (human-readable)

 Completed: N task(s)
 Remaining: N task(s)
 Blockers: N
 Uncommitted files: N
 False completions: N placeholder(s) found

 Next action: <brief next_action summary>

 Resume with: /resume
===================================================================
```

---

## Error Handling

### Error: Not in a Git Repository
**Cause**: `git rev-parse --show-toplevel` fails — no `.git/` directory found
**Solution**: Handoff files require git context for branch and uncommitted file detection. Navigate to a git repository root and retry.

### Error: Cannot Determine Session Work
**Cause**: No commits on current branch, no task_plan.md, no uncommitted changes — nothing to hand off
**Solution**: If the session genuinely did no work, there is nothing to hand off. Inform the user: "No work detected to hand off. If you made changes that aren't committed or tracked, describe what you were working on and I'll create the handoff manually."

### Error: HANDOFF.json Already Exists
**Cause**: A previous `/pause` created handoff files that were never consumed by `/resume`
**Solution**: Warn the user that stale handoff files exist. Offer to overwrite (default) or append. Overwriting is almost always correct — stale handoffs from abandoned sessions should not block new ones.

---

## Anti-Patterns

### Anti-Pattern 1: Vague Next Actions
**What it looks like**: `"next_action": "Continue working on the feature"`
**Why wrong**: The entire point of handoff is to avoid reconstruction. Vague next actions force the next session to re-discover what "continue working" means.
**Do instead**: Be specific: `"next_action": "Wire quality-score.py into pr-pipeline Phase 3. The function signature is score_package(path) -> ScoreResult. Integration point is the gate check between STAGE and REVIEW phases."`

### Anti-Pattern 2: Skipping context_notes
**What it looks like**: `"context_notes": ""` or omitting the field
**Why wrong**: Context notes capture WHY the session chose its approach — the information most likely to be lost and most expensive to reconstruct.
**Do instead**: Always include at least: what approach was chosen, what was rejected, and any gotchas discovered.

### Anti-Pattern 3: Using Handoff as Task Plan
**What it looks like**: Creating detailed phase breakdowns in HANDOFF.json instead of task_plan.md
**Why wrong**: Handoff files are one-shot artifacts deleted after resume. Task plans persist as the task record of truth. Putting plan content in handoff means it vanishes after the next `/resume`.
**Do instead**: Keep task_plan.md for task structure. Use handoff for session-specific reasoning that supplements the plan.

### Anti-Pattern 4: Auto-Committing Code Changes
**What it looks like**: Committing uncommitted work as part of the pause flow without user consent
**Why wrong**: Uncommitted changes may be experimental, broken, or intentionally staged for review. Auto-committing removes the user's ability to decide.
**Do instead**: Suggest a WIP commit. Show the files. Let the user decide.

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The task plan captures everything" | task_plan.md captures task state, not session reasoning (approach, rejections, mental model) | Create handoff files with context_notes |
| "Next session can figure it out from git log" | Git log shows WHAT changed, not WHY or what was rejected | Include decisions and context_notes |
| "No need for .continue-here.md, JSON is enough" | Humans read prose faster than JSON; .continue-here.md is for manual inspection | Always write both files |
| "The changes are obvious, no need for detailed next_action" | What's obvious now is opaque after context loss | Write specific next_action with file paths |
| "I'll just quickly commit the code too" | Auto-committing code without user consent risks committing broken/experimental work | Suggest WIP commit, never auto-commit code |

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Related Skills
- `resume-work` — Consumes handoff artifacts to restore session state
- `workflow-orchestrator` — For complex multi-phase tasks that benefit from handoff between phases
