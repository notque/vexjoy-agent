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

## Required worker preflight and plan

Run `bash scripts/worktree-preflight.sh <assigned-branch>` before edits. Confirm
this is the assigned linked checkout and feature branch; stop on another task's
branch. Reuse the assigned branch or create a unique one; never delete a
colliding branch or change the main checkout. Use checkout-relative paths.

The router must prepare the Simple+ `task_plan.md` inside this task's checkout
before dispatch. The worker reads and updates it as needed; an auto-plan hook
cannot authorize ignoring it. Never write another checkout's plan or state.

Stage explicit owned paths only, never `git add .`, `git add -A`, or
`git add --all`; inspect the staged diff. Follow the user's commit wording and
omit attribution lines. Python changes require both configured Ruff lint and
format checks before claiming CI-ready. After a merge command's local checkout
error, verify the remote PR state before retrying or claiming success.
