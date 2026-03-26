#!/usr/bin/env python3
"""PostCompact hook: re-inject plan context after context compaction.

After compaction shrinks the conversation, this hook reminds the model
about the active task plan and/or ADR session so work can continue
without losing track of goals.
"""

import json
import os
import sys
from pathlib import Path


def main():
    try:
        cwd = Path(os.getcwd())

        # Check for active task plan
        plan_file = cwd / "task_plan.md"
        if plan_file.is_file():
            lines = plan_file.read_text().splitlines()[:20]
            preview = "\n".join(lines)
            print(f"[post-compact] Active plan reminder:\n{preview}")

        # Check for active ADR session
        adr_session_file = cwd / ".adr-session.json"
        if adr_session_file.is_file():
            try:
                data = json.loads(adr_session_file.read_text())
                adr_path = data.get("adr_path", "unknown")
                print(f"[post-compact] Active ADR session: {adr_path}")
            except (json.JSONDecodeError, KeyError):
                pass  # Malformed file, skip silently

    except Exception:
        pass  # Hook must never fail itself

    sys.exit(0)


if __name__ == "__main__":
    main()
