#!/usr/bin/env bash
# KB Compile: nightly knowledge base compilation + lint via Claude Code headless mode.
# Compiles all KB topics under research/ that have a kb.yaml config.
#
# Usage:
#   ./scripts/kb-compile-cron.sh           # Compile all topics
#   ./scripts/kb-compile-cron.sh --topic X # Compile specific topic
#
# Cron example (nightly at 3:37 AM, after toolkit-evolution at 3:07 AM):
#   37 3 * * * /home/feedgen/claude-code-toolkit/scripts/kb-compile-cron.sh >> /home/feedgen/claude-code-toolkit/cron-logs/kb-compile/cron.log 2>&1

# Ensure claude CLI is in PATH (cron doesn't inherit user PATH)
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/$(ls $HOME/.nvm/versions/node/ 2>/dev/null | tail -1)/bin:$PATH"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/cron-logs/kb-compile"
LOCKFILE="/tmp/kb-compile.lock"
MAX_BUDGET="${MAX_BUDGET_USD:-3.00}"
SPECIFIC_TOPIC=""

# Cleanup function: release lock FD and remove lockfile on any exit
cleanup() {
    exec 9>&- 2>/dev/null
    rm -f "$LOCKFILE"
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --topic)
            shift
            SPECIFIC_TOPIC="${1:-}"
            shift
            ;;
        --topic=*)
            SPECIFIC_TOPIC="${arg#--topic=}"
            ;;
        *)
            echo "Unknown arg: $arg" >&2
            echo "Usage: $0 [--topic TOPIC]" >&2
            exit 1
            ;;
    esac
done

# Create log directory
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date -Iseconds) SKIP: another kb-compile instance is running" >> "$LOG_DIR/cron.log"
    exit 0
fi

# Now that we hold the lock, register cleanup for any exit path
trap cleanup EXIT

TIMESTAMP="$(date -Iseconds)"
echo "=== KB Compile run: $TIMESTAMP ==="

# Discover topics from research/*/kb.yaml
if [ -n "$SPECIFIC_TOPIC" ]; then
    KB_YAML="$REPO_DIR/research/$SPECIFIC_TOPIC/kb.yaml"
    if [ ! -f "$KB_YAML" ]; then
        echo "ERROR: No kb.yaml found for topic '$SPECIFIC_TOPIC' at $KB_YAML" >&2
        exit 1
    fi
    TOPICS=("$SPECIFIC_TOPIC")
else
    TOPICS=()
    while IFS= read -r -d '' yaml_file; do
        topic_dir="$(dirname "$yaml_file")"
        topic_name="$(basename "$topic_dir")"
        TOPICS+=("$topic_name")
    done < <(find "$REPO_DIR/research" -maxdepth 2 -name "kb.yaml" -print0 2>/dev/null | sort -z)
fi

if [ "${#TOPICS[@]}" -eq 0 ]; then
    echo "No KB topics found (no research/*/kb.yaml). Nothing to compile."
    exit 0
fi

TOPIC_LIST="$(printf '%s\n' "${TOPICS[@]}")"
echo "Topics: ${TOPICS[*]} | Budget: \$${MAX_BUDGET}"

# Build the prompt
PROMPT="You are running the nightly KB compile cycle.

For each topic, execute the kb-compile skill at skills/kb-compile/SKILL.md.
Run all 4 phases: SCAN → COMPILE → INDEX → VERIFY.

Topics to compile:
${TOPIC_LIST}

Budget cap: \$${MAX_BUDGET}"

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
echo "=== KB Compile complete: $(date -Iseconds) | exit: $EXIT_CODE ==="

# Ensure we're back on main after compile (skill may have switched branches)
cd "$REPO_DIR"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "WARNING: Compile left repo on branch $CURRENT_BRANCH, switching back to main"
    git checkout main 2>/dev/null || true
fi

# Rotate old logs (keep last 30 days)
find "$LOG_DIR" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
