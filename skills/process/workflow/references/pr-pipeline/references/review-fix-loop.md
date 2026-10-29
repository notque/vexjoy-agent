# Review-Fix Loop

Full details for the PR Pipeline review-fix loop.

## Loop Logic

Before each commit, run `ruff check`/`ruff format` and the repo's own formatters and linters. Up to 3 iterations of `/pr-review` -> fix -> commit, all local. Push once, after the loop exits clean and `/pr-review` recorded the final SHA. Each fix commit is a new SHA and needs its own review.

```
ITERATION = 0
MAX_ITERATIONS = 3

while ITERATION < MAX_ITERATIONS:
    ITERATION += 1

    Step 1: Run /pr-review
    Step 2: If no issues found -> EXIT LOOP: record, push, then Phase 5
    Step 3: Fix all reported issues
    Step 4: Stage fixes and commit (no push)
    Step 5: Report iteration results
```

## Step 1: Run `/pr-review`

Invoke the `/pr-review` command, which launches specialized review agents (code-reviewer, silent-failure-hunter, comment-analyzer, etc.) and captures retro learnings.

## Step 2: Evaluate Results

| Result | Action |
|--------|--------|
| No issues found | **Exit loop**. `/pr-review` records the SHA (Phase 6b), push the branch, then Phase 5 (CREATE PR). |
| Issues found (iteration < 3) | Fix issues in Step 3, then re-review. |
| Issues remaining after iteration 3 | **Exit loop**. Repos that are not non-fork notque repos: stop and report; do not push. Non-fork notque repos: list remaining issues in the PR body as known items and proceed to Phase 5. |

## Step 3: Fix Reported Issues

Address each issue found by the review. This includes:
- Code quality fixes (naming, style, error handling)
- Documentation updates (stale references, missing README entries)
- Test gaps (if flagged)

## Step 4: Commit, then push after the loop

```bash
git add [fixed files]
git commit -m "fix review findings"
# after the loop exits clean and /pr-review recorded HEAD:
git push -u origin "$(git branch --show-current)"
```

## Step 5: Iteration Report Format

```
REVIEW-FIX ITERATION [N/3]
  Found: [X issues]
  Fixed: [Y issues]
  Remaining: [Z issues]
  Status: [CLEAN | FIXING | MAX ITERATIONS REACHED]
```
