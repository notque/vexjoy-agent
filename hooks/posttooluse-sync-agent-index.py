#!/usr/bin/env python3
# hook-version: 2.0.0
"""
PostToolUse Hook: refresh the installed agent index on agent-file edits.

Mirror of posttooluse-sync-skill-index.py for agents/*.md. On Write|Edit of an
agent markdown file, runs `python3 -m vexinstall sync --index-only --target <t>`
for each installed target (installer spec 7.3); the engine writes only
~/.<t>/vexjoy/index/agents.json. This hook never writes into a repo: the
gitignored agents/INDEX.json is rebuilt only by an explicit
`python3 scripts/generate-agent-index.py`. Advisory: always exits 0.

Registration (~/.claude/settings.json PostToolUse Write|Edit group, after the
skill-index hook and before posttool-docs-drift-alert.py):
    python3 "$HOME/.claude/hooks/posttooluse-sync-agent-index.py"   timeout 15000
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

# agents/<name>.md, flat layout (exactly one segment after agents/).
AGENT_FILE_RE = re.compile(r"(?:^|/)agents/[^/]+\.md$")
_EXCLUDE = {"INDEX.md", "README.md"}


def _refresh_manifest_cache() -> None:
    """Refresh the /do routing-manifest cache after an index refresh (C5)."""
    try:
        from manifest_cache import refresh, resolve_scripts_dir

        sdir = resolve_scripts_dir()
        if sdir is not None:
            refresh(sdir)
    except Exception:
        pass


def is_agent_file(file_path: str) -> bool:
    """True when file_path is a flat agents/*.md (excluding INDEX.md/README.md)."""
    if not file_path or not AGENT_FILE_RE.search(file_path):
        return False
    return Path(file_path).name not in _EXCLUDE


def main() -> None:
    """Process PostToolUse hook event."""
    try:
        from stdin_timeout import read_stdin

        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return
        event = json.loads(event_data)
        file_path = (event.get("tool_input") or {}).get("file_path", "")
        if not is_agent_file(file_path):
            return

        from installed_index import refresh_installed_indexes

        refreshed, errors = refresh_installed_indexes()
        if refreshed:
            print(
                f"[sync-agent-index] installed index refreshed ({', '.join(refreshed)}) after {Path(file_path).name} edit"
            )
            _refresh_manifest_cache()
        for err in errors:
            print(f"[sync-agent-index] {err}", file=sys.stderr)
    except Exception as e:
        print(f"[sync-agent-index] hook error: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
