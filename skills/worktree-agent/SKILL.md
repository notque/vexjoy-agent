---
name: worktree-agent
description: "Mandatory rules for agents in git worktree isolation."
version: 1.0.0
user-invocable: false
context: fork
tags: [worktree, isolation, parallel, agent]
---

# Worktree Agent Rules

Mandatory rules for any agent dispatched with `isolation: "worktree"`.

## Rule 1: Verify Your Working Directory

On start, run `pwd`. Your path MUST contain `.claude/worktrees/`.
If your CWD is the main repo path, **STOP** and report the error.

## Rule 2: Create Feature Branch First

```bash
git checkout -b <branch-name>
```

Never commit on the default `worktree-agent-*` branch. Create your feature branch FIRST.

## Rule 3: Use Worktree-Relative Paths

Never hardcode absolute paths from the main repo. Use `$(git rev-parse --show-toplevel)/path`.
**Exception**: Reading gitignored ADR files requires the main repo absolute path.

## Rule 4: Ignore Auto-Plan Hooks

Do NOT create or modify `task_plan.md`. If auto-plan hook fires, ignore it.
Focus exclusively on your implementation tasks.

## Rule 5: Stage Specific Files Only

```bash
git add path/to/specific/file.py
```

Never `git add .`, `git add -A`, or `git add --all`. Verify with `git diff --cached --stat`.

## Rule 6: Do Not Touch the Main Worktree

Never write to paths outside your worktree directory. Never run `git checkout` in the main repo.

## Rule 7: Commit with Conventional Format

Use the commit message specified in your prompt. No attribution lines.

## Failure Modes This Prevents

| Failure | Rule | Without It |
|---------|------|-----------|
| Agent edits main repo files | 1, 6 | Changes leak to main, get stashed/lost |
| Context wasted on task_plan.md | 4 | Implementation budget consumed by planning |
| Commit on wrong branch | 2 | Orchestrator merges wrong content |
| PR has changes from 2 ADRs | 5, 6 | Cross-contamination between agents |
| Branch locked by worktree | 2 | Fatal error on checkout |
