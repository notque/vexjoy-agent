#!/bin/sh
# Install the toolkit when a Claude cloud session starts without the hook launcher.
#
# Every toolkit hook runs through "$HOME/.claude/hooks/lib/pyrun.sh". A cloud session VM
# (CLAUDE_CODE_REMOTE=true, a fresh root home) never ran ./install.sh, so every hook exits
# 2 and blocks, and the repo's own sync hook runs through the same launcher, so it cannot
# repair this. This script runs from the checkout instead:
#
#   launcher present           -> exit at once
#   Claude cloud session       -> ./install.sh, then replay the repo's SessionStart hooks
#                                 (they ran in parallel with this one and failed) and
#                                 print their context as one SessionStart JSON object
#   local home, no launcher    -> one line saying to run ./install.sh; nothing touched
#
# It is repo-only: vexinstall never copies the entry into user settings. It never blocks:
# every path exits 0. Install output goes to ~/.claude/vexjoy/bootstrap.log.

[ -f "$HOME/.claude/hooks/lib/pyrun.sh" ] && exit 0
start=$(date +%s)

repo="${CLAUDE_PROJECT_DIR:-}"
[ -n "$repo" ] || repo=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)
[ -n "$repo" ] && [ -f "$repo/install.sh" ] || exit 0

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    echo "[session-bootstrap] the toolkit is not installed for $HOME, so its hooks fail; run ./install.sh in $repo, then restart"
    exit 0
fi

log_dir="$HOME/.claude/vexjoy"
mkdir -p "$log_dir" 2>/dev/null || exit 0
log="$log_dir/bootstrap.log"
payload="$log_dir/bootstrap-sessionstart.json"
if [ -t 0 ]; then : > "$payload"; else cat > "$payload" 2>/dev/null || : > "$payload"; fi

limit=""
command -v timeout >/dev/null 2>&1 && limit="timeout -k 10 200"
if $limit bash "$repo/install.sh" < /dev/null > "$log" 2>&1 && [ -f "$HOME/.claude/hooks/lib/pyrun.sh" ]; then
    if grep -q "⚠" "$log" 2>/dev/null; then
        status="[session-bootstrap] installed the toolkit into $HOME/.claude with warnings (log: $log)"
    else
        status="[session-bootstrap] installed the toolkit into $HOME/.claude (log: $log)"
    fi
    out=$(sh "$HOME/.claude/hooks/lib/pyrun.sh" "$repo/scripts/session-bootstrap-replay.py" \
        "$repo/.claude/settings.json" "$payload" "$status" "$((start + 232))" < /dev/null 2>>"$log")
    if [ -n "$out" ]; then
        printf '%s\n' "$out"
    else
        echo "$status"
    fi
else
    echo "[session-bootstrap] toolkit install failed; hooks stay broken until ./install.sh succeeds (log: $log)"
fi
exit 0
