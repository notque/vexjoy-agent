# PR Cleanup Skill

## Overview

This skill provides safe, systematic cleanup of local branches after PR merge. It implements a **Sequential Safety** pattern: identify target, verify merge status, delete safely, confirm result. The workflow follows 5 sequential steps to prevent data loss and ensure reliable cleanup.

---

## Instructions

### Step 0: CHECK for Worktrees

**Goal**: Remove any git worktrees referencing the target branch before attempting deletion.

Worktree agents (dispatched with `isolation: "worktree"`) create local branches that block both `git branch -d` and `gh pr merge --delete-branch`. Since worktree branches prevent deletion, check and clean up first:

```bash
# List worktrees referencing any branch
git worktree list

# If the target branch appears in a worktree, remove it
git worktree remove <worktree-path>
```

If worktree removal fails (e.g., uncommitted changes), report the issue to the user rather than force-removing, to avoid data loss.

**Gate**: No worktrees reference the target branch.

### Step 1: IDENTIFY Target Branch

**Goal**: Determine which branch to clean up before any state changes.

Capture the target branch *before* switching (switching state changes current branch and complicates recovery). If user provides a branch name, use that; otherwise:

```bash
BRANCH_TO_DELETE=$(git branch --show-current)
```

If already on main/master, ask the user which branch to clean up — do not assume and prevent accidental deletion of the base branch.

Never delete protected branches (main, master, develop) — these are the foundation of the repo and accidentally deleting them causes widespread damage. Detect the main branch name for later use:

```bash
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
```

**Gate**: Branch to delete is identified and is NOT a protected branch (main/master/develop).

### Step 2: SWITCH and Pull

**Goal**: Move to main branch and sync with remote.

Must switch away from the target branch before deletion — git forbids deleting the current branch. Prune old remote-tracking references to keep the branch list clean:

```bash
git checkout "$MAIN_BRANCH" && git pull --prune origin "$MAIN_BRANCH"
```

**Gate**: Successfully on main/master with latest changes.

### Step 3: DELETE Local Branch

**Goal**: Remove the target branch safely.

Use `-d` (safe delete) before `-D` (force delete) to prevent destroying unmerged work. Git's `-d` will refuse to delete branches with unmerged commits — this is a guard rail:

```bash
git branch -d "$BRANCH_TO_DELETE"
```

If `-d` fails with "not fully merged":

Squash-merged and rebase-merged branches have no merge commit, so git doesn't recognize them as merged. Check if the remote branch was deleted (indicating a completed PR):

```bash
git branch --format '%(refname:short) %(upstream:track)' | grep "$BRANCH_TO_DELETE"
```

If upstream shows `[gone]`, the remote branch was deleted after PR merge — evidence the work is safe. Inform user and offer `-D` for forced deletion.

If upstream is NOT gone, the branch may contain unmerged work — warn user and ask for explicit confirmation before using `-D`. Never force-delete without user confirmation on unknown merge status.

Prune stale remote-tracking references to keep the reference list accurate:

```bash
git remote prune origin
```

**Gate**: Target branch deleted and remote references pruned.

### Step 4: REPORT Results

**Goal**: Confirm what happened and show current state.

Always report results so the user has visibility into what was removed and the final state. This prevents silent failures and gives confidence the cleanup succeeded:

```
PR Cleanup Complete
  - Switched to: [main branch name]
  - Deleted local branch: [branch name]
  - Pruned remote references
  - Remaining local branches:
    [list from git branch]
```

Run `git branch` to show remaining local branches.

## Extended Cleanup (--all)

When user passes `--all`, batch-delete all merged branches except protected ones.

**Safety first**: Preview the branch list before deleting. If more than 3 branches will be deleted, ask for explicit confirmation to prevent unexpected wholesale cleanup:

First, remove all stale worktrees pointing at branches we're about to delete:

```bash
# Step 0: Clean up worktrees pointing at branches we're about to delete
git worktree list --porcelain | grep -A2 'branch refs/heads/' | grep -v 'main\|master\|develop'
# For each stale worktree: git worktree remove <path>
```

Then delete all branches merged into main except protected branches (never delete main/master/develop):

```bash
git branch --merged "$MAIN_BRANCH" | grep -v -E '^\*|main|master|develop' | xargs -r git branch -d
```

Also find and delete squash-merged branches by detecting gone upstreams:

```bash
git branch --format '%(refname:short) %(upstream:track)' | awk '$2 == "[gone]" { print $1 }'
```

Show the full list before deleting and confirm with user if more than 3 branches to prevent accidental data loss.

---

## Examples

### Example 1: Current Branch Cleanup
User says: `/pr-cleanup`
Actions:
1. Capture current branch name (IDENTIFY)
2. Switch to main, pull latest (SWITCH)
3. Delete the branch with `-d`, prune remote refs (DELETE)
4. Show remaining branches (REPORT)

### Example 2: Named Branch Cleanup
User says: `/pr-cleanup feature/auth-flow`
Actions:
1. Use `feature/auth-flow` as target (IDENTIFY)
2. Switch to main, pull latest (SWITCH)
3. Delete `feature/auth-flow`, prune remote refs (DELETE)
4. Show remaining branches (REPORT)

### Example 3: Squash-Merged Branch
User says: `/pr-cleanup` on a squash-merged branch
Actions:
1. Capture current branch name (IDENTIFY)
2. Switch to main, pull latest (SWITCH)
3. `-d` fails, detect `[gone]` upstream, use `-D` after informing user (DELETE)
4. Show remaining branches (REPORT)

---

## Error Handling

### Error: "Branch not fully merged"
Cause: Branch was squash-merged or rebase-merged, so git does not recognize it as merged
Solution:
1. Check if upstream tracking shows `[gone]` (remote branch deleted after PR merge)
2. If gone, inform user and use `git branch -D` to force-delete
3. If not gone, warn user branch may have unmerged work and ask for confirmation

### Error: "Cannot delete checked-out branch"
Cause: Attempting to delete the branch you are currently on
Solution:
1. Switch to main/master first with `git checkout`
2. Then retry the delete operation

### Error: "Cannot determine main branch"
Cause: `refs/remotes/origin/HEAD` is not set (common in freshly cloned repos)
Solution:
1. Try `git remote set-head origin --auto` to set it
2. Fall back to checking if `main` or `master` exists locally
3. Ask user to specify if neither is found

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
