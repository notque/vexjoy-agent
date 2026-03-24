#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Record session-level retro knowledge activation for ROI tracking.

Tracks whether sessions with retro knowledge injected produce successful
outcomes. Feeds learning-db.py record-session for cohort comparison
(sessions with retro knowledge vs without).

ADR-032 Phase 1 — TRACK component.

Design:
- SILENT always (no stdout output to Claude)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, no heavy imports)
- Batched recording: only records every 10th successful tool use
- Uses /tmp marker file to detect retro knowledge presence
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import get_session_id
from stdin_timeout import read_stdin

# Tools that represent meaningful work completing successfully
TRACKED_TOOLS = {"Edit", "Write", "Bash"}


def main() -> None:
    """Record session activation stats on successful tool completions."""
    try:
        hook_input = json.loads(read_stdin(timeout=2))

        tool_name = hook_input.get("tool_name", "")
        if tool_name not in TRACKED_TOOLS:
            return

        tool_result = hook_input.get("tool_result", {})
        if tool_result.get("is_error", False):
            return

        session_id = get_session_id()

        # Check if retro knowledge was injected this session.
        # The retro-knowledge-injector.py sets this marker when it injects.
        marker = Path("/tmp") / f"claude-retro-active-{session_id}"
        had_retro = marker.exists()

        # Batch: only record every 10th successful tool use to avoid spam
        counter_file = Path("/tmp") / f"claude-activation-counter-{session_id}"
        count = 0
        if counter_file.exists():
            try:
                count = int(counter_file.read_text().strip())
            except (ValueError, OSError):
                count = 0
        count += 1
        counter_file.write_text(str(count))

        if count % 10 != 0:
            return

        # Record session stats via learning-db.py
        repo_root = Path(__file__).resolve().parent.parent
        script = repo_root / "scripts" / "learning-db.py"
        if not script.exists():
            return

        cmd = [
            sys.executable,
            str(script),
            "record-session",
            "--session",
            session_id,
            "--failures",
            "0",
            "--waste-tokens",
            "0",
        ]
        if had_retro:
            cmd.append("--had-retro")

        subprocess.run(cmd, capture_output=True, timeout=5)

    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, Exception):
        pass  # Silent failure — never block the session
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
