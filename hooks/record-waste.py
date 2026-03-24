#!/usr/bin/env python3
# hook-version: 1.0.0
"""PostToolUse Hook: Record wasted tokens from tool failures for ROI tracking.

Estimates token waste when tools fail and feeds learning-db.py record-waste
for ROI computation. The waste estimate uses output length / 4 (rough
chars-to-tokens ratio) with a minimum floor of 100 tokens.

ADR-032 Phase 1 — TRACK component.

Design:
- SILENT always (no stdout output to Claude)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, no heavy imports)
- Records every failure immediately (no batching — failures are rare)
"""

import json
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import get_session_id
from stdin_timeout import read_stdin

# Minimum token waste estimate per failure
MIN_WASTE_TOKENS = 100

# Rough chars-to-tokens ratio (1 token ~ 4 chars)
CHARS_PER_TOKEN = 4


def main() -> None:
    """Record wasted tokens when a tool execution fails."""
    try:
        hook_input = json.loads(read_stdin(timeout=2))

        tool_result = hook_input.get("tool_result", {})
        if not tool_result.get("is_error", False):
            return  # Only track failures

        # Estimate wasted tokens from output length
        output = tool_result.get("output", "")
        waste_tokens = max(len(output) // CHARS_PER_TOKEN, MIN_WASTE_TOKENS)

        session_id = get_session_id()

        repo_root = Path(__file__).resolve().parent.parent
        script = repo_root / "scripts" / "learning-db.py"
        if not script.exists():
            return

        subprocess.run(
            [
                sys.executable,
                str(script),
                "record-waste",
                "--session",
                session_id,
                "--tokens",
                str(waste_tokens),
            ],
            capture_output=True,
            timeout=5,
        )

    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, Exception):
        pass  # Silent failure — never block the session
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
