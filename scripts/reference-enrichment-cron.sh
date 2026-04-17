#!/usr/bin/env bash
# Reference Enrichment: hourly domain knowledge improvement via Claude Code headless mode.
# Runs the ADR-171 audit to identify knowledge gaps, then uses ADR-172's enrichment
# skill to generate reference files for the top-priority agents/skills.
#
# Usage:
#   # Dry run (audit only, no enrichment)
#   ./scripts/reference-enrichment-cron.sh
#
#   # Full run (audit + enrich + PR)
#   ./scripts/reference-enrichment-cron.sh --execute
#
#   # Decomposition run (split oversized references)
#   ./scripts/reference-enrichment-cron.sh --decompose
#
# Cron example (hourly at :07):
#   7 * * * * /home/feedgen/claude-code-toolkit/scripts/reference-enrichment-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/reference-enrichment/cron.log 2>&1

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:$PATH"

# Ensure GitHub CLI auth for PR creation (cron doesn't source .bashrc)
if [ -z "${GH_TOKEN:-}" ]; then
    export GH_TOKEN=$(python3 -c "
import subprocess
r = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n', capture_output=True, text=True)
print(next((l.split('=',1)[1] for l in r.stdout.split('\n') if l.startswith('password=')), ''))
" 2>/dev/null)
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/cron-logs/reference-enrichment"
LOCKFILE="/tmp/reference-enrichment.lock"
MAX_BUDGET="${MAX_BUDGET_USD:-5.00}"
MAX_TARGETS="${MAX_TARGETS:-1}"
MAX_DECOMP_TARGETS="${MAX_DECOMP_TARGETS:-1}"
MAX_OPEN_DECOMP_PRS="${MAX_OPEN_DECOMP_PRS:-3}"
EXECUTE=""
DECOMPOSE=""

# Cleanup function: release lock FD, remove stale worktree, and remove lockfile on any exit
cleanup() {
    if [ -n "${ENRICH_WORKTREE:-}" ] && [ -d "$ENRICH_WORKTREE" ]; then
        cd "$REPO_DIR" 2>/dev/null || true
        git worktree remove "$ENRICH_WORKTREE" --force 2>/dev/null || true
    fi
    if [ -n "${DECOMP_WORKTREE:-}" ] && [ -d "$DECOMP_WORKTREE" ]; then
        cd "$REPO_DIR" 2>/dev/null || true
        git worktree remove "$DECOMP_WORKTREE" --force 2>/dev/null || true
    fi
    exec 9>&- 2>/dev/null
    rm -f "$LOCKFILE"
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --execute) EXECUTE="1" ;;
        --decompose) DECOMPOSE="1" ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

# Mutual exclusivity check
if [ -n "$EXECUTE" ] && [ -n "$DECOMPOSE" ]; then
    echo "ERROR: --execute and --decompose are mutually exclusive" >&2
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date -Iseconds) SKIP: another reference-enrichment instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

# Now that we hold the lock, register cleanup for any exit path
trap cleanup EXIT

# All git operations need to run from inside the repo
cd "$REPO_DIR"

TIMESTAMP="$(date -Iseconds)"
echo "=== Reference Enrichment run: $TIMESTAMP ==="

MODE="dry-run"
[ -n "$EXECUTE" ] && MODE="enrich-live"
[ -n "$DECOMPOSE" ] && MODE="decompose-live"
echo "Mode: $MODE | Budget: \$${MAX_BUDGET} | Max targets: ${MAX_TARGETS}"

# Fetch latest remote main (safe: does not touch working tree)
echo "Fetching latest remote main..."
git fetch origin main
echo "Remote main at $(git rev-parse --short origin/main)"

# Prune stale worktrees left by prior crashes
git worktree prune 2>/dev/null || true

# Clean up stale agent worktrees older than 3 days (.claude/worktrees/agent-*)
if [ -d "$REPO_DIR/.claude/worktrees" ]; then
    find "$REPO_DIR/.claude/worktrees" -maxdepth 1 -name 'agent-*' -type d -mtime +3 -print0 2>/dev/null | while IFS= read -r -d '' wt; do
        echo "Removing stale agent worktree: $(basename "$wt")"
        git worktree remove "$wt" --force 2>/dev/null || rm -rf "$wt"
    done
    git worktree prune 2>/dev/null || true
