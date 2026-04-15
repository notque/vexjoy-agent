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
EXECUTE=""

# Cleanup function: release lock FD, remove stale worktree, and remove lockfile on any exit
cleanup() {
    if [ -n "${ENRICH_WORKTREE:-}" ] && [ -d "$ENRICH_WORKTREE" ]; then
        cd "$REPO_DIR" 2>/dev/null || true
        git worktree remove "$ENRICH_WORKTREE" --force 2>/dev/null || true
    fi
    exec 9>&- 2>/dev/null
    rm -f "$LOCKFILE"
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --execute) EXECUTE="1" ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

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
[ -n "$EXECUTE" ] && MODE="live"
echo "Mode: $MODE | Budget: \$${MAX_BUDGET} | Max targets: ${MAX_TARGETS}"

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

# Fetch latest remote main (safe: does not touch working tree)
echo "Fetching latest remote main..."
git fetch origin main
echo "Remote main at $(git rev-parse --short origin/main)"

# Prune stale worktrees left by prior crashes
git worktree prune 2>/dev/null || true

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
    --model sonnet \
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

# Rotate old logs (keep last 30 days)
find "$LOG_DIR" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true

# Lock is released by the EXIT trap (cleanup function)
exit $EXIT_CODE
