#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse Hook: Block git commit/push when SKILL.md staged without INDEX.json.

Fires on Bash tool calls containing 'git commit' or 'git push'.
Checks whether any skills/**/SKILL.md files are staged. If yes, requires
skills/INDEX.json to also be staged. Blocks with exit code 2 when mismatch found.

This prevents the broken-state pattern where a SKILL.md edit triggers
posttooluse-sync-skill-index.py to regenerate INDEX.json, but the
regenerated INDEX.json is never staged before commit.

Registration (add to .claude/settings.json under hooks.PreToolUse):
    {
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "python3 \"$HOME/.claude/hooks/pretool-index-sync-check.py\"",
        "description": "Block git commit/push when SKILL.md staged without INDEX.json sync",
        "timeout": 5000
      }]
    }
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

GIT_COMMIT_RE = re.compile(r"\bgit\s+(commit|push)\b")
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")
INDEX_PATH = "skills/INDEX.json"


def get_staged_files(cwd: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=5,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    try:
        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            sys.exit(0)

        event = json.loads(event_data)
        tool_name = event.get("tool_name", "")
        if tool_name != "Bash":
            sys.exit(0)

        command = event.get("tool_input", {}).get("command", "")
        if not GIT_COMMIT_RE.search(command):
            sys.exit(0)

        cwd = str(Path(__file__).parent.parent)
        staged = get_staged_files(cwd)
        if not staged:
            sys.exit(0)

        skill_md_staged = [f for f in staged if SKILL_FILE_RE.search(f)]
        if not skill_md_staged:
            sys.exit(0)

        index_staged = INDEX_PATH in staged
        if index_staged:
            sys.exit(0)

        names = [Path(f).parent.name for f in skill_md_staged]
        print(
            f"[index-sync-check] BLOCKED: {len(skill_md_staged)} SKILL.md file(s) staged "
            f"({', '.join(names)}) but skills/INDEX.json is not staged.\n"
            f"  Run: python3 scripts/generate-skill-index.py && git add skills/INDEX.json\n"
            f"  Then re-run your commit.",
            file=sys.stderr,
        )
        sys.exit(2)

    except subprocess.TimeoutExpired:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
