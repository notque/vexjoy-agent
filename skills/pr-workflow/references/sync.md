# PR Sync Skill

Sync local changes to GitHub in a single command. Detects current state (main vs feature branch, staged vs unstaged changes, existing PRs), then executes the minimum steps needed: branch, commit, push, and create PR. Execute only the steps needed for the current state -- do not add extra commits, rebase, or reorganize history beyond what is required to sync.

## Usage

```
/pr-sync                           # Auto-detect everything
/pr-sync feature/new-auth          # Specify branch name
/pr-sync fix/bug-123 "Fix login"   # Specify branch and PR title
```

## Instructions

### Step 0: Read CLAUDE.md and Classify Repo

Read and follow the repository CLAUDE.md before any git operations, because repo-specific branch conventions, commit formats, or CI requirements override defaults in this skill.

Then determine repo type:

```bash
REPO_TYPE=$(python3 ~/.claude/scripts/classify-repo.py --type-only)
```

**Protected-org repos**: Every subsequent step (commit, push, PR creation) requires **explicit user confirmation**. Present the proposed action, show what will happen, and wait for approval before executing. Never auto-execute, because protected-org repos have CI gates and review policies that assume human oversight at each stage.

**Personal repos**: Run `/pr-review` comprehensive review before creating the PR. Auto-execute steps normally.

### Step 1: Detect Current State

Always detect state before taking any action, because skipping detection risks creating nested branches, committing to the wrong branch, or duplicating work already done.

```bash
# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

# Detect main branch name
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")

# Check for uncommitted changes
HAS_CHANGES=$(git status --porcelain)

# Check for unpushed commits (include these in the push so nothing is left behind)
UNPUSHED=$(git log origin/$CURRENT_BRANCH..$CURRENT_BRANCH --oneline 2>/dev/null)

# Determine if on main/master
ON_MAIN=false
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    ON_MAIN=true
fi
```

If the branch is behind remote, warn the user before pushing so they can pull or rebase first and avoid a rejected push.

### Step 2: Create Branch (if on main)

Never commit directly to main/master -- always create a feature branch first, because direct main commits skip code review, make rollback harder, and can break CI for everyone.

If on main/master with changes, create a feature branch. If no branch name was provided, generate one from the changes or commit message.

Branch naming conventions:

| Change Type | Prefix | Example |
|-------------|--------|---------|
| New feature | `feature/` | `feature/add-auth` |
| Bug fix | `fix/` | `fix/login-error` |
| Documentation | `docs/` | `docs/update-readme` |
| Refactoring | `refactor/` | `refactor/cleanup-utils` |
| Chore/maintenance | `chore/` | `chore/update-deps` |

```bash
git checkout -b "$BRANCH_NAME"
```

If already on a feature branch, skip this step.

### Step 3: Stage and Commit

Stage files selectively by name rather than using `git add -A`, because blind staging catches unintended files -- build artifacts, `.env` files, editor configs, large binaries -- that pollute the repository and may leak secrets. Review `git status`, stage specific files, and verify with `git diff --cached` before committing.

Never commit `.env`, credentials, secrets, or API keys. Block these files and warn the user if they appear in the staging area.

All commit messages use conventional commit format (`type(scope): description`).

```bash
# Stage specific files (not git add -A)
git add path/to/changed/files

# Create commit with conventional format
git commit -m "type(scope): description"
```

If no uncommitted changes exist, skip to Step 4.

**Protected-org repos**: Before executing the commit, present the proposed commit message and list of files to the user. Wait for explicit approval before committing.

### Step 4: Push to Remote

All pushes use standard `git push`, never `--force`, because force pushing destroys remote history and teammates lose work. If push is rejected due to the branch being behind remote, pull with rebase and resolve conflicts rather than forcing.

```bash
# Push with upstream tracking (CLAUDE_GATE_BYPASS=1 bypasses the git-submission-gate hook)
CLAUDE_GATE_BYPASS=1 git push -u origin "$CURRENT_BRANCH"
```

If the user requested a rebase before push, run `git pull --rebase origin $MAIN_BRANCH` first, but this is off by default.

**Protected-org repos**: Before executing the push, present the branch name, remote, and commits that will be pushed. Wait for explicit approval before pushing.

### Step 4a: ADR Decision Coverage (conditional -- ADR-094)

**Skip if**: No `.adr-session.json` exists in the working directory.

When an active ADR session exists, run the coverage check before the review loop:

```bash
python3 scripts/adr-decision-coverage.py --adr <active-adr-path> --diff-base main --human
```

If verdict is PARTIAL or FAIL, display uncovered decision points and ask whether to proceed or address gaps first. This runs once before the review loop, not on every iteration.

### Step 4b: Review-Fix Loop (personal repos only)

**Skip if**: `REPO_TYPE == "protected-org"` (protected-org repos use their own review gates).

Iteratively review and fix issues before creating the PR. Up to 3 iterations of: `/pr-review` -> fix -> amend -> push.

Never modify commits already on the remote except the tip commit just pushed by this workflow. The review-fix loop amends only the tip commit it just created, before any external review, and uses `--force-with-lease` (not `--force`) because lease-checking confirms no one else has pushed to the branch in the meantime.

**Loop (max 3 iterations):**
1. Run `/pr-review` comprehensive review
2. If clean -> exit loop, proceed to Step 5
3. Fix all reported issues
4. `git add [fixes] && git commit --amend --no-edit && CLAUDE_GATE_BYPASS=1 git push --force-with-lease`
5. Report iteration: `REVIEW-FIX [N/3]: X found, Y fixed, Z remaining`

After 3 iterations, proceed to Step 5 with any remaining issues documented in the PR body.

### Step 5: Create or Update PR

Generate the PR title from the branch name or first commit when not provided by the user. Never create a PR with an empty description, because reviewers need context to understand the changes and a missing test plan signals incomplete work.

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

If the user requested a draft PR, add `--draft` to `gh pr create`. If auto-assign reviewers was requested, assign based on CODEOWNERS.

Always show the PR URL after creation for easy access.

**Protected-org repos**: Before executing PR creation, present the PR title, body, and target branch. Wait for explicit approval. Do not run the review-fix loop -- protected-org repos rely on their own CI gates and human reviewers.

### Step 6: Post-Merge ADR Status Update (conditional -- ADR-095)

**Skip if**: No `.adr-session.json` exists, or the PR was only created (not merged).

After a PR is merged (confirmed via `gh pr view --json state`), update the ADR lifecycle:

```bash
# 1. Read active ADR path
ADR_PATH=$(python3 -c "import json; print(json.load(open('.adr-session.json'))['adr_path'])")

# 2. Update status to Accepted
sed -i 's/^## Status$/&/' "$ADR_PATH"  # (use Edit tool in practice)

# 3. Move to completed/
mv "$ADR_PATH" adr/completed/

# 4. Clear session
rm .adr-session.json
```

Report: `ADR updated: {name} -> Accepted, moved to completed/`

This is local-only (ADR files are gitignored). No branch or PR needed.

### Decision Tree

```
/pr-sync invoked
       |
       v
  Read CLAUDE.md + Classify repo (Step 0)
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
*Graduated from learning.db -- multi-agent-coordination/worktree-push-from-wrong-branch*

---

## References

- `/pr-review` -- Comprehensive PR review (used in the review-fix loop)
- `/pr-cleanup` -- Post-merge branch cleanup
- `scripts/classify-repo.py` -- Repo classification for workflow gating
- `scripts/adr-decision-coverage.py` -- ADR decision coverage checker
