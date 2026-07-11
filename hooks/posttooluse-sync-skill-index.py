#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PostToolUse Hook: Auto-sync INDEX.json on SKILL.md frontmatter changes

Triggered by Write|Edit events. Checks whether the written file is a
skills/**/SKILL.md. If yes, regenerates skills/INDEX.json by running
scripts/generate-skill-index.py. Silent on unrelated file writes.

INDEX.json is an untracked, generated artifact (ADR untrack-generated-indexes):
this hook only refreshes the local on-disk copy so routing stays current within
the session. It does NOT stage anything for commit — the index is gitignored.

Registration (add to ~/.claude/settings.json under hooks.PostToolUse):
    {
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "python3 \"$HOME/.claude/hooks/posttooluse-sync-skill-index.py\"",
        "description": "Regenerate INDEX.json when a SKILL.md is written",
        "timeout": 15000
      }]
    }

Design:
- Silent unless a SKILL.md was touched (zero cost for unrelated edits)
- Advisory: always exits 0 (never blocks Claude Code)
- Runs with a 15-second timeout budget (index gen completes in <2s for 100+ skills)
- Emits a one-line summary on success; full stderr on failure
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Matches skills/**/SKILL.md (flat and nested category layouts)
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")


def _project_root(event: dict) -> Path:
    """Resolve the repository targeted by the PostToolUse event."""
    candidate = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    return Path(candidate).resolve()


def _generator(project_root: Path) -> Path | None:
    """Find the generator in the hook install or target checkout."""
    hook_install_root = Path(__file__).resolve().parent.parent
    for candidate in (
        hook_install_root / "scripts" / "generate-skill-index.py",
        project_root / "scripts" / "generate-skill-index.py",
    ):
        if candidate.is_file():
            return candidate
    return None


def _refresh_manifest_cache() -> None:
    """Refresh the /do routing-manifest cache after an INDEX regen (C5).

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


def main() -> None:
    """Process PostToolUse hook event."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return

        event = json.loads(event_data)
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path:
            return

        # Only act on skills/**/SKILL.md files
        if not SKILL_FILE_RE.search(file_path):
            return

        project_root = _project_root(event)
        generator = _generator(project_root)

        if generator is None:
            print(
                "[sync-skill-index] generator not found in hook install or target project",
                file=sys.stderr,
            )
            return

        result = subprocess.run(
            [sys.executable, str(generator), "--repo-root", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=12,
        )

        if result.returncode == 0:
            # Emit a brief confirmation — model sees this as context
            skill_name = Path(file_path).parent.name
            print(f"[sync-skill-index] INDEX.json regenerated after {skill_name}/SKILL.md edit")
            _refresh_manifest_cache()
        else:
            print(
                f"[sync-skill-index] generator failed (exit {result.returncode})",
                file=sys.stderr,
            )
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines()[:10]:
                    print(f"  {line}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        print("[sync-skill-index] generator timed out after 12s", file=sys.stderr)
    except Exception as e:
        print(f"[sync-skill-index] hook error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
