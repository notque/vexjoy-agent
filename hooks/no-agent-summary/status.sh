#!/bin/bash
# Is the agent_summary preload working? Prints, per Claude Code build the hook has seen, whether the
# binary still carries the anchors ("static") and whether a summary timer has been suppressed on
# it ("live"); then which running Claude Code processes carry the preload and which need a restart.
# A hooked process leaves $STATE/pids/<pid> while it runs (macOS hides other processes' env).
#
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 declanbx. Vendored from https://gist.github.com/declanbx/c4511b8642c9d7179ab5761ff6473871
STATE="${CC_AGENT_SUMMARY_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/no-agent-summary}"
echo "builds checked ($STATE):"
if ls "$STATE"/*.txt >/dev/null 2>&1; then
  for f in "$STATE"/*.txt; do
    exe=$(sed -n '1s/.*exe=//p' "$f")
    printf '  %-60s %s, %s\n' "$exe" "$(head -1 "$f" | cut -d' ' -f1-2)" \
      "$(grep -q '^live ' "$f" && grep '^live ' "$f" | head -1 | cut -d' ' -f1-3 || echo 'no suppression seen yet')"
  done
else
  echo "  none yet (the hook has not loaded in any Claude Code process)"
fi
for f in "$STATE"/pids/*; do                      # drop markers left by processes that crashed
  [ -e "$f" ] && ! kill -0 "$(basename "$f")" 2>/dev/null && rm -f "$f"
done
echo "session-start check (warns inside a session that is unprotected or on a broken build):"
for d in $(echo "${CLAUDE_CONFIG_DIR:-$HOME/.claude}${NAS_CLAUDE_CONFIG_DIRS:+:$NAS_CLAUDE_CONFIG_DIRS}" | tr ':' ' '); do
  f="$d/settings.json"
  if grep -q 'no-agent-summary' "$f" 2>/dev/null; then echo "  installed in $f"; else echo "  NOT installed in $f"; fi
done
echo "running Claude Code processes:"
for pid in $(ps -A -o pid=,args= | awk '{n=split($2,a,"/"); b=a[n]}
    b=="claude" || b=="claude.exe" || b==".claude-wrapped" || $2 ~ /\/claude\/versions\// {print $1}'); do
  if [ -e "$STATE/pids/$pid" ]; then tag="hooked"; else tag="NOT hooked (restart it)"; fi
  printf '  pid %-7s %-24s %s\n' "$pid" "$tag" "$(ps -o args= -p "$pid" | cut -c1-70)"
done
