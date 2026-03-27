#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse Hook: Session Read Tracker

Tracks files read during the session by appending file paths to
.claude/session-reads.txt. This provides a lightweight record of
files the parent session has seen, used by the warmstart hook to
give subagents context about what's already been read.

Design Principles:
- SILENT output (no context injection)
- Non-blocking (always exits 0)
- Fast execution (<10ms target)
- Only processes Read tool results
- Deduplicates paths within the session file
"""

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output
from stdin_timeout import read_stdin

EVENT_NAME = "PostToolUse"

SESSION_READS_FILE = ".claude/session-reads.txt"


def main() -> None:
    """Process PostToolUse events for Read tool file tracking.

    Flow:
    1. Read stdin JSON, check tool_name == "Read"
    2. Extract file_path from tool_input
    3. Append to .claude/session-reads.txt (deduplicated)
    4. Exit silently (no context injection)
    """
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # tool_name filter removed — matcher "Read" in settings.json prevents
        # this hook from spawning for non-Read tools.

        # Extract file_path from tool_input
        tool_input = event.get("tool_input", {})
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, TypeError):
                return
        if not isinstance(tool_input, dict):
            return

        file_path = tool_input.get("file_path", "")
        if not file_path:
            return

        # Resolve the session-reads file path
        reads_path = Path(SESSION_READS_FILE)

        # Ensure parent directory exists
        reads_path.parent.mkdir(parents=True, exist_ok=True)

        # Check for duplicates by reading existing entries
        existing_paths: set[str] = set()
        if reads_path.is_file():
            try:
                content = reads_path.read_text(encoding="utf-8")
                existing_paths = {line.strip() for line in content.splitlines() if line.strip()}
            except OSError:
                pass

        # Only append if not already tracked
        if file_path not in existing_paths:
            with open(reads_path, "a", encoding="utf-8") as f:
                f.write(file_path + "\n")

        # Silent output — no context injection
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[posttool-session-reads] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
