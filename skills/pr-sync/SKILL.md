---
name: pr-sync
description: |
  Sync local changes to GitHub in one command: detect state, branch, commit,
  push, create PR. Use when user wants to push work to GitHub, create a PR,
  or sync a feature branch. Use for "push my changes", "create a PR",
  "sync to GitHub", "open pull request", or "ship this". Do NOT use for
  reviewing PRs (use /pr-review), cleaning up after merge (use pr-cleanup),
  or CI checks (use ci).
version: 2.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# PR Sync Skill

## Purpose

Sync local changes to GitHub in a single command. Detects current state (main vs feature branch, staged vs unstaged changes, existing PRs), then executes the minimum steps needed: branch, commit, push, and create PR.

## Operator Context

This skill operates as an operator for GitHub sync workflows, configuring Claude's behavior for safe, predictable git operations that get local work onto GitHub with a PR.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any git operations
- **Over-Engineering Prevention**: Execute only the steps needed for the current state. Do not add extra commits, rebase, or reorganize history beyond what is required to sync.
- **Never force push**: All pushes use standard `git push`, never `--force`. Exception: the review-fix loop (Step 4b) uses `--force-with-lease` after amending the tip commit, which is safe because the branch was just pushed by us.
- **Never modify pushed commits**: Commits already on remote are immutable. Exception: the review-fix loop amends only the tip commit it just created, before any external review.
- **Never commit sensitive files**: Block `.env`, credentials, secrets, API keys
- **Conventional commit format**: All commit messages follow conventional commits
- **Branch protection**: Never commit directly to main/master
- **Repo-Aware Review Gate**: Classify repo before creating PR. For personal repos, run up to 3 iterations of `/pr-review` → fix before PR creation. For protected-org repos, every step requires explicit user confirmation.
- **Organization-Gated Workflow**: Repos under protected organizations (configured in `scripts/classify-repo.py`) require user confirmation before EACH step: commit message review, push, and PR creation. Never auto-execute any of these steps. Present the proposed action and wait for user approval.

### Default Behaviors (ON unless disabled)
- **Auto-detect branch name**: Generate from commit message or changed files when not provided
- **Auto-detect PR title**: Derive from branch name or first commit when not provided
- **Stage selectively**: Prefer staging specific files over `git add -A`
- **Check for unpushed commits**: Include existing unpushed commits in the push
- **Warn if behind remote**: Alert user if branch is behind main before pushing
- **Show PR URL**: Display the PR URL after creation for easy access

### Optional Behaviors (OFF unless enabled)
- **Draft PR**: Create PR as draft instead of ready for review
- **Auto-assign reviewers**: Assign reviewers based on CODEOWNERS
- **Rebase before push**: Rebase on main before pushing to avoid merge conflicts

## What This Skill CAN Do
- Detect current git state and choose the right workflow
- Create feature branches from main/master with conventional naming
- Stage, commit, and push changes in sequence
- Create GitHub PRs with summary and test plan
- Update existing PRs by pushing new commits

## What This Skill CANNOT Do
- Force push to shared/upstream branches (force-with-lease on own feature branches during review-fix loop is permitted)
- Review PRs (use /pr-review instead)
- Clean up merged branches (use pr-cleanup instead)
- Run CI checks (use ci instead)
- Commit directly to main/master

---

## Instructions

### Usage

```
/pr-sync                           # Auto-detect everything
/pr-sync feature/new-auth          # Specify branch name
/pr-sync fix/bug-123 "Fix login"   # Specify branch and PR title
```

### Step 0: Classify Repo

Determine repo type before any git operations.

```bash
REPO_TYPE=$(python3 scripts/classify-repo.py --type-only)
```

**Protected-org repos**: Every subsequent step (commit, push, PR creation) requires **explicit user confirmation**. Present the proposed action, show what will happen, and wait for approval before executing. Never auto-execute.

**Personal repos**: Run `/pr-review` comprehensive review before creating the PR. Auto-execute steps normally.

### Step 1: Detect Current State

Determine the starting point before taking any action.

```bash
# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

# Detect main branch name
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")

# Check for uncommitted changes
HAS_CHANGES=$(git status --porcelain)

# Check for unpushed commits
UNPUSHED=$(git log origin/$CURRENT_BRANCH..$CURRENT_BRANCH --oneline 2>/dev/null)

# Determine if on main/master
ON_MAIN=false
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    ON_MAIN=true
fi
```

### Step 2: Create Branch (if on main)

If on main/master with changes, create a feature branch first.

Branch naming conventions:

