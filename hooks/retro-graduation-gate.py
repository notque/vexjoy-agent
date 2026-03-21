#!/usr/bin/env python3
"""
PostToolUse Hook: Retro Graduation Gate (ADR-010)

After `gh pr create`, checks for ungraduated retro entries. If in the toolkit
repo (agents/ + skills/ present), warns that graduation should happen before merge.
Advisory only — does not block. Early-exit for non-Bash/<1ms. Sub-50ms execution.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output

DB_PATH = Path.home() / ".claude" / "learning" / "learning.db"
EVENT = "PostToolUse"


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        empty_output(EVENT).print_and_exit(0)
        return

    # Event type guard (defensive — matches peer hook pattern)
    event_type = data.get("hook_event_name") or data.get("type", "")
    if event_type and event_type != EVENT:
        empty_output(EVENT).print_and_exit(0)
        return

    # Early-exit: only care about Bash tool (PostToolUse schema: tool_name)
    if data.get("tool_name") != "Bash":
        empty_output(EVENT).print_and_exit(0)
        return

    # Early-exit: check if output indicates a PR was created (PostToolUse schema: tool_result.output)
    tool_result = data.get("tool_result", {})
    stdout = tool_result.get("output", "") if isinstance(tool_result, dict) else ""
    if not isinstance(stdout, str) or "github.com" not in stdout or "pull/" not in stdout:
        empty_output(EVENT).print_and_exit(0)
        return

    # Check if we're in the toolkit repo (use project dir, not cwd)
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    if not (project_dir / "agents").is_dir() or not (project_dir / "skills").is_dir():
        empty_output(EVENT).print_and_exit(0)
        return

    # Check for ungraduated entries in learning.db
    if not DB_PATH.exists():
        empty_output(EVENT).print_and_exit(0)
        return

    rows = []
    try:
        with sqlite3.connect(DB_PATH, timeout=2) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT topic, key, value FROM learnings
                WHERE graduated_to IS NULL
                  AND confidence >= 0.7
                  AND last_seen >= datetime('now', '-24 hours')
                ORDER BY confidence DESC
                LIMIT 20
                """,
            ).fetchall()
    except sqlite3.Error as e:
        print(f"[retro-gate] DB error (advisory skip): {e}", file=sys.stderr)
        empty_output(EVENT).print_and_exit(0)
        return

    if not rows:
        empty_output(EVENT).print_and_exit(0)
        return

    # Build advisory warning
    lines = [f"[retro-gate] Found {len(rows)} ungraduated retro entries from this session."]
    lines.append("Before merging, graduate findings into the responsible agents/skills:")
    for row in rows:
        lines.append(f"  - {row['topic']}: {row['key']}")
    lines.append('Use: python3 scripts/learning-db.py graduate TOPIC KEY "target-file.md"')

    context_output(EVENT, "\n".join(lines)).print_and_exit(0)


if __name__ == "__main__":
    main()
