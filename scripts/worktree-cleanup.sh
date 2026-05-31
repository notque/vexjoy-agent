#!/usr/bin/env bash
# worktree-cleanup.sh — prune stale worktree refs and zombie branches.
#
# Run after PR merge or when `git worktree list` shows stale entries.
# Safe to run at any time; only removes branches with no worktree checked out
# and that point to commits already merged into main.
#
# Usage:
#   bash scripts/worktree-cleanup.sh          # interactive, confirms each delete
#   bash scripts/worktree-cleanup.sh --dry-run  # report only, no deletions
#   bash scripts/worktree-cleanup.sh --force    # delete without prompts

set -euo pipefail

DRY_RUN=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --force)   FORCE=1 ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "[worktree-cleanup] repo: $REPO_ROOT"
echo ""

# Step 1: prune stale worktree administrative entries (.git/worktrees/<id>
# where the actual directory no longer exists on disk).
echo "=== Step 1: prune stale .git/worktrees entries ==="
if [[ $DRY_RUN -eq 1 ]]; then
    git worktree prune --dry-run --verbose 2>&1 || true
else
    git worktree prune --verbose 2>&1 || true
fi
echo ""

# Step 2: identify zombie branches.
# A zombie branch is a local branch that:
#   (a) matches harness naming patterns (worktree-agent-* or worktree-wf_*)
#   (b) has NO worktree checked out (worktreepath is empty in for-each-ref)
#   OR
#   (a) matches harness naming patterns
#   (b) points to a commit reachable from main (already merged)
echo "=== Step 2: zombie branch analysis ==="

MAIN_BRANCH="main"
# Fall back to master if main doesn't exist.
if ! git rev-parse --verify "$MAIN_BRANCH" >/dev/null 2>&1; then
    MAIN_BRANCH="master"
fi

ZOMBIES=()

while IFS='|' read -r branch worktreepath; do
    # Only inspect harness-created branch patterns.
    case "$branch" in
        worktree-agent-*|worktree-wf_*) ;;
        *) continue ;;
    esac

    # If branch has an active worktree, skip.
    if [[ -n "$worktreepath" ]]; then
        echo "  ACTIVE  $branch  ->  $worktreepath"
        continue
    fi

    # No worktree. Check if the branch tip is merged into main.
    BRANCH_SHA="$(git rev-parse "$branch" 2>/dev/null)" || continue
    MERGE_BASE="$(git merge-base "$MAIN_BRANCH" "$BRANCH_SHA" 2>/dev/null)" || continue

    if [[ "$MERGE_BASE" == "$BRANCH_SHA" ]]; then
        # Branch tip is an ancestor of main — fully merged.
        echo "  ZOMBIE  $branch  (merged into $MAIN_BRANCH)"
        ZOMBIES+=("$branch")
    else
        echo "  UNMERGED $branch  (has commits not in $MAIN_BRANCH)"
    fi
done < <(git for-each-ref --format="%(refname:short)|%(worktreepath)" refs/heads/)

echo ""

if [[ ${#ZOMBIES[@]} -eq 0 ]]; then
    echo "No zombie branches found."
else
    echo "=== Step 3: delete zombie branches ==="
    for branch in "${ZOMBIES[@]}"; do
        if [[ $DRY_RUN -eq 1 ]]; then
            echo "  DRY-RUN  would delete: $branch"
        elif [[ $FORCE -eq 1 ]]; then
            git branch -d "$branch" && echo "  DELETED  $branch" || echo "  SKIP (unmerged guard): $branch"
        else
            read -rp "  Delete zombie branch '$branch'? [y/N] " ans
            case "$ans" in
                [Yy]*) git branch -d "$branch" && echo "  DELETED  $branch" || echo "  SKIP (unmerged guard): $branch" ;;
                *)     echo "  SKIPPED  $branch" ;;
            esac
        fi
    done
fi

echo ""
echo "=== Final worktree list ==="
git worktree list
