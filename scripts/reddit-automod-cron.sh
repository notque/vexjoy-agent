#!/usr/bin/env bash
# Reddit auto-moderation via Claude Code headless mode.
# Designed for cron: fetches modqueue, classifies, auto-actions high-confidence items.
#
# Usage:
#   # Dry run (classify but don't act)
#   ./scripts/reddit-automod-cron.sh
#
#   # Live mode (execute mod actions)
#   ./scripts/reddit-automod-cron.sh --execute
#
# Cron example (twice daily at 8am and 8pm):
#   0 8,20 * * * /home/feedgen/claude-code-toolkit/scripts/reddit-automod-cron.sh --execute >> /home/feedgen/claude-code-toolkit/reddit-data/sap/cron-log/cron.log 2>&1

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:$PATH"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SUBREDDIT="${REDDIT_SUBREDDIT:-sap}"
LOG_DIR="$REPO_DIR/reddit-data/$SUBREDDIT/cron-log"
LOCKFILE="/tmp/reddit-automod-$SUBREDDIT.lock"
SINCE_MINUTES="${SINCE_MINUTES:-720}"
MAX_BUDGET="${MAX_BUDGET_USD:-2.00}"
EXECUTE=""

# Parse args
for arg in "$@"; do
    case "$arg" in
        --execute) EXECUTE="--execute" ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date -Iseconds) SKIP: another instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

TIMESTAMP="$(date -Iseconds)"
echo "=== Reddit automod run: $TIMESTAMP ==="

MODE="dry-run"
[ -n "$EXECUTE" ] && MODE="live"
echo "Mode: $MODE | Subreddit: r/$SUBREDDIT | Since: ${SINCE_MINUTES}m | Budget: \$${MAX_BUDGET}"

PROMPT="You are running automated Reddit moderation for r/$SUBREDDIT.

Step 1: Run this command to fetch and build classification prompts:
python3 scripts/reddit_mod.py queue --auto --since-minutes $SINCE_MINUTES --json | python3 scripts/reddit_mod.py classify

Step 2: If the queue is empty (count: 0), output 'Queue empty, no action needed.' and stop.

Step 3: For each item in the output, read the 'prompt' field and classify it as one of:
FALSE_REPORT, VALID_REPORT, MASS_REPORT_ABUSE, SPAM, BAN_RECOMMENDED, NEEDS_HUMAN_REVIEW

Assign confidence 0-100 and one-sentence reasoning.

Step 4: Apply actions for items meeting confidence thresholds:
- FALSE_REPORT/MASS_REPORT_ABUSE >= 95%: python3 scripts/reddit_mod.py approve --id {id}
- SPAM >= 90%: python3 scripts/reddit_mod.py remove --id {id} --reason '{reason}' --spam
- VALID_REPORT >= 90%: python3 scripts/reddit_mod.py remove --id {id} --reason '{reason}'
- BAN_RECOMMENDED: ALWAYS skip (never auto-ban)
- Below threshold: skip (leave for human review)

Step 5: Output a summary table of all items and actions taken.

IMPORTANT: When in doubt, SKIP. False negatives are better than false positives.
IMPORTANT: Never ban users. Never lock threads. These require human review."

cd "$REPO_DIR"

if [ -z "$EXECUTE" ]; then
    # Dry run: replace action commands with echo
    PROMPT="$PROMPT

DRY RUN MODE: Do NOT execute any approve/remove commands. Instead, show what you WOULD do for each item."
fi

claude -p "$PROMPT" \
    --output-format text \
    --dangerously-skip-permissions \
    --max-budget-usd "$MAX_BUDGET" \
    --no-session-persistence \
    2>&1 | tee "$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=== Run complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

# Release lock
exec 9>&-
rm -f "$LOCKFILE"

exit $EXIT_CODE
