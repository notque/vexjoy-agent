---
name: worktree-agent
description: "Mandatory rules for agents in git worktree isolation."
user-invocable: false
context: fork
tags: [worktree, isolation, parallel, agent]
routing:
  triggers:
    - "worktree agent"
    - "git worktree"
    - "git worktree rules"
    - "isolated agent"
  category: git-workflow
---

# Worktree Agent Rules

Mandatory rules for any agent dispatched with `isolation: "worktree"`.

## Rule 1: Verify Working Directory

On start, run `pwd`. Path MUST contain `.claude/worktrees/`.
If CWD is the main repo path, **STOP** and report the error.

## Rule 2: Create Feature Branch First

```bash
git checkout -b <branch-name>
```

Never commit on the default `worktree-agent-*` branch. Create feature branch FIRST.

## Rule 3: Use Worktree-Relative Paths

Never hardcode main repo absolute paths. Use `$(git rev-parse --show-toplevel)/path`.
**Exception**: Reading gitignored ADR files requires the main repo absolute path.

## Rule 4: Ignore Auto-Plan Hooks

Keep planning inline. If auto-plan hook fires, continue with current task.

## Rule 5: Stage Specific Files Only

```bash
git add path/to/specific/file.py
```

Never `git add .`, `git add -A`, or `git add --all`. Verify with `git diff --cached --stat`.

## Rule 6: Do Not Touch the Main Worktree

Never write outside your worktree directory. Never `git checkout` in the main repo.

## Rule 7: Commit with Conventional Format

Use the commit message from your prompt. No attribution lines.

## Rule 8: Run Both ruff Checks Before CI-Ready

For Python changes, run both before pushing:

```bash
ruff check . --config pyproject.toml
ruff format --check . --config pyproject.toml
```

Running only `ruff check` misses formatting violations. CI runs both — skipping `ruff format --check` fails the PR.

## Failure Modes This Prevents

| Failure | Rule | Without It |
|---------|------|-----------|
| Agent edits main repo files | 1, 6 | Changes leak to main |
| Context wasted on task_plan.md | 4 | Implementation budget consumed by planning |
| Commit on wrong branch | 2 | Orchestrator merges wrong content |
| PR has changes from 2 ADRs | 5, 6 | Cross-contamination between agents |
| Branch locked by worktree | 2 | Fatal error on checkout |
| PR fails CI on format | 8 | Merge blocked |
