#!/usr/bin/env bash
# Auto-Dream: nightly memory consolidation via Claude Code headless mode.
# Scans memory files, deduplicates, archives stale entries, synthesizes
# cross-session patterns, and builds injection-ready payloads.
#
# Usage:
#   # Dry run (read-only, no filesystem changes)
#   ./scripts/auto-dream-cron.sh
#
#   # Full run (execute consolidation)
#   ./scripts/auto-dream-cron.sh --execute
#
# Cron example (nightly at 2:07 AM):
#   7 2 * * * /home/feedgen/claude-code-toolkit/scripts/auto-dream-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/auto-dream/cron.log 2>&1

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:$PATH"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/cron-logs/auto-dream"
LOCKFILE="/tmp/auto-dream.lock"
MAX_BUDGET="${MAX_BUDGET_USD:-3.00}"
EXECUTE=""

# Cleanup function: release lock FD and remove lockfile on any exit
cleanup() {
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
    echo "$(date -Iseconds) SKIP: another dream instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

# Now that we hold the lock, register cleanup for any exit path
trap cleanup EXIT

TIMESTAMP="$(date -Iseconds)"
echo "=== Auto-Dream run: $TIMESTAMP ==="

MODE="dry-run"
[ -n "$EXECUTE" ] && MODE="live"
echo "Mode: $MODE | Budget: \$${MAX_BUDGET}"

# Derive project-specific paths for the dream prompt template
# These get substituted into dream-prompt.md via envsubst
PROJECT_PATH="$REPO_DIR"
PROJECT_HASH=$(echo "$PROJECT_PATH" | sed 's|/|-|g' | sed 's|^-||')

export DREAM_MEMORY_DIR="$HOME/.claude/projects/-${PROJECT_HASH}/memory"
export DREAM_LEARNING_DB="$HOME/.claude/learning/learning.db"
export DREAM_STATE_DIR="$HOME/.claude/state"
export DREAM_REPO_DIR="$PROJECT_PATH"
export DREAM_PROJECT_HASH="$PROJECT_HASH"

# Ensure state directory exists
mkdir -p "$DREAM_STATE_DIR"

# Build the prompt from template using envsubst
PROMPT_TEMPLATE="$REPO_DIR/skills/auto-dream/dream-prompt.md"
if [ ! -f "$PROMPT_TEMPLATE" ]; then
    echo "ERROR: dream-prompt.md not found at $PROMPT_TEMPLATE" >&2
    exit 1
fi

# Set dry-run mode variables before envsubst so ${DREAM_DRY_RUN_MODE} is substituted correctly
export DREAM_DRY_RUN_MODE="no"
if [ -z "$EXECUTE" ]; then
    export DREAM_DRY_RUN_MODE="yes"
    echo "Dry-run mode: CONSOLIDATE and SYNTHESIZE will describe but not execute changes"
fi

PROMPT=$(envsubst '${DREAM_MEMORY_DIR} ${DREAM_LEARNING_DB} ${DREAM_STATE_DIR} ${DREAM_REPO_DIR} ${DREAM_PROJECT_HASH} ${DREAM_DRY_RUN_MODE}' < "$PROMPT_TEMPLATE")

cd "$REPO_DIR"

set +e
claude -p "$PROMPT" \
    --output-format text \
    --permission-mode auto \
    --allowedTools "Bash Read Write Edit Glob Grep" \
    --max-budget-usd "$MAX_BUDGET" \
    --no-session-persistence \
    --model sonnet \
    2>&1 | tee "$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"
EXIT_CODE=${PIPESTATUS[0]}
set -e

echo ""
echo "=== Dream complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

# Rotate old logs and state files (keep last 30 days)
find "$LOG_DIR" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true
find "$DREAM_STATE_DIR" -name "dream-scan-*.md" -mtime +30 -delete 2>/dev/null || true
find "$DREAM_STATE_DIR" -name "dream-analysis-*.md" -mtime +30 -delete 2>/dev/null || true

# Lock is released by the EXIT trap (cleanup function)
exit $EXIT_CODE
