#!/usr/bin/env python3
# hook-version: 1.0.0
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

from hook_utils import context_output, empty_output, get_tool_output, get_tool_result, hook_error
from learning_db_v2 import get_db_dir
from stdin_timeout import read_stdin

DB_PATH = get_db_dir() / "learning.db"
EVENT = "PostToolUse"

# Only categories the retro skill can graduate. Derived from the candidate
# query in skills/meta/retro/SKILL.md (Step 1):
#   learning-db.py query --category design --category gotcha
# Keep the two in sync — if the skill's query changes, change this tuple.
# Excluded on purpose: 'error' and 'effectiveness' are injection-only,
# 'voice' is corpus data; none can ever satisfy this gate.
GRADUATABLE_CATEGORIES = ("design", "gotcha")

# Verified = confirmed by an executed check at least once. success_count is
# incremented only by boost_confidence() (learning_db_v2.py), which fires when
# feedback tracking sees an injected solution succeed or after an explicit
# `learning-db.py boost` following a check. Recurrence alone can entrench a
# wrong guess (docs/PHILOSOPHY.md, "memory needs a verify step"); only
# verified rows are graduatable. Unverified rows are listed separately.
VERIFIED = "COALESCE(success_count, 0) >= 1"


def main() -> None:
    try:
        data = json.loads(read_stdin(timeout=2))
    except (json.JSONDecodeError, OSError):
        empty_output(EVENT).print_and_exit(0)
        return

    # tool_name/event_type filters removed — matcher "Bash" in settings.json
    # prevents this hook from spawning for non-Bash tools.

    # Early-exit: check if output indicates a PR was created (PostToolUse schema: tool_result.output)
    tool_result = get_tool_result(data)
    stdout = get_tool_output(tool_result) if isinstance(tool_result, dict) else ""
    if not isinstance(stdout, str) or "github.com" not in stdout or "pull/" not in stdout:
        empty_output(EVENT).print_and_exit(0)
        return

    # Check if we're in the toolkit repo (use project dir, not cwd)
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    has_skills = (project_dir / "skills").is_dir() or (project_dir / "pipelines").is_dir()
    if not (project_dir / "agents").is_dir() or not has_skills:
        empty_output(EVENT).print_and_exit(0)
        return

    # Check for ungraduated entries in learning.db
    if not DB_PATH.exists():
        empty_output(EVENT).print_and_exit(0)
        return

    verified = []
    unverified = []
    try:
        with sqlite3.connect(DB_PATH, timeout=2) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" * len(GRADUATABLE_CATEGORIES))
            rows = conn.execute(
                f"""
                SELECT topic, key, value, {VERIFIED} AS verified FROM learnings
                WHERE graduated_to IS NULL
                  AND confidence >= 0.7
                  AND last_seen >= datetime('now', '-24 hours')
                  AND category IN ({placeholders})
                ORDER BY confidence DESC
                LIMIT 20
                """,
                GRADUATABLE_CATEGORIES,
            ).fetchall()
            verified = [r for r in rows if r["verified"]]
            unverified = [r for r in rows if not r["verified"]]
    except sqlite3.Error as e:
        print(f"[retro-gate] DB error (advisory skip): {e}", file=sys.stderr)
        empty_output(EVENT).print_and_exit(0)
        return

    if not verified and not unverified:
        empty_output(EVENT).print_and_exit(0)
        return

    # Build advisory warning
    lines = []
    if verified:
        lines.append(f"[retro-gate] Found {len(verified)} ungraduated verified retro entries from this session.")
        lines.append("Before merging, graduate findings into the responsible agents/skills:")
        for row in verified:
            lines.append(f"  - {row['topic']}: {row['key']}")
        lines.append('Use: python3 ~/.claude/scripts/learning-db.py graduate TOPIC KEY "target-file.md"')
    if unverified:
        lines.append(
            f"[retro-gate] Not graduatable — needs verification ({len(unverified)} entries,"
            " no executed check has confirmed them yet):"
        )
        for row in unverified:
            lines.append(f"  - {row['topic']}: {row['key']}")
        lines.append(
            "Confirm each with an executed check, then: python3 ~/.claude/scripts/learning-db.py boost TOPIC KEY"
        )

    context_output(EVENT, "\n".join(lines)).print_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("retro-graduation-gate", e)
    finally:
        sys.exit(0)
