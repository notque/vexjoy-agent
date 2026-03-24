#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Stop Hook: Session Summary and Metrics

Generates a summary when the conversation ends and persists session metrics
to the unified learning database (learning_db_v2).

Design Principles:
- Comprehensive session tracking
- Persistent metrics storage
- Silent on empty sessions
- Non-blocking (always exits 0)
"""

import json
import os
import sys
import uuid
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from learning_db_v2 import get_stats, record_session
from stdin_timeout import read_stdin


def main():
    """Generate session summary on conversation end."""
    try:
        event_data = read_stdin(timeout=2)
        cwd = os.getcwd()

        # Generate session ID
        session_id = str(uuid.uuid4())[:8]

        if event_data:
            try:
                event = json.loads(event_data)
                # Extract metrics if available
                session_data = event.get("session_data", {})
                files_modified = len(session_data.get("files_modified", []))
                tools_used = len(session_data.get("tool_uses", []))
                errors = session_data.get("errors_encountered", 0)
                resolved = session_data.get("errors_resolved", 0)
            except (json.JSONDecodeError, KeyError):
                files_modified = 0
                tools_used = 0
                errors = 0
                resolved = 0
        else:
            files_modified = 0
            tools_used = 0
            errors = 0
            resolved = 0

        # Record session
        record_session(
            session_id,
            files_modified=files_modified,
            tools_used=tools_used,
            errors_encountered=errors,
            errors_resolved=resolved,
            project_path=cwd,
            end_session=True,
        )

        # Get stats
        stats = get_stats()

        total_learnings = stats.get("total_learnings", 0)
        high_conf = stats.get("high_confidence", 0)
        total_sessions = stats.get("sessions_tracked", 0)

        if total_learnings > 0 or total_sessions > 1:
            print("[session-summary] Session ended")
            print(f"[session-summary] Learning: {high_conf}/{total_learnings} high-confidence")
            print(f"[session-summary] Total sessions: {total_sessions}")

    except Exception as e:
        # Log to stderr if debug enabled, but never fail
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[session-summary] Error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
