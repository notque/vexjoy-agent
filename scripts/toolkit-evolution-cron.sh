#!/usr/bin/env bash
# Toolkit Evolution: nightly self-improvement cycle via Claude Code headless mode.
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
# Cron example (nightly at 3:07 AM, after auto-dream at 2:07 AM):
#   7 3 * * * /home/feedgen/claude-code-toolkit/scripts/toolkit-evolution-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/toolkit-evolution/cron.log 2>&1

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

# Preflight: verify GitHub auth is functional before running the full cycle.
# This check runs early so failures are diagnosed at start, not discovered at Phase 6.
# The cycle still runs without valid auth -- Phase 6 will skip PR creation.
GH_AUTH_VALID=""
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GH_AUTH_VALID="1"
    echo "GitHub auth: OK (Phase 6 PR creation enabled)"
else
    echo "WARNING: GitHub auth not available -- Phase 6 PR creation will be skipped"
    echo "  Fix: ensure GH_TOKEN is set with repo scope, or run: gh auth login"
    echo "  Branch will be left on remote for manual PR creation after cycle completes"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/cron-logs/toolkit-evolution"
LOCKFILE="/tmp/toolkit-evolution.lock"
MAX_BUDGET="${MAX_BUDGET_USD:-15.00}"
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
PROMPT="You are running the nightly toolkit evolution cycle for the claude-code-toolkit.

Read and execute the skill at skills/toolkit-evolution/SKILL.md — it defines the full 6-phase pipeline:
DIAGNOSE → PROPOSE → CRITIQUE → BUILD → VALIDATE → EVOLVE

Key constraints:
- Budget cap: \$${MAX_BUDGET} for this entire cycle
- Maximum 3 implementations per cycle (focus over breadth)
- Winners that pass critique (STRONG consensus) AND A/B testing (WIN) should be merged via PR
- Record all outcomes (wins AND losses) to the learning DB
- Write evolution report to evolution-reports/evolution-report-$(date +%Y-%m-%d).md
- Index generation: if the cycle regenerates skills/INDEX.json or agents/INDEX.json, run
  the generators in default mode only. Do not pass --include-private. Do not modify
  routing-tables.md to add entries for symlinked skill directories."

if [ -z "$GH_AUTH_VALID" ]; then
    PROMPT="$PROMPT

GITHUB AUTH: GitHub CLI authentication is NOT available in this session. In Phase 6, skip the 'gh pr create' step. Instead, push the branch to origin and record its name in the evolution report so it can be manually reviewed. Do NOT mark the cycle as failed -- record it as 'PR pending: branch pushed, needs manual creation'."
fi

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

# Rotate old logs (keep last 30 days)
find "$LOG_DIR" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
