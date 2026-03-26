---
name: pr-cleanup
description: |
  Local branch cleanup after PR merge: identify, switch, delete, prune in
  4 steps. Use when a PR has been merged and local branches need cleanup,
  when stale branches accumulate, or when user says "clean up branches",
  "delete merged branch", or "prune". Do NOT use for branch creation,
  PR review, or CI checks.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Bash
  - Read
routing:
  triggers:
    - "cleanup branches"
    - "delete merged branch"
    - "prune branches"
  category: git-workflow
---

# PR Cleanup Skill

## Operator Context

This skill operates as an operator for post-merge branch cleanup, configuring Claude's behavior for safe, systematic removal of stale local branches. It implements a **Sequential Safety** pattern -- identify target, verify merge status, delete safely, confirm result.

### Hardcoded Behaviors (Always Apply)
- **Protected Branches**: NEVER delete main, master, or develop branches
- **Safe Delete First**: Always use `git branch -d` before considering `-D`
- **Identify Before Switch**: Capture branch name BEFORE switching to main
- **Verify Merge Status**: Confirm branch was merged or remote-deleted before removing
- **Report Results**: Always show what was deleted and what remains
- **Worktree Cleanup First**: Before deleting any branch, check if a git worktree references it. Worktree branches block `git branch -d/-D` and `gh pr merge --delete-branch`. Run `git worktree remove` before branch deletion.

### Default Behaviors (ON unless disabled)
- **Prune Remote References**: Run `git remote prune origin` after cleanup
- **Pull Latest**: Pull main/master with `--prune` after switching
- **Show Remaining Branches**: List local branches after cleanup completes
- **Squash-Merge Detection**: Check for `[gone]` upstream when `-d` fails

### Optional Behaviors (OFF unless enabled)
- **Batch Cleanup**: Delete all merged branches with `--all` flag
- **Dry Run**: Show what would be deleted without acting, with `--dry-run` flag

## What This Skill CAN Do
- Delete local branches that have been merged into main/master
- Detect squash-merged branches by checking upstream tracking status
- Batch-delete all merged branches except protected ones
- Prune stale remote-tracking references
- Dry-run to preview cleanup actions

## What This Skill CANNOT Do
- Delete remote branches (local cleanup only)
- Review or merge PRs (use /pr-review instead)
- Run CI checks (use ci skill instead)
- Create or rename branches
- Force-delete unmerged branches without explicit user confirmation

---

## Instructions

### Step 0: CHECK for Worktrees

**Goal**: Remove any git worktrees referencing the target branch before attempting deletion.

Worktree agents (dispatched with `isolation: "worktree"`) create local branches that block both `git branch -d` and `gh pr merge --delete-branch`. Check and clean up worktrees first:

```bash
# List worktrees referencing any branch
git worktree list

# If the target branch appears in a worktree, remove it
git worktree remove <worktree-path>
```

If worktree removal fails (e.g., uncommitted changes), report the issue to the user. Do not force-remove without confirmation.

**Gate**: No worktrees reference the target branch.

### Step 1: IDENTIFY Target Branch

**Goal**: Determine which branch to clean up before any state changes.

If user provides a branch name argument, use that. Otherwise capture the current branch:

```bash
BRANCH_TO_DELETE=$(git branch --show-current)
```

If already on main/master, ask the user which branch to clean up. Do not proceed without a target.

Detect the main branch name:

```bash
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
```

**Gate**: Branch to delete is identified and is NOT a protected branch (main/master/develop).

### Step 2: SWITCH and Pull

**Goal**: Move to main branch and sync with remote.

```bash
git checkout "$MAIN_BRANCH" && git pull --prune origin "$MAIN_BRANCH"
```

**Gate**: Successfully on main/master with latest changes.

### Step 3: DELETE Local Branch

**Goal**: Remove the target branch safely.

Attempt safe delete first:

```bash
git branch -d "$BRANCH_TO_DELETE"
```

If `-d` fails with "not fully merged":
1. Check if branch was squash-merged by looking for gone upstream:
   ```bash
   git branch --format '%(refname:short) %(upstream:track)' | grep "$BRANCH_TO_DELETE"
   ```
2. If upstream shows `[gone]`, the remote branch was deleted (PR was merged). Inform user and offer `-D`.
3. If upstream is NOT gone, warn user the branch may contain unmerged work. Only use `-D` with explicit user confirmation.

Prune stale remote-tracking references:

```bash
git remote prune origin
```

**Gate**: Target branch deleted and remote references pruned.

### Step 4: REPORT Results

**Goal**: Confirm what happened and show current state.

Report format:

```
PR Cleanup Complete
  - Switched to: [main branch name]
  - Deleted local branch: [branch name]
  - Pruned remote references
  - Remaining local branches:
    [list from git branch]
```

Run `git branch` to show remaining local branches.

---

## Extended Cleanup (--all)

When user passes `--all`, first remove all stale worktrees, then delete branches:

```bash
# Step 0: Clean up worktrees pointing at branches we're about to delete
git worktree list --porcelain | grep -A2 'branch refs/heads/' | grep -v 'main\|master\|develop'
# For each stale worktree: git worktree remove <path>
```

Then delete all branches merged into main except protected branches:

```bash
git branch --merged "$MAIN_BRANCH" | grep -v -E '^\*|main|master|develop' | xargs -r git branch -d
```

Also find squash-merged branches with gone upstreams:

```bash
git branch --format '%(refname:short) %(upstream:track)' | awk '$2 == "[gone]" { print $1 }'
```

Show the full list before deleting and confirm with user if more than 3 branches.

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

## Anti-Patterns

### Anti-Pattern 1: Force-Deleting Without Checking Merge Status
**What it looks like**: Using `git branch -D` immediately without trying `-d` first
**Why wrong**: May destroy unmerged work with no recovery path
**Do instead**: Always try `-d` first, check merge/upstream status, then `-D` only with evidence

### Anti-Pattern 2: Deleting Before Switching
**What it looks like**: Trying to delete the current branch while still on it
**Why wrong**: Git will refuse, causing a confusing error
**Do instead**: Always switch to main/master before deleting the target branch

### Anti-Pattern 3: Skipping the Report
**What it looks like**: Deleting branches silently without showing what was removed
**Why wrong**: User has no confirmation of what happened, no visibility into remaining state
**Do instead**: Always list deleted branches and remaining local branches

### Anti-Pattern 4: Batch Delete Without Preview
**What it looks like**: Running `--all` and deleting everything without showing the list first
**Why wrong**: May delete branches user intended to keep
**Do instead**: Show the list of branches to be deleted and confirm before proceeding

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
