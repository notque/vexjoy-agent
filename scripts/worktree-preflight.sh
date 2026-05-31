#!/usr/bin/env bash
# worktree-preflight.sh — validate worktree state before an agent starts work.
#
# Exits 0 if the environment is clean, 1 if stale state that could cause
# failures is detected. Run this at the start of a worktree agent task.
#
# Checks:
#   1. Current CWD is inside .claude/worktrees/ (Rule 1 validation)
#   2. No stale .git/worktrees entries for directories that no longer exist
#   3. Target branch (if provided) is not already checked out in another worktree
#
# Usage:
#   bash scripts/worktree-preflight.sh                    # CWD check only
#   bash scripts/worktree-preflight.sh feat/my-branch     # also check branch availability

set -euo pipefail

TARGET_BRANCH="${1:-}"
ISSUES=0

echo "[worktree-preflight] checking environment..."

# Check 1: CWD contains .claude/worktrees/ (worktree isolation is active).
CWD="$(pwd)"
if [[ "$CWD" != *"/.claude/worktrees/"* ]]; then
    echo "ERROR: CWD is not inside a worktree."
    echo "  CWD: $CWD"
    echo "  Expected path containing: /.claude/worktrees/"
    echo "  Stop. Report to the dispatcher that the agent started in the wrong directory."
    ISSUES=$((ISSUES + 1))
else
    echo "OK: CWD is inside a worktree: $CWD"
fi

# Check 2: Prune and report stale worktree admin entries.
STALE="$(git worktree prune --dry-run 2>&1)" || true
if [[ -n "$STALE" ]]; then
    echo "WARN: Stale worktree entries detected (will be pruned by cleanup):"
    echo "$STALE" | sed 's/^/  /'
    git worktree prune 2>&1 || true
    echo "  Auto-pruned."
fi

# Check 3: Target branch availability.
if [[ -n "$TARGET_BRANCH" ]]; then
    CHECKED_OUT="$(git for-each-ref --format="%(refname:short) %(worktreepath)" refs/heads/ | grep "^$TARGET_BRANCH " | awk '{print $2}')" || true
    if [[ -n "$CHECKED_OUT" ]]; then
        echo "ERROR: Branch '$TARGET_BRANCH' is already checked out at: $CHECKED_OUT"
        echo "  Use a unique branch name. Append a timestamp or short UUID to the feature name."
        ISSUES=$((ISSUES + 1))
    else
        # Check if branch exists locally (was created before, may be deleteable).
        if git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
            echo "WARN: Branch '$TARGET_BRANCH' exists locally but is not checked out."
            echo "  Options:"
            echo "    a) Use it: git checkout $TARGET_BRANCH"
            echo "    b) Use a fresh name: git checkout -b ${TARGET_BRANCH}-2"
            echo "    c) Delete and recreate: git branch -D $TARGET_BRANCH && git checkout -b $TARGET_BRANCH"
        else
            echo "OK: Branch '$TARGET_BRANCH' is available for checkout."
        fi
    fi
fi

if [[ $ISSUES -gt 0 ]]; then
    echo ""
    echo "[worktree-preflight] FAILED: $ISSUES issue(s) require attention before proceeding."
    exit 1
fi

echo "[worktree-preflight] PASSED: environment is clean."
exit 0