| Change Type | Prefix | Example |
|-------------|--------|---------|
| New feature | `feature/` | `feature/add-auth` |
| Bug fix | `fix/` | `fix/login-error` |
| Documentation | `docs/` | `docs/update-readme` |
| Refactoring | `refactor/` | `refactor/cleanup-utils` |
| Chore/maintenance | `chore/` | `chore/update-deps` |

```bash
# If no branch name provided, generate from changes or commit message
# Create and switch to new branch
git checkout -b "$BRANCH_NAME"
```

If already on a feature branch, skip this step.

### Step 3: Stage and Commit

Stage changes selectively and create a conventional commit.

```bash
# Stage specific files (prefer over git add -A)
git add path/to/changed/files

# Create commit with conventional format
git commit -m "type(scope): description"
```

If no uncommitted changes exist, skip to Step 4.

**Protected-org repos**: Before executing the commit, present the proposed commit message and list of files to the user. Wait for explicit approval before committing.

### Step 4: Push to Remote

```bash
# Push with upstream tracking (CLAUDE_GATE_BYPASS=1 bypasses the git-submission-gate hook)
CLAUDE_GATE_BYPASS=1 git push -u origin "$CURRENT_BRANCH"
```

**Protected-org repos**: Before executing the push, present the branch name, remote, and commits that will be pushed. Wait for explicit approval before pushing.

### Step 4b: Review-Fix Loop (personal repos only)

Iteratively review and fix issues before creating the PR. Up to 3 iterations of: `/pr-review` → fix → amend → push.

**Skip if**: `REPO_TYPE == "protected-org"` (protected-org repos use their own review gates).

**Loop (max 3 iterations):**
1. Run `/pr-review` comprehensive review
2. If clean → exit loop, proceed to Step 5
3. Fix all reported issues
4. `git add [fixes] && git commit --amend --no-edit && CLAUDE_GATE_BYPASS=1 git push --force-with-lease`
5. Report iteration: `REVIEW-FIX [N/3]: X found, Y fixed, Z remaining`

After 3 iterations, proceed to Step 5 with any remaining issues documented in the PR body.

### Step 5: Create or Update PR

```bash
# Check if PR already exists for this branch
EXISTING_PR=$(gh pr list --head "$CURRENT_BRANCH" --json number --jq '.[0].number' 2>/dev/null)

if [[ -z "$EXISTING_PR" ]]; then
    # Create new PR
    CLAUDE_GATE_BYPASS=1 gh pr create --title "$PR_TITLE" --body "$(cat <<'EOF'
## Summary
[Description of changes]

## Test Plan
- [ ] Tested locally
- [ ] Tests pass
EOF
)"
else
    # PR exists, just pushed updates
    echo "PR #$EXISTING_PR updated with new commits"
    gh pr view "$EXISTING_PR" --web
fi
```

### Decision Tree

```
/pr-sync invoked
       |
       v
  Classify repo (Step 0)
       |
       v
  Has changes?
   /        \
 YES         NO
  |           |
  v           v
On main?    PR exists?
 / \         / \
YES  NO    YES  NO
 |    |     |    |
 v    v     v    v
Create  Stage  Show  Create
branch  commit link  PR
  |      |
  v      v
Stage & commit
  |
  v
protected-org? ──YES──> Confirm commit msg with user
  |                    |
  NO                   v
  |              Confirm push with user
  v                    |
Push to remote  <──────┘
  |
  v
protected-org? ──YES──> Confirm PR creation with user
  |                    |
  NO                   v
  |              Create PR, STOP (no merge)
  v
┌─> Run /pr-review (iteration N/3)
|     |
|     v
|   Issues found?
|    / \
|  YES  NO ──────> Create PR
|   |
|   v
|  Fix issues
|   |
|   v
|  Amend commit, push
|   |
|   v
|  N < 3? ──YES──┐
|   |             |
|   NO            |
|   |             |
|   v             |
|  Create PR      |
|  (note remaining)|
└─────────────────┘
```

### Output Format

**Personal repos:**
```
PR SYNC COMPLETE

Status: [on main -> created branch | on feature branch]
Changes: [N files modified]
Review: /pr-review [N iterations] — [X issues found, Y fixed]

Actions:
  - Created branch: feature/your-feature (if from main)
  - Staged N files
  - Committed: "your commit message"
  - Pushed to origin/feature/your-feature
  - Review-fix loop: [N/3 iterations]
    - Iteration 1: [X found, Y fixed]
    - Iteration 2: [X found, Y fixed] (if needed)
    - Iteration 3: [X found, Y fixed] (if needed)
  - Created PR #123: "PR Title"
    https://github.com/owner/repo/pull/123
```

