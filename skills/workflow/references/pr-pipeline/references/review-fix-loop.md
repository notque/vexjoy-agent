# Review-Fix Loop

Full details for Phase 4b of the PR Pipeline (personal repos only).

## Loop Logic

Up to 3 iterations of `/pr-review` -> fix -> amend commit -> push.

```
ITERATION = 0
MAX_ITERATIONS = 3

while ITERATION < MAX_ITERATIONS:
    ITERATION += 1

    Step 1: Run /pr-review
    Step 2: If no issues found -> EXIT LOOP (proceed to Phase 5)
    Step 3: Fix all reported issues
    Step 4: Stage fixes, amend commit, force push to branch
    Step 5: Report iteration results
```

## Step 1: Run `/pr-review`

Invoke the `/pr-review` command, which launches specialized review agents (code-reviewer, silent-failure-hunter, comment-analyzer, etc.) and captures retro learnings.

## Step 2: Evaluate Results

| Result | Action |
|--------|--------|
| No issues found | **Exit loop**. Proceed to Phase 5 (CREATE PR). |
| Issues found (iteration < 3) | Fix issues in Step 3, then re-review. |
| Issues remaining after iteration 3 | **Exit loop**. Include remaining issues in PR body as known items. Proceed to Phase 5. |

## Step 3: Fix Reported Issues

Address each issue found by the review. This includes:
- Code quality fixes (naming, style, error handling)
- Documentation updates (stale references, missing README entries)
- Test gaps (if flagged)

## Step 4: Amend and Push

```bash
git add [fixed files]
git commit --amend --no-edit
CLAUDE_GATE_BYPASS=1 git push --force-with-lease
```

## Step 5: Iteration Report Format

```
REVIEW-FIX ITERATION [N/3]
  Found: [X issues]
  Fixed: [Y issues]
  Remaining: [Z issues]
  Status: [CLEAN | FIXING | MAX ITERATIONS REACHED]
```
