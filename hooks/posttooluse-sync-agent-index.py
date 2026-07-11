#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PostToolUse Hook: Auto-sync agents/INDEX.json on agent-file changes.

Mirror of posttooluse-sync-skill-index.py for agents/*.md. On Write|Edit of an
agent markdown file, regenerates agents/INDEX.json via scripts/generate-agent-index.py.
Silent and fast on unrelated writes. agents/INDEX.json is gitignored (.gitignore);
this only refreshes the local copy so /do routing stays current within the session.
Advisory: always exits 0.

Registration (add to ~/.claude/settings.json PostToolUse Write|Edit group, after
the skill-index hook and before posttool-docs-drift-alert.py so the drift alert's
count check reads a fresh index):
    {
      "type": "command",
      "command": "python3 \"$HOME/.claude/hooks/posttooluse-sync-agent-index.py\"",
      "description": "Auto-regenerate agents/INDEX.json when an agent .md is written or edited",
      "timeout": 15000
    }
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# agents/<name>.md, flat layout (exactly one segment after agents/).
AGENT_FILE_RE = re.compile(r"(?:^|/)agents/[^/]+\.md$")
_EXCLUDE = {"INDEX.md", "README.md"}


def _project_root(event: dict) -> Path:
    """Resolve the repository targeted by the PostToolUse event."""
    candidate = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    return Path(candidate).resolve()


def _generator(project_root: Path) -> Path | None:
    """Find the generator in the hook install or target checkout."""
    hook_install_root = Path(__file__).resolve().parent.parent
    for candidate in (
        hook_install_root / "scripts" / "generate-agent-index.py",
        project_root / "scripts" / "generate-agent-index.py",
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


def is_agent_file(file_path: str) -> bool:
    """True when file_path is a flat agents/*.md (excluding INDEX.md/README.md)."""
    if not file_path or not AGENT_FILE_RE.search(file_path):
        return False
    return Path(file_path).name not in _EXCLUDE


def main() -> None:
    """Process PostToolUse hook event."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return

        event = json.loads(event_data)
        file_path = event.get("tool_input", {}).get("file_path", "")
        if not is_agent_file(file_path):
            return

        project_root = _project_root(event)
        generator = _generator(project_root)
        if generator is None:
            print("[sync-agent-index] generator not found in hook install or target project", file=sys.stderr)
            return

        result = subprocess.run(
            [sys.executable, str(generator), "--repo-root", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=12,
        )

        if result.returncode == 0:
            print(f"[sync-agent-index] INDEX.json regenerated after {Path(file_path).name} edit")
            _refresh_manifest_cache()
        else:
            print(f"[sync-agent-index] generator failed (exit {result.returncode})", file=sys.stderr)
            for line in result.stderr.strip().splitlines()[:10]:
                print(f"  {line}", file=sys.stderr)

    except subprocess.TimeoutExpired:
        print("[sync-agent-index] generator timed out after 12s", file=sys.stderr)
    except Exception as e:
        print(f"[sync-agent-index] hook error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
