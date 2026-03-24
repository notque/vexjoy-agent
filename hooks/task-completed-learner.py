#!/usr/bin/env python3
# hook-version: 1.0.0
"""
TaskCompleted Hook: Capture subagent/task completion metadata.

Fires when a task is marked as completed (via TaskUpdate or teammate finishing).
Records task metadata to learning.db for tracking which agent types succeed
at which task types — enabling better routing decisions over time.

Design Principles:
- Lightweight: Only captures metadata, not transcript content
- Non-blocking: Always exits 0
- Category: effectiveness (tracks what works)
"""

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

EVENT_NAME = "TaskCompleted"


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            print("{}")
            sys.exit(0)

        event = json.loads(event_data)

        task_id = event.get("task_id", "")
        task_subject = event.get("task_subject", "")
        teammate_name = event.get("teammate_name", "")
        session_id = event.get("session_id", "")

        if not task_subject:
            if debug:
                print("[task-completed] No task_subject, skipping", file=sys.stderr)
            print("{}")
            sys.exit(0)

        # Lazy import to avoid startup cost
        from learning_db_v2 import record_learning

        # Build a compact value from the available metadata
        value_parts = [f"task: {task_subject}"]
        if teammate_name:
            value_parts.append(f"agent: {teammate_name}")

        value = " | ".join(value_parts)

        # Derive tags from task subject keywords
        tags = []
        subject_lower = task_subject.lower()
        for keyword in [
            "go",
            "python",
            "typescript",
            "test",
            "review",
            "debug",
            "fix",
            "implement",
            "refactor",
            "deploy",
            "hook",
            "skill",
            "agent",
            "security",
            "performance",
        ]:
            if keyword in subject_lower:
                tags.append(keyword)

        if teammate_name:
            tags.append(teammate_name)

        record_learning(
            topic="task-completion",
            key=task_id or task_subject[:50],
            value=value,
            category="effectiveness",
            tags=tags or ["task"],
            confidence=0.4,  # Low initial confidence; patterns emerge from frequency
            session_id=session_id,
        )

        if debug:
            print(
                f"[task-completed] Recorded: {task_subject[:60]} tags={tags}",
                file=sys.stderr,
            )

    except json.JSONDecodeError:
        if debug:
            print("[task-completed] Invalid JSON input", file=sys.stderr)
    except Exception as e:
        if debug:
            print(f"[task-completed] Error: {e}", file=sys.stderr)

    print("{}")
    sys.exit(0)


if __name__ == "__main__":
    main()
