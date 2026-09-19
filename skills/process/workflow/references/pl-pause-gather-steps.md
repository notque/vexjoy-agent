# Pause-Work Gather Steps

Verbatim Phase 1 (GATHER) detail.

## Step 1: Read CLAUDE.md

Read and follow the repository CLAUDE.md before any other operations because it establishes conventions for the current project that may differ from defaults.

## Step 2: Identify project root

Find the git root directory:
```bash
git rev-parse --show-toplevel
```

All subsequent paths and file writes target this root, not the current working directory because writing to the project root ensures `/resume-work` can find the files reliably across different shell invocation contexts.

## Step 3: Collect git state

Uncommitted work is the highest-risk information to lose across sessions because a new shell or worktree cleanup can destroy changes the user intended to save. Run these commands to capture the current state:

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

## Step 4: Check for false completions

Search uncommitted/modified files for placeholder markers because they indicate work that looks done but is not — this is the most dangerous handoff failure mode. These markers are easily missed during context loss and become invisible in the next session.

```bash
# Get list of modified files
git diff --name-only
git diff --cached --name-only
```

Use the Grep tool to search those files for these patterns: `TODO`, `FIXME`, `PLACEHOLDER`, `TBD`, `XXX`, `HACK`, `stub`, `not yet implemented`.

Record any findings — these are items that look complete but are not.

## Step 5: Read task_plan.md if present

If `task_plan.md` exists in the project root, read it and incorporate its phase status into the handoff because the plan captures WHAT phases and tasks exist while the handoff captures WHY and the session's mental model. The handoff supplements the plan (capturing session reasoning), it does not replace it. Extract:
- Which phases are complete (marked `[x]`)
- Which phases remain (marked `[ ]`)
- Current status line
- Decisions and errors logged

## Step 6: Read .adr-session.json if present

If `.adr-session.json` exists, note the active ADR for context in the handoff because ADRs record architectural decisions that influence remaining work.
