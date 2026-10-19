#!/usr/bin/env python3
# hook-version: 2.0.2
"""
PostToolUse Hook: refresh the installed skill index on SKILL.md edits

Triggered by Write|Edit events. When the written file is a skills/**/SKILL.md,
runs `python3 -m vexinstall sync --index-only --target <t>` for each installed
target (installer spec 7.3). The engine writes only
~/.<t>/vexjoy/index/skills.json. This hook never writes into a repo: the
gitignored repo dev index (skills/INDEX.json) is rebuilt only by an explicit
`python3 scripts/generate-skill-index.py`.


Registration (~/.claude/settings.json, hooks.PostToolUse, matcher Write|Edit):
    python3 "$HOME/.claude/hooks/posttooluse-sync-skill-index.py"   timeout 15000

Design:
- Silent unless a SKILL.md was touched (zero cost for unrelated edits)
- Advisory: always exits 0 (never blocks Claude Code)
- One-line summary on refresh; one stderr line per failed target
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

# Matches skills/**/SKILL.md (flat and nested category layouts)
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")


def _refresh_manifest_cache() -> None:
    """Refresh the /do routing-manifest cache after an index refresh (C5).

    Best-effort: the SessionStart hook re-checks next session, and /do
    Phase 2's hash check falls back to the generator on any mismatch.
    """
    try:
        from manifest_cache import refresh, resolve_scripts_dir

        sdir = resolve_scripts_dir()
        if sdir is not None:
            refresh(sdir)
    except Exception:
        pass


_BYPASS_ENV = "POSTTOOLUSE_SYNC_SKILL_INDEX_BYPASS"


def main() -> None:
    """Process PostToolUse hook event."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[posttooluse-sync-skill-index] Bypassed via POSTTOOLUSE_SYNC_SKILL_INDEX_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        from stdin_timeout import read_stdin

        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return
        event = json.loads(event_data)
        file_path = (event.get("tool_input") or {}).get("file_path", "")
        if not file_path or not SKILL_FILE_RE.search(file_path):
            return

        from installed_index import refresh_installed_indexes

        refreshed, errors = refresh_installed_indexes()
        if refreshed:
            skill_name = Path(file_path).parent.name
            print(
                f"[sync-skill-index] installed index refreshed ({', '.join(refreshed)}) after {skill_name}/SKILL.md edit"
            )
            _refresh_manifest_cache()
        for err in errors:
            print(f"[sync-skill-index] {err}", file=sys.stderr)
    except Exception as e:
        print(f"[sync-skill-index] hook error: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
