#!/usr/bin/env bash
# Outcome eval: weekly task-outcome monitor via Claude Code headless mode.
# Runs one arm of the trajectory A/B smoke suite with deterministic scoring
# (hidden-test completion, hard safety gates, cost, wall time) and compares
# the result with the previous run.
#
# Job:         outcome-eval (weekly task-outcome monitor)
# Owner:       notque (crontab of user feedgen)
# Command:     /home/feedgen/vexjoy-agent/scripts/outcome-eval-cron.sh
#              which runs, at nice 10:
#              python3 scripts/trajectory-ab-test.py monitor --protocol <evals>/protocol.json
#                  --arm baseline --suite smoke --max-total-usd 16 --jobs 2 --out-dir <out>
# Working dir: /home/feedgen/vexjoy-agent (the checkout that holds this script)
# Env:         PATH gains $HOME/.local/bin for the claude CLI. Optional, all non-secret:
#              OUTCOME_EVAL_DIR      evals dir (default <repo>/evals/agent-trajectory-ab)
#              OUTCOME_EVAL_OUT_DIR  results and log dir (default ~/.claude/learning/outcome-eval)
#              OUTCOME_EVAL_ARM      baseline or challenger (default baseline)
#              OUTCOME_EVAL_JOBS     parallel trajectories, 1-4 (default 2)
#              MAX_TOTAL_USD         total budget cap in USD (default 16)
#              Claude credentials come from the user's own CLI login, never from this
#              script or its command line.
# Schedule:    weekly, outside 01:00-04:00 (the script refuses to start in that window).
# Log:         ~/.claude/learning/outcome-eval/cron.log (mode 600, appended)
# Results:     ~/.claude/learning/outcome-eval/monitor-<UTC stamp>.json (mode 600)
# Stop:        remove the crontab line (crontab -e). To stop a run in progress,
#              kill the process group of this script.
#
# Cron example (Wednesdays at 14:23):
#   23 14 * * 3 /home/feedgen/vexjoy-agent/scripts/outcome-eval-cron.sh
#
# Exit codes: 0 OK or skipped, 1 completion regressed or a hard gate failed,
# 2 error, 3 truncated by the budget cap.

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$PATH"

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER="$SCRIPT_DIR/trajectory-ab-test.py"
EVAL_DIR="${OUTCOME_EVAL_DIR:-$REPO_DIR/evals/agent-trajectory-ab}"
OUT_DIR="${OUTCOME_EVAL_OUT_DIR:-$HOME/.claude/learning/outcome-eval}"
ARM="${OUTCOME_EVAL_ARM:-baseline}"
JOBS="${OUTCOME_EVAL_JOBS:-2}"
MAX_TOTAL="${MAX_TOTAL_USD:-16}"
MAX_WORKERS=4

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
LOG_FILE="$OUT_DIR/cron.log"
LOCKFILE="$OUT_DIR/.outcome-eval.lock"
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"

# Everything below goes to the log; the crontab line needs no redirection.
exec >>"$LOG_FILE" 2>&1

skip() {
    echo "$(date -Iseconds) SKIP: $1"
    exit 0
}

case "$ARM" in
    baseline | challenger) ;;
    *) echo "$(date -Iseconds) ERROR: OUTCOME_EVAL_ARM must be baseline or challenger"; exit 2 ;;
esac
case "$JOBS" in
    '' | *[!0-9]*) echo "$(date -Iseconds) ERROR: OUTCOME_EVAL_JOBS must be a whole number"; exit 2 ;;
esac
JOBS=$((10#$JOBS))
[ "$JOBS" -lt 1 ] && JOBS=1
[ "$JOBS" -gt "$MAX_WORKERS" ] && JOBS="$MAX_WORKERS"

# Machine policy: no agent sims between 01:00 and 04:00 local time.
HOUR=$((10#$(date +%H)))
if [ "$HOUR" -ge 1 ] && [ "$HOUR" -lt 4 ]; then
    skip "inside the 01:00-04:00 quiet window; not starting"
fi

[ -f "$EVAL_DIR/protocol.json" ] || skip "evals dir or protocol.json is missing: $EVAL_DIR"
[ -f "$RUNNER" ] || skip "runner is missing: $RUNNER"
CLAUDE_BIN="$(command -v claude || true)"
[ -n "$CLAUDE_BIN" ] || skip "claude binary is not on PATH"
PYTHON_BIN="$(command -v python3 || true)"
[ -n "$PYTHON_BIN" ] || skip "python3 is not on PATH"

# Prevent concurrent runs
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    skip "another outcome-eval run holds the lock"
fi

cd "$REPO_DIR"
echo "=== Outcome eval run: $(date -Iseconds) ==="
echo "Arm: $ARM | Suite: smoke | Jobs: $JOBS | Budget cap: \$${MAX_TOTAL} | claude: $CLAUDE_BIN"

set +e
nice -n 10 "$PYTHON_BIN" "$RUNNER" monitor \
    --protocol "$EVAL_DIR/protocol.json" \
    --arm "$ARM" \
    --suite smoke \
    --max-total-usd "$MAX_TOTAL" \
    --jobs "$JOBS" \
    --out-dir "$OUT_DIR"
STATUS=$?
set -e

case "$STATUS" in
    0) echo "$(date -Iseconds) DONE: ok" ;;
    1) echo "$(date -Iseconds) DONE: REGRESSION (completion dropped or a hard gate failed)" ;;
    3) echo "$(date -Iseconds) DONE: TRUNCATED by the budget cap" ;;
    *) echo "$(date -Iseconds) DONE: ERROR (exit $STATUS)" ;;
esac
exit "$STATUS"
