#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Auto-sync INDEX.json on SKILL.md frontmatter changes

Triggered by Write|Edit events. Checks whether the written file is a
skills/**/SKILL.md. If yes, regenerates skills/INDEX.json by running
scripts/generate-skill-index.py. Silent on unrelated file writes.

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
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Matches skills/**/SKILL.md (flat and nested category layouts)
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")


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

        # Resolve repo root: hooks/ is one level below repo root
        hook_dir = Path(__file__).resolve().parent
        repo_root = hook_dir.parent
        generator = repo_root / "scripts" / "generate-skill-index.py"

        if not generator.exists():
            print(
                f"[sync-skill-index] generator not found: {generator}",
                file=sys.stderr,
            )
            return

        result = subprocess.run(
            [sys.executable, str(generator)],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=12,
        )

        if result.returncode == 0:
            # Emit a brief confirmation — model sees this as context
            skill_name = Path(file_path).parent.name
            print(f"[sync-skill-index] INDEX.json regenerated after {skill_name}/SKILL.md edit")
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