**Protected-org repos:**
```
PR SYNC COMPLETE (protected-org repo — human-gated)

Status: [on feature branch]
Changes: [N files modified]

Actions (each confirmed by user):
  - Committed: "your commit message" (user confirmed)
  - Pushed to origin/feature/your-feature (user confirmed)
  - Created PR #123: "PR Title" (user confirmed)
    https://github.com/your-org/your-repo/pull/123

Next steps: Review and merge handled by org CI gates and human reviewers.
```

---

## Error Handling

### Error: "Push rejected - branch behind remote"
Cause: Remote branch has commits not present locally (teammate pushed, or previous rebase).
Solution:
1. Run `git pull --rebase origin $CURRENT_BRANCH`
2. Resolve any conflicts if they arise
3. Retry the push
4. If conflicts are complex, inform the user and show the conflicting files

### Error: "gh: not authenticated"
Cause: GitHub CLI is not authenticated or token expired.
Solution:
1. Run `gh auth status` to confirm
2. Instruct user to run `gh auth login`
3. Do not proceed with PR creation until auth is confirmed

### Error: "No changes to commit"
Cause: All changes are already committed, or working tree is clean.
Solution:
1. Check for unpushed commits with `git log origin/$BRANCH..$BRANCH`
2. If unpushed commits exist, skip to push step
3. If no unpushed commits, check if PR exists and show its status
4. If nothing to do, report clean state to user

### Error: "Branch name already exists"
Cause: A branch with the generated name already exists locally or on remote.
Solution:
1. Check if user is already on that branch (`git branch --show-current`)
2. If different branch, append a suffix (e.g., `-v2`) or ask user for alternative name
3. Never silently overwrite an existing branch

### Error: "Cannot delete branch used by worktree"
Cause: A git worktree references the branch, blocking deletion during PR merge or cleanup.
Solution:
1. Run `git worktree list` to identify the worktree using the branch
2. Run `git worktree remove <path>` to detach the worktree
3. Retry the branch deletion or PR merge with `--delete-branch`
4. This commonly happens when worktree agents (`isolation: "worktree"`) created the branch

### Error: "git push says up-to-date but changes are missing on remote"
Cause: `git push origin master` reports "up-to-date" when HEAD is on a different branch. Git pushes the named remote ref, not the current branch, so feature branch commits are never pushed.
Solution:
1. Always push the current branch: `git push -u origin $(git branch --show-current)`
2. Never hardcode branch names in push commands
3. Verify after push: `git log origin/$(git branch --show-current)..HEAD` should show 0 commits
*Graduated from learning.db — multi-agent-coordination/worktree-push-from-wrong-branch*

---

## Anti-Patterns

### Anti-Pattern 1: Committing Everything with git add -A
**What it looks like**: Running `git add -A` without checking what will be staged.
**Why wrong**: Catches unintended files -- build artifacts, `.env` files, editor configs, large binaries. These pollute the repository and may leak secrets.
**Do instead**: Review `git status`, stage specific files by name, verify with `git diff --cached` before committing.

### Anti-Pattern 2: Force Pushing to Resolve Conflicts
**What it looks like**: Push fails, so running `git push --force` to override.
**Why wrong**: Destroys remote history. Teammates lose work. PRs become inconsistent.
**Do instead**: Pull with rebase, resolve conflicts, push normally. If the situation is complex, inform the user rather than forcing.

### Anti-Pattern 3: Creating PR with Empty Description
**What it looks like**: `gh pr create --title "Updates" --body ""`
**Why wrong**: Reviewers have no context. PR purpose is unclear. Test plan is missing.
**Do instead**: Generate a summary from the diff and commit messages. Include a test plan section. Even a brief description is better than none.

### Anti-Pattern 4: Skipping State Detection
**What it looks like**: Immediately creating a branch and committing without checking current state.
**Why wrong**: May create nested branches, commit to wrong branch, or duplicate work already done.
**Do instead**: Always run Step 1 first. Detect branch, changes, and PR state before taking any action.

### Anti-Pattern 5: Committing Directly to Main
**What it looks like**: Staging and committing on main/master instead of creating a feature branch.
**Why wrong**: Violates branch protection conventions. Makes rollback harder. Skips code review.
**Do instead**: Always create a feature branch from main before committing. The only exception is if the user explicitly authorizes a direct commit.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Quick push to main, I'll branch later" | Main commits skip review and break CI | Create branch first, always |
| "git add -A is fine, nothing sensitive" | Assumption without checking | Review status, stage selectively |
| "PR description can wait" | Reviewers need context now, not later | Write summary before creating PR |
| "Force push fixes the conflict" | Destroys teammate work on remote | Pull, rebase, resolve, push normally |
