#!/usr/bin/env bash
# Toolkit Evolution: weekly self-improvement cycle via Claude Code headless mode.
# Diagnoses improvement opportunities, proposes solutions, critiques them via
# multi-persona review, builds winners, A/B tests, and creates PRs for review.
#
# Usage:
#   # Dry run (diagnose + propose only, no builds)
#   ./scripts/toolkit-evolution-cron.sh
#
#   # Full run (execute full evolution cycle)
#   ./scripts/toolkit-evolution-cron.sh --execute
#
# Cron example (weekly Sunday at 3:07 AM):
#   7 3 * * 0 /home/feedgen/claude-code-toolkit/scripts/toolkit-evolution-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/toolkit-evolution/cron.log 2>&1

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:$PATH"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/cron-logs/toolkit-evolution"
LOCKFILE="/tmp/toolkit-evolution.lock"
MAX_BUDGET="${MAX_BUDGET_USD:-5.00}"
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
    echo "$(date -Iseconds) SKIP: another evolution instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

# Now that we hold the lock, register cleanup for any exit path
trap cleanup EXIT

TIMESTAMP="$(date -Iseconds)"
echo "=== Toolkit Evolution run: $TIMESTAMP ==="

MODE="dry-run"
[ -n "$EXECUTE" ] && MODE="live"
echo "Mode: $MODE | Budget: \$${MAX_BUDGET}"

# Build the prompt
PROMPT="You are running the weekly toolkit evolution cycle for the claude-code-toolkit.

Read and execute the skill at skills/toolkit-evolution/SKILL.md — it defines the full 6-phase pipeline:
DIAGNOSE → PROPOSE → CRITIQUE → BUILD → VALIDATE → EVOLVE

Key constraints:
- Budget cap: \$${MAX_BUDGET} for this entire cycle
- Maximum 3 implementations per cycle (focus over breadth)
- Never auto-merge to main — create PRs for human review
- Record all outcomes (wins AND losses) to the learning DB
- Write evolution report to ~/.claude/state/evolution-report-$(date +%Y-%m-%d).md"

if [ -z "$EXECUTE" ]; then
    PROMPT="$PROMPT

DRY RUN MODE: Execute only DIAGNOSE and PROPOSE phases. Do NOT build, test, or create PRs. Output what you WOULD do."
fi

cd "$REPO_DIR"

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

echo ""
echo "=== Evolution complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

# Ensure we're back on main after evolution (build phase may have switched branches)
cd "$REPO_DIR"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != feat/toolkit-evolution-cron ]]; then
    echo "WARNING: Evolution left repo on branch $CURRENT_BRANCH, switching back to main"
    git checkout main 2>/dev/null || true
fi

# Rotate old logs (keep last 90 days — weekly cadence means fewer logs)
find "$LOG_DIR" -name "run-*.log" -mtime +90 -delete 2>/dev/null || true

exit $EXIT_CODE
