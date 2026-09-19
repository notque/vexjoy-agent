# Preflight Checklist

Full details for Phase 0.5 of the PR Pipeline.

## Check Table

Run all checks sequentially. Abort on the first failure.

| # | Check | Command | Failure Action |
|---|-------|---------|---------------|
| 1 | Verification status (did quality gates pass?) | Check for recent test/build output or verification artifacts | Abort: "Run verification first -- no evidence that quality gates passed." |
| 2 | Clean working tree (no uncommitted changes) | `git status --porcelain` | Abort: "Working tree is dirty. Uncommitted files:\n{list}. Stage or stash before running PR pipeline." |
| 3 | Correct branch (not main/master) | `git branch --show-current` | Abort: "Currently on {branch}. Create a feature branch first: `git checkout -b type/description`" |
| 4 | Remote configured for current branch | `git config --get branch.$(git branch --show-current).remote` | Abort: "No remote configured for branch. Push with: `git push -u origin $(git branch --show-current)`" |
| 5 | `gh` CLI authenticated | `gh auth status 2>&1` | Abort: "GitHub CLI not authenticated. Run: `gh auth login`" |

## Bash Script

```bash
# Preflight check sequence
echo "Running preflight checklist..."

# Check 1: Verification status
# Look for verification artifacts (test output, build logs) — if the project
# has a test suite and no recent verification evidence exists, warn.
# This is a soft gate: skip if no test infrastructure is detected.

# Check 2: Clean working tree
DIRTY=$(git status --porcelain)
if [ -n "$DIRTY" ]; then
    echo "PREFLIGHT FAIL: Working tree is dirty."
    echo "$DIRTY"
    echo "Stage or stash uncommitted changes before running PR pipeline."
    exit 1
fi

# Check 3: Not on main/master
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "PREFLIGHT FAIL: On branch '$BRANCH'."
    echo "Create a feature branch: git checkout -b type/description"
    exit 1
fi

# Check 4: Remote configured
REMOTE=$(git config --get "branch.$BRANCH.remote" 2>/dev/null)
if [ -z "$REMOTE" ]; then
    echo "PREFLIGHT FAIL: No remote configured for branch '$BRANCH'."
    echo "Push with: git push -u origin $BRANCH"
    exit 1
fi

# Check 5: gh CLI authenticated
if ! gh auth status >/dev/null 2>&1; then
    echo "PREFLIGHT FAIL: GitHub CLI not authenticated."
    echo "Run: gh auth login"
    exit 1
fi

echo "Preflight checklist PASSED."
```

## Note on Check 1 (Verification Status)

This is context-dependent. If the project has a test suite (`go test`, `npm test`, `pytest`, etc.), look for evidence that tests were run recently (e.g., verification report files, recent test output in the session). If no test infrastructure exists, this check passes by default. The goal is to prevent submitting code that was never tested, not to block projects without tests.
