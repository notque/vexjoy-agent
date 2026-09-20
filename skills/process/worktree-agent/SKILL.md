---
name: worktree-agent
promoted_to: do
description: "Local isolation, capacity, branch, staging, and cleanup contracts for dispatched git worktrees."
user-invocable: false
context: fork
tags: [worktree, isolation, parallel, agent]
routing:
  triggers: ["worktree agent", "git worktree", "git worktree rules", "isolated agent"]
  category: git-workflow
---

# Worktree agent contracts

These rules apply to `isolation: "worktree"` dispatches.

## Before work

1. Run `pwd`; the checkout must be under `.claude/worktrees/`. Otherwise stop.
2. Run `bash scripts/worktree-preflight.sh <intended-branch-name>` and resolve a
   nonzero result before editing.
3. Create a feature branch before the first commit. Never use the generated
   `worktree-agent-*` branch. If a name is live in another checkout, choose a
   unique suffix; do not delete or steal the live branch.
4. Use worktree-relative paths rooted at `git rev-parse --show-toplevel` and
   never write into the main checkout. The sole exception is read-only access
   to a gitignored ADR explicitly supplied from the main checkout.

Ignore auto-plan hooks inside isolated workers; keep the assigned plan inline.

## Capacity and roles

Before creating an implementation checkout, the dispatcher runs:

```bash
python3 ~/.claude/skills/process/worktree-agent/scripts/worktree_capacity.py \
  --repo "$(git rev-parse --show-toplevel)" --strict
```

- `ready` (<80%): one writable implementation checkout may be created.
- `cleanup-soon` (80–<85%): reclaim accepted, clean, inactive checkouts first.
- `blocked` (≥85%): create no checkout; integrate, verify, deploy, or reclaim.

Cleanliness does not prove inactivity. Review and investigation read the
candidate from the root with `git diff`/`git show`; they receive no checkout.
Reuse one writable checkout through review fixes. Prefer sparse checkout for a
large repository and record why a full checkout was required.

## Delivery

- Stage explicit paths only; never `git add .`, `-A`, or `--all`.
- Verify `git diff --cached --stat` before committing.
- Use the requested conventional commit message without attribution lines.
- For Python changes run both `ruff check . --config pyproject.toml` and
  `ruff format --check . --config pyproject.toml` before claiming CI-ready.
- To update a branch held elsewhere, work detached from `origin/<branch>` and
  push `HEAD:<branch>`.

After merge, and only after confirming the task inactive and checkout clean:

```bash
git worktree remove -- <accepted-worktree-path>
bash scripts/worktree-cleanup.sh --force
```

Removal frees the checkout but preserves its branch for recovery.
