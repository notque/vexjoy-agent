#!/usr/bin/env python3
"""
Stop Hook: Session Learning Gap Detector

Fires at session end to check whether the session recorded any learnings.
Prints a gap warning for substantive sessions with zero learnings, or a
summary count when learnings were captured.

Design Principles:
- Observability only, not enforcement
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- Silent on trivial sessions
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id
from learning_db_v2 import get_connection, init_db

EVENT_NAME = "Stop"

SUBSTANTIVE_TOOL_THRESHOLD = 5


def count_session_learnings(session_id: str) -> int:
    """Count learnings recorded for this session.

    Falls back to time-based query (last hour) if no session_id match.
    """
    init_db()

    with get_connection() as conn:
        # Primary: match by session_id
        row = conn.execute(
            "SELECT COUNT(*) FROM learnings WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        count = row[0] if row else 0

        if count > 0:
            return count

        # Fallback: learnings recorded in the last hour
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) FROM learnings WHERE last_seen >= ?",
            (cutoff,),
        ).fetchone()
        return row[0] if row else 0


def is_substantive_session(event: dict) -> bool:
    """Determine if the session was substantive enough to warrant a gap check."""
    session_data = event.get("session_data", {})

    # Check tool call count
    tool_uses = session_data.get("tool_uses", [])
    if len(tool_uses) > SUBSTANTIVE_TOOL_THRESHOLD:
        return True

    # Check if files were modified
    files_modified = session_data.get("files_modified", [])
    if len(files_modified) > 0:
        return True

    return False


def main():
    """Check learning gap at session end."""
    try:
        event_data = sys.stdin.read()
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()

        # Skip trivial sessions
        if not is_substantive_session(event):
            empty_output(EVENT_NAME).print_and_exit()

        learning_count = count_session_learnings(session_id)

        if learning_count == 0:
            print(
                "[learning-gap] Substantive session with 0 learnings recorded. Consider recording insights.",
                file=sys.stderr,
            )
        else:
            print(
                f"[learning-summary] Session recorded {learning_count} learnings",
                file=sys.stderr,
            )

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[session-learning-recorder] Error: {e}", file=sys.stderr)

    empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
