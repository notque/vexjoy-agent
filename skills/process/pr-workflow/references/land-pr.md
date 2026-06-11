# PR Landing Skill

Land an open PR end-to-end: rebase it on a temp branch, run the quality gate, push fork-safe, merge, and verify the merged end state. Use for contributor PRs and any PR that needs a rebase plus local validation before merge.

**End state contract**: `gh pr view` reports state `MERGED`. A `CLOSED` state is a failure — reopen and finish, or report why landing stopped. Final local state: on `main`, fast-forwarded, temp branch deleted.

---

## Instructions

### Step 0: GUARDRAILS

**Goal**: Confirm a safe starting state before touching branches.

```bash
git status -sb   # must be clean
```

Stop and ask the user when any of these hold:

- Working tree has local changes.
- PR is a draft.
- PR has merge conflicts (`mergeable` is `CONFLICTING`).
- Head branch is on a fork and `maintainerCanModify` is false (you cannot push the rebase).

**Gate**: Clean tree, mergeable open PR, push access to the head branch.

### Step 1: CAPTURE PR Context

**Goal**: Record everything needed for the rest of the workflow in one query.

```bash
PR=<number-or-url>
gh pr view "$PR" --json number,title,state,isDraft,mergeable,author,baseRefName,headRefName,headRepository,maintainerCanModify
prnum=$(gh pr view "$PR" --json number --jq .number)
contrib=$(gh pr view "$PR" --json author --jq .author.login)
base=$(gh pr view "$PR" --json baseRefName --jq .baseRefName)
head=$(gh pr view "$PR" --json headRefName --jq .headRefName)
head_repo_url=$(gh api "repos/{owner}/{repo}/pulls/$prnum" --jq .head.repo.clone_url)
```

**Gate**: `state` is `OPEN`; variables captured.

### Step 2: TEMP Branch From Fresh Base

**Goal**: Pin the exact base commit the PR will rebase onto. The temp branch makes the rebase target explicit and keeps `main` untouched until merge.

```bash
git checkout "$base" && git pull --ff-only
git checkout -b "temp/land-pr-$prnum"
```

**Gate**: Temp branch exists at the tip of an up-to-date base.

### Step 3: CHECKOUT PR and Rebase

**Goal**: Replay the PR commits onto the pinned base.

```bash
gh pr checkout "$PR"
git rebase "temp/land-pr-$prnum"
```

Resolve conflicts only when the resolution is obvious from the diff; otherwise `git rebase --abort` and ask the user.

**Gate**: Rebase completes; PR branch now sits on the current base tip.

### Step 4: FIX, Test, Changelog Credit

**Goal**: Make the branch merge-ready with tight scope.

- Apply only fixes needed to land; keep scope to the PR's intent.
- Add or adjust tests when the fix warrants a regression test.
- When the repo keeps a `CHANGELOG.md`, add an entry crediting the contributor: include `#$prnum` and `thanks @$contrib`.

**Gate**: Changes complete, contributor credited.

### Step 5: QUALITY Gate Before Commit

**Goal**: Prove the rebased branch passes the full repo gate locally.

For this repo: `ruff check . --config pyproject.toml && ruff format --check . --config pyproject.toml` plus the test suite. For other repos, run their documented gate (lint, typecheck, tests, docs build).

**Gate**: Every gate command exits 0.

### Step 6: COMMIT Scoped Files

**Goal**: Commit fixes with explicit pathspecs (staging rules: `commit-staging-rules.md`).

```bash
git add <changed-file> [<changed-file>...]   # named paths only
git commit -m "fix: <summary> (#$prnum) (thanks @$contrib)"
land_sha=$(git rev-parse HEAD)
```

Skip this step when Step 4 changed nothing.

**Gate**: Tree clean; `land_sha` recorded.

### Step 7: PUSH Fork-Safe

**Goal**: Update the PR head branch — which may live on a fork — while protecting work pushed since checkout.

A dedicated `prhead` remote targets the head repo directly, so the push works whether the PR comes from a fork or a same-repo branch. `--force-with-lease` rejects the push if the remote moved, protecting contributor commits you have not seen:

```bash
git remote add prhead "$head_repo_url" 2>/dev/null || git remote set-url prhead "$head_repo_url"
git fetch prhead "$head"   # create the tracking ref so the lease has a real baseline
git push --force-with-lease prhead "HEAD:$head"
```

If the lease fails, fetch, inspect the new commits, and redo from Step 3.

**Gate**: Push accepted; PR on GitHub shows the rebased commits.

### Step 8: MERGE

**Goal**: Merge the PR through GitHub so the PR record stays intact.

```bash
gh pr merge "$PR" --squash    # or --rebase per repo convention
```

Merge only — `gh pr close` discards the contribution and breaks the MERGED end-state contract.

**Gate**: Merge command succeeds.

### Step 9: VERIFY End State

**Goal**: Prove the contract, comment with evidence, return local state to clean `main`.

```bash
gh pr view "$PR" --json state,mergedAt --jq '.state + " @ " + .mergedAt'
```

Output must show `MERGED`. Then comment with SHAs and thanks — write the body to a temp file with a quoted heredoc and pass `--body-file` (inline `--body` with `$`/backticks gets shell-mangled):

```bash
merge_sha=$(gh pr view "$PR" --json mergeCommit --jq '.mergeCommit.oid')
cat > /tmp/land-comment.md <<'EOF'
Landed via temp-branch rebase onto BASE.

- Gate: GATE_CMDS
- Land commit: LAND_SHA
- Merge commit: MERGE_SHA

Thanks @CONTRIB!
EOF
# fill placeholders, then:
gh pr comment "$PR" --body-file /tmp/land-comment.md
```

Finally, clean return to main:

```bash
git checkout main && git pull --ff-only
git branch -D "temp/land-pr-$prnum"
git remote remove prhead
git branch --show-current   # must print: main
```

**Gate**: State `MERGED`, comment posted, on `main` at remote tip, temp branch and `prhead` remote removed.

---

## Error Handling

### Error: Rebase conflicts
Cause: Base moved past the PR in conflicting files.
Solution: Resolve only obvious conflicts; otherwise `git rebase --abort`, report the conflicting files, and ask the user.

### Error: `--force-with-lease` rejected
Cause: Contributor pushed new commits after your checkout.
Solution: `git fetch prhead`, review the new commits, redo from Step 3 with them included.

### Error: Push to fork denied
Cause: `maintainerCanModify` is false on the fork PR.
Solution: Ask the contributor to enable "Allow edits by maintainers", or post the rebased diff as review feedback instead of pushing.

### Error: Merge blocked by required checks
Cause: CI has not finished or failed on the rebased head.
Solution: Wait for CI (see `ci-check.md`); if checks fail, fix from Step 4 — leave the PR open, never close it.
