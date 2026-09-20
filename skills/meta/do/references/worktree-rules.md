# Worktree dispatch rules

Set `flags.worktree` only when the selected workflow requires isolated writes.
Before dispatch, resolve the exact checkout path, branch, ownership, and target
integration branch. Workers operate only inside their assigned checkout and
stage only owned files.

Before creating a checkout, run
`python3 ~/.claude/skills/process/worktree-agent/scripts/worktree_capacity.py --repo "$(git rev-parse --show-toplevel)" --strict`.
At 80% used, reclaim inactive accepted clean checkouts before adding one; at
85%, create none. Never remove a worktree with uncommitted or unpushed work.

Use one writable task worktree for implementation and reuse it for fixes. For
read-only work, inspect the candidate from the repository root; allocate no checkout.
For a large repository, prefer `git worktree add --no-checkout`, then
`sparse-checkout init --no-cone` and `sparse-checkout set --no-cone` for the
declared paths; record why a full checkout is required.

After merge, confirm the task is inactive, the branch is integrated, and the
checkout is clean. Then authorized cleanup may run
`git worktree remove -- <accepted-worktree-path>`.
