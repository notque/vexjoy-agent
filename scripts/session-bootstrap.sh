#!/bin/sh
# Install the toolkit into this $HOME when a repo session starts without one.
#
# Every toolkit hook runs through "$HOME/.claude/hooks/lib/pyrun.sh". A home
# that never ran ./install.sh (a cloud session container, a new user) or one
# installed before pyrun.sh existed has no launcher, so every hook exits 2 and
# blocks. The repo's own SessionStart sync hook runs through the same launcher,
# so it cannot repair this. This script runs from the checkout instead.
#
# It is repo-only: its path is outside hooks/, so vexinstall never copies the
# entry into user settings. It never blocks: every path exits 0. Install
# output goes to ~/.claude/vexjoy/bootstrap.log; stdout gets one line.

[ -f "$HOME/.claude/hooks/lib/pyrun.sh" ] && exit 0

repo="${CLAUDE_PROJECT_DIR:-}"
[ -n "$repo" ] || repo=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)
[ -n "$repo" ] && [ -f "$repo/install.sh" ] || exit 0

log_dir="$HOME/.claude/vexjoy"
mkdir -p "$log_dir" 2>/dev/null || exit 0
log="$log_dir/bootstrap.log"

if bash "$repo/install.sh" > "$log" 2>&1 && [ -f "$HOME/.claude/hooks/lib/pyrun.sh" ]; then
    echo "[session-bootstrap] installed the toolkit into $HOME/.claude (log: $log)"
else
    echo "[session-bootstrap] toolkit install failed; hooks stay broken until ./install.sh succeeds (log: $log)"
fi
exit 0
