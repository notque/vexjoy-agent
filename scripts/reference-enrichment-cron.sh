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
DAILY_BUDGET_CAP="${DAILY_BUDGET_CAP:-0}"
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
    echo "$(date -Iseconds) SKIP: another reference-enrichment instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

# Now that we hold the lock, register cleanup for any exit path
trap cleanup EXIT

TIMESTAMP="$(date -Iseconds)"
echo "=== Reference Enrichment run: $TIMESTAMP ==="

MODE="dry-run"
[ -n "$EXECUTE" ] && MODE="live"
DAILY_CAP_LABEL="\$${DAILY_BUDGET_CAP}"
[ "$DAILY_BUDGET_CAP" = "0" ] && DAILY_CAP_LABEL="unlimited"
echo "Mode: $MODE | Budget: \$${MAX_BUDGET} | Max targets: ${MAX_TARGETS} | Daily cap: ${DAILY_CAP_LABEL}"

# Daily budget guard: count today's runs and estimate spend
DAILY_SPEND_FILE="$LOG_DIR/.daily-runs-$(date +%Y%m%d)"
RUNS_TODAY=$(cat "$DAILY_SPEND_FILE" 2>/dev/null || echo "0")
ESTIMATED_DAILY_SPEND=$(echo "$RUNS_TODAY * $MAX_BUDGET" | bc 2>/dev/null || echo "0")
if [ "$DAILY_BUDGET_CAP" != "0" ] && [ "$(echo "$ESTIMATED_DAILY_SPEND >= $DAILY_BUDGET_CAP" | bc 2>/dev/null)" = "1" ]; then
    echo "$(date -Iseconds) SKIP: daily budget cap reached (\$${ESTIMATED_DAILY_SPEND}/\$${DAILY_BUDGET_CAP} after ${RUNS_TODAY} runs)"
    exit 0
fi
echo "Daily spend: \$${ESTIMATED_DAILY_SPEND}/${DAILY_CAP_LABEL} (${RUNS_TODAY} runs today)"

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

# Completion journal: skip targets already enriched today
COMPLETION_JOURNAL="$LOG_DIR/.completions-$(date +%Y%m%d)"
touch "$COMPLETION_JOURNAL"
TARGETS_TRIMMED=$(echo "$TARGETS_TRIMMED" | python3 -c "
import json, sys
targets = json.load(sys.stdin)
journal = set()
try:
    with open('$COMPLETION_JOURNAL') as f:
        journal = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    pass
filtered = [t for t in targets if t not in journal]
print(json.dumps(filtered))
")
TARGETS_COUNT=$(echo "$TARGETS_TRIMMED" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

if [ "$TARGETS_COUNT" -eq 0 ]; then
    echo "$(date -Iseconds) All targets already completed today (see $COMPLETION_JOURNAL). Exiting cleanly."
    exit 0
fi

echo "Audit found ${TARGETS_COUNT} gap(s). Processing up to ${MAX_TARGETS}: ${TARGETS_TRIMMED}"

# Build envsubst variables
export ENRICH_REPO_DIR="$REPO_DIR"
export ENRICH_TARGETS="$TARGETS_TRIMMED"
export ENRICH_DATE="$(date +%Y-%m-%d)"
export ENRICH_MAX_TARGETS="$MAX_TARGETS"
export ENRICH_DRY_RUN_MODE="no"
if [ -z "$EXECUTE" ]; then
    export ENRICH_DRY_RUN_MODE="yes"
    echo "Dry-run mode: audit only, no reference files will be created"
fi

# Build the prompt from template using envsubst
PROMPT_TEMPLATE="$REPO_DIR/skills/reference-enrichment/enrichment-prompt.md"
if [ ! -f "$PROMPT_TEMPLATE" ]; then
    echo "ERROR: enrichment-prompt.md not found at $PROMPT_TEMPLATE" >&2
    exit 1
fi

PROMPT=$(envsubst '${ENRICH_REPO_DIR} ${ENRICH_TARGETS} ${ENRICH_DATE} ${ENRICH_MAX_TARGETS} ${ENRICH_DRY_RUN_MODE}' < "$PROMPT_TEMPLATE")

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
echo "=== Reference Enrichment complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

# Record completed targets in journal (only on success)
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$TARGETS_TRIMMED" | python3 -c "
import json, sys
for name in json.load(sys.stdin):
    print(name)
" >> "$COMPLETION_JOURNAL"
fi

# Increment daily run counter
echo "$(( RUNS_TODAY + 1 ))" > "$DAILY_SPEND_FILE"

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
