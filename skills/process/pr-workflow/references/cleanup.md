# Safe branch cleanup

Resolve exact target branches and reject protected bases (`main`, `master`, `develop`). Check worktree ownership before deletion; never delete a branch still checked out elsewhere. Update the base branch, then use normal merged deletion first.

If `git branch -d` rejects a squash-merged branch, verify its PR is merged and its upstream is gone before proposing forced local deletion. Otherwise treat it as possibly unmerged work. For batch cleanup, preview every target and require explicit confirmation when more than three branches would be removed.

Prune remote-tracking refs after local cleanup and report what was deleted, skipped, or still owns a worktree. Remote branch deletion requires explicit scope from the user or merge workflow.
