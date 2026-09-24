#!/usr/bin/env bash
# Print the routing manifest: hash-gated disk cache when fresh, else regenerate.
#
# Cache inputs: the two generator scripts plus every INDEX file the manifest
# reads. Any byte change invalidates the hash and forces a regenerate.
# Missing optional files (INDEX.local.json, installed indexes) contribute
# nothing to the hash. Installed index dir (installer spec 7.2): $VEXJOY_INDEX_DIR,
# else <runtime>/vexjoy/index for a ~/.<runtime>/scripts dir, else
# ~/.claude/vexjoy/index. Keep in step with hooks/lib/manifest_cache.py.
#
# --request-file PATH: gate private (overlay) entries on the request text, as
# /d and pre-route.py do (routing_index_merge.gate_private_entries). When a
# private source exists (an installed index with an overlay owner, or a legacy
# INDEX.local.json), the generator runs with the request instead of the cache,
# since the cache holds every entry. With no private source, the cache serves.
set -u

REQUEST_FILE=""
if [ "${1:-}" = "--request-file" ] && [ -n "${2:-}" ]; then
  REQUEST_FILE="$2"
fi

SDIR="$(cd "$(dirname "$0")" && pwd)"
BASE="$(dirname "$SDIR")"
CACHE="${HOME}/.claude/cache/routing-manifest.txt"
CHASH="${HOME}/.claude/cache/routing-manifest.hash"
if [ -n "${VEXJOY_INDEX_DIR:-}" ]; then
  IDX="$VEXJOY_INDEX_DIR"
else
  case "$(basename "$BASE")" in
    .*) IDX="$BASE/vexjoy/index" ;;
    *) IDX="${HOME}/.claude/vexjoy/index" ;;
  esac
fi

if [ -n "$REQUEST_FILE" ] && {
  grep -qs '"overlay:' "$IDX/skills.json" "$IDX/agents.json" ||
    [ -e "$BASE/skills/INDEX.local.json" ] || [ -e "$BASE/agents/INDEX.local.json" ]
}; then
  python3 "$SDIR/routing-manifest.py" --request-file "$REQUEST_FILE"
elif [ -s "$CACHE" ] && [ -s "$CHASH" ] && [ "$(cat "$SDIR/routing-manifest.py" "$SDIR/routing_index_merge.py" "$BASE/skills/INDEX.json" "$BASE/skills/INDEX.local.json" "$BASE/agents/INDEX.json" "$BASE/agents/INDEX.local.json" "$BASE/skills/process/workflow/references/pipeline-index.json" "$IDX/skills.json" "$IDX/agents.json" 2>/dev/null | sha256sum | cut -d' ' -f1)" = "$(cat "$CHASH")" ]; then
  cat "$CACHE"    # cache hit: manifest read from disk, no Python start
else
  python3 "$SDIR/routing-manifest.py"
fi