fi

if [ -n "$DECOMPOSE" ]; then
    # === DECOMPOSITION MODE ===

    # Guard: check for too many open decomposition PRs
    if command -v gh &>/dev/null; then
        OPEN_DECOMP_PRS=$(gh pr list --search "decomp/refs" --state open --json number 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
        if [ "$OPEN_DECOMP_PRS" -ge "$MAX_OPEN_DECOMP_PRS" ]; then
            echo "$(date -Iseconds) SKIP: ${OPEN_DECOMP_PRS} open decomposition PRs (max: ${MAX_OPEN_DECOMP_PRS}). Review/merge existing PRs first."
            exit 0
        fi
        echo "Open decomposition PRs: ${OPEN_DECOMP_PRS}/${MAX_OPEN_DECOMP_PRS}"
    fi

    # Detect oversized references that need decomposition
    DECOMP_TARGETS=$(python3 "$REPO_DIR/scripts/detect-decomposition-targets.py" --json --min-lines 500 2>/dev/null)
    DECOMP_TARGET_COUNT=$(echo "$DECOMP_TARGETS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))")

    if [ "$DECOMP_TARGET_COUNT" -eq 0 ]; then
        echo "$(date -Iseconds) No decomposition targets found (all references under 500 lines). Exiting cleanly."
        exit 0
    fi

    echo "Found ${DECOMP_TARGET_COUNT} decomposition target(s). Processing up to ${MAX_DECOMP_TARGETS}."

    # Limit targets
    DECOMP_TARGETS_TRIMMED=$(echo "$DECOMP_TARGETS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d[:${MAX_DECOMP_TARGETS}]))")

    # Build envsubst variables
    export DECOMP_REPO_DIR="$REPO_DIR"
    export DECOMP_TARGETS="$DECOMP_TARGETS_TRIMMED"
    export DECOMP_DATE="$(date +%Y-%m-%d)"
    export DECOMP_RUN_ID="$(date +%Y-%m-%d-%H%M)"
    export DECOMP_MAX_TARGETS="$MAX_DECOMP_TARGETS"
    export DECOMP_DRY_RUN_MODE="no"

    # Create temporary worktree for isolated decomposition work
    DECOMP_WORKTREE="/tmp/decomp-worktree-${DECOMP_RUN_ID}"
    git worktree add "$DECOMP_WORKTREE" origin/main 2>/dev/null || {
        # If worktree already exists, remove and recreate
        git worktree remove "$DECOMP_WORKTREE" --force 2>/dev/null || true
        git worktree add "$DECOMP_WORKTREE" origin/main
    }
    export DECOMP_WORKTREE
    echo "Worktree created at $DECOMP_WORKTREE (based on origin/main)"

    # Build the prompt from template using envsubst
    DECOMP_PROMPT_TEMPLATE="$REPO_DIR/skills/reference-enrichment/decomposition-prompt.md"
    if [ ! -f "$DECOMP_PROMPT_TEMPLATE" ]; then
        echo "ERROR: decomposition-prompt.md not found at $DECOMP_PROMPT_TEMPLATE" >&2
        exit 1
    fi

    DECOMP_PROMPT=$(envsubst '${DECOMP_REPO_DIR} ${DECOMP_TARGETS} ${DECOMP_DATE} ${DECOMP_RUN_ID} ${DECOMP_MAX_TARGETS} ${DECOMP_DRY_RUN_MODE} ${DECOMP_WORKTREE}' < "$DECOMP_PROMPT_TEMPLATE")

    # Clean up local branches from merged/closed decomposition PRs
    for branch in $(git branch --list 'decomp/*' 2>/dev/null); do
        pr_state=$(gh pr list --head "$branch" --state all --json state --jq '.[0].state // "NONE"' 2>/dev/null)
        if [[ "$pr_state" == "MERGED" || "$pr_state" == "CLOSED" ]]; then
            echo "Cleaning up stale branch: $branch (PR state: $pr_state)"
            git branch -D "$branch" 2>/dev/null || true
        fi
    done

    cd "$DECOMP_WORKTREE"

    set +e
    claude -p "$DECOMP_PROMPT" \
        --output-format text \
        --dangerously-skip-permissions \
        --max-budget-usd "$MAX_BUDGET" \
        --no-session-persistence \
        --model claude-sonnet-4-7 \
        2>&1 | tee "$LOG_DIR/decomp-$(date +%Y%m%d-%H%M%S).log"
    EXIT_CODE=${PIPESTATUS[0]}
    set -e

    # Clean up temporary worktree
    echo "Cleaning up worktree..."
    cd "$REPO_DIR"
    git worktree remove "$DECOMP_WORKTREE" --force 2>/dev/null || true

    echo ""
    echo "=== Reference Decomposition complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "Decomposition completed successfully for: $DECOMP_TARGETS_TRIMMED"
    fi

    # Ensure we're back on main after decomposition (decomp/* branch may have been left active)
    cd "$REPO_DIR"
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [[ "$CURRENT_BRANCH" == decomp/* ]]; then
        echo "WARNING: Decomposition left repo on branch $CURRENT_BRANCH, switching back to main"
        git checkout main 2>/dev/null || true
    fi

    # Sync main checkout with remote after decomposition push
    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "Syncing main checkout with remote after decomposition push..."
        git fetch origin main
        git checkout -- . 2>/dev/null || true
        git clean -fd -- agents/*/references/ 2>/dev/null || true
        git clean -fd -- skills/*/references/ 2>/dev/null || true
        if ! git pull --ff-only 2>/dev/null; then
            echo "WARNING: fast-forward pull failed (main may have diverged). Manual sync needed."
        fi
        echo "Main checkout synced to $(git rev-parse --short HEAD)"
    fi

else
    # === ENRICHMENT MODE (--execute or dry-run) ===

    # Guard: check for too many open enrichment PRs (prevents accumulation — ADR consultation concern #2)
    MAX_OPEN_PRS="${MAX_OPEN_PRS:-5}"
    if command -v gh &>/dev/null; then
        OPEN_PRS=$(gh pr list --search "enrich/refs" --state open --json number 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
        if [ "$OPEN_PRS" -ge "$MAX_OPEN_PRS" ]; then
            echo "$(date -Iseconds) SKIP: ${OPEN_PRS} open enrichment PRs (max: ${MAX_OPEN_PRS}). Review/merge existing PRs first."
            exit 0
        fi
        echo "Open enrichment PRs: ${OPEN_PRS}/${MAX_OPEN_PRS}"
    fi

    # Run audit to find agents/skills below Level 3 (the goal is continuous
    # improvement toward Level 3, not just backfilling missing references)
    AUDIT_JSON=$(python3 "$REPO_DIR/scripts/audit-reference-depth.py" --json --min-level 3 2>/dev/null)

    # Select targets using the deterministic script (extracted per ADR consultation concern #4)
    TARGETS_TRIMMED=$(echo "$AUDIT_JSON" | python3 "$REPO_DIR/scripts/select-enrichment-targets.py" --max-targets "$MAX_TARGETS" --names-only)
    TARGETS_COUNT=$(echo "$TARGETS_TRIMMED" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

    if [ "$TARGETS_COUNT" -eq 0 ]; then
        echo "$(date -Iseconds) No gaps found (all components at Level 3). Exiting cleanly."
        exit 0
    fi

    echo "Audit found ${TARGETS_COUNT} gap(s). Processing up to ${MAX_TARGETS}: ${TARGETS_TRIMMED}"

    # Build envsubst variables
    export ENRICH_REPO_DIR="$REPO_DIR"
    export ENRICH_TARGETS="$TARGETS_TRIMMED"
    export ENRICH_DATE="$(date +%Y-%m-%d)"
    export ENRICH_RUN_ID="$(date +%Y-%m-%d-%H%M)"
    export ENRICH_MAX_TARGETS="$MAX_TARGETS"
    export ENRICH_DRY_RUN_MODE="no"
    if [ -z "$EXECUTE" ]; then
        export ENRICH_DRY_RUN_MODE="yes"
        echo "Dry-run mode: audit only, no reference files will be created"
    fi

    # Create temporary worktree for isolated enrichment work
    ENRICH_WORKTREE="/tmp/enrichment-worktree-${ENRICH_RUN_ID}"
    git worktree add "$ENRICH_WORKTREE" origin/main 2>/dev/null || {
        # If worktree already exists, remove and recreate
        git worktree remove "$ENRICH_WORKTREE" --force 2>/dev/null || true
        git worktree add "$ENRICH_WORKTREE" origin/main
    }
    export ENRICH_WORKTREE
    echo "Worktree created at $ENRICH_WORKTREE (based on origin/main)"

    # Build the prompt from template using envsubst
    PROMPT_TEMPLATE="$REPO_DIR/skills/reference-enrichment/enrichment-prompt.md"
    if [ ! -f "$PROMPT_TEMPLATE" ]; then
        echo "ERROR: enrichment-prompt.md not found at $PROMPT_TEMPLATE" >&2
        exit 1
    fi

    PROMPT=$(envsubst '${ENRICH_REPO_DIR} ${ENRICH_TARGETS} ${ENRICH_DATE} ${ENRICH_RUN_ID} ${ENRICH_MAX_TARGETS} ${ENRICH_DRY_RUN_MODE} ${ENRICH_WORKTREE}' < "$PROMPT_TEMPLATE")

    # Clean up local branches from merged/closed enrichment PRs
    for branch in $(git branch --list 'enrich/*' 2>/dev/null); do
        # Check if the branch's PR was merged or closed
        pr_state=$(gh pr list --head "$branch" --state all --json state --jq '.[0].state // "NONE"' 2>/dev/null)
        if [[ "$pr_state" == "MERGED" || "$pr_state" == "CLOSED" ]]; then
            echo "Cleaning up stale branch: $branch (PR state: $pr_state)"
            git branch -D "$branch" 2>/dev/null || true
        fi
    done

    cd "$ENRICH_WORKTREE"

    set +e
    claude -p "$PROMPT" \
        --output-format text \
        --dangerously-skip-permissions \
        --max-budget-usd "$MAX_BUDGET" \
        --no-session-persistence \
        --model claude-sonnet-4-7 \
        2>&1 | tee "$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"
    EXIT_CODE=${PIPESTATUS[0]}
    set -e

    # Clean up temporary worktree
    echo "Cleaning up worktree..."
    cd "$REPO_DIR"
    git worktree remove "$ENRICH_WORKTREE" --force 2>/dev/null || true

    echo ""
    echo "=== Reference Enrichment complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

    # Record completed targets in journal (only on success)
    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "Enrichment completed successfully for: $TARGETS_TRIMMED"
    fi

    # Ensure we're back on main after enrichment (enrich/* branch may have been left active)
    cd "$REPO_DIR"
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [[ "$CURRENT_BRANCH" == enrich/* ]]; then
        echo "WARNING: Enrichment left repo on branch $CURRENT_BRANCH, switching back to main"
        git checkout main 2>/dev/null || true
    fi

    # Sync main checkout with remote after enrichment push.
    # Interactive sessions create reference files locally but don't commit them (the
    # enrichment cron handles commit/push from its worktree). This leaves orphaned
    # local changes that conflict with future git pulls. Clean them up here.
    if [ "$EXIT_CODE" -eq 0 ] && [ -n "$EXECUTE" ]; then
        echo "Syncing main checkout with remote after enrichment push..."
        git fetch origin main
        # Drop tracked file modifications (stale enrichment leftovers from interactive sessions)
        git checkout -- . 2>/dev/null || true
        # Remove untracked reference files that enrichment creates — scoped narrowly to
        # avoid deleting legitimate local-only files (cron-logs/, plan/, benchmark/, adr/, etc.)
        git clean -fd -- agents/*/references/ 2>/dev/null || true
        git clean -fd -- skills/*/references/ 2>/dev/null || true
        # Fast-forward to include the just-merged changes
        if ! git pull --ff-only 2>/dev/null; then
            echo "WARNING: fast-forward pull failed (main may have diverged). Manual sync needed."
        fi
        echo "Main checkout synced to $(git rev-parse --short HEAD)"
    fi
fi

# Rotate old logs (keep last 30 days)
find "$LOG_DIR" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true
find "$LOG_DIR" -name "decomp-*.log" -mtime +30 -delete 2>/dev/null || true

# Lock is released by the EXIT trap (cleanup function)
exit $EXIT_CODE
