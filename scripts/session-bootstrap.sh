#!/bin/sh
# Install the toolkit into this $HOME when a repo session starts without the hook launcher.
#
# Every toolkit hook runs through "$HOME/.claude/hooks/lib/pyrun.sh". A home without it
# makes every hook exit 2 and block, and the repo's own sync hook runs through the same
# launcher, so it cannot repair this. This script runs from the checkout instead:
#
#   launcher present             -> exit at once
#   Claude cloud session         -> ./install.sh (CLAUDE_CODE_REMOTE=true: a fresh VM home)
#   local home with an install   -> ./install.sh (ledger.json: the user already installed;
#                                   repairs an install older than the launcher)
#   local home, never installed  -> one line saying to run ./install.sh; ~/.claude untouched
#
# It is repo-only: vexinstall never copies the entry into user settings. It never blocks:
# every path exits 0. Install output goes to ~/.claude/vexjoy/bootstrap.log; stdout gets
# one line, which Claude sees as session context.

[ -f "$HOME/.claude/hooks/lib/pyrun.sh" ] && exit 0

repo="${CLAUDE_PROJECT_DIR:-}"
[ -n "$repo" ] || repo=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)
[ -n "$repo" ] && [ -f "$repo/install.sh" ] || exit 0

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && [ ! -f "$HOME/.claude/vexjoy/ledger.json" ]; then
    echo "[session-bootstrap] the toolkit is not installed for $HOME, so its hooks fail; run ./install.sh in $repo, then restart"
    exit 0
fi

log_dir="$HOME/.claude/vexjoy"
mkdir -p "$log_dir" 2>/dev/null || exit 0
log="$log_dir/bootstrap.log"

if bash "$repo/install.sh" > "$log" 2>&1 && [ -f "$HOME/.claude/hooks/lib/pyrun.sh" ]; then
    echo "[session-bootstrap] installed the toolkit into $HOME/.claude (log: $log)"
else
    echo "[session-bootstrap] toolkit install failed; hooks stay broken until ./install.sh succeeds (log: $log)"
fi
exit 0
