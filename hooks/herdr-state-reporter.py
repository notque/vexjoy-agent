#!/usr/bin/env python3
"""Report session/subagent state to herdr for sidebar visibility.

No-op when HERDR_ENV and HERDR_PANE_ID are absent. Fail-open on all errors.

Events: SessionStart, SubagentStop
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output, hook_error
from stdin_timeout import read_stdin

HOOK_NAME = "herdr-state-reporter"


def _herdr_available() -> bool:
    """Return True when running inside a herdr environment."""
    return os.environ.get("HERDR_ENV") == "1" and bool(os.environ.get("HERDR_PANE_ID"))


def _report_state(state: str, label: str = "vexjoy-agent") -> None:
    """Call herdr pane report-agent. Swallows all errors."""
    import subprocess

    try:
        subprocess.run(
            ["herdr", "pane", "report-agent", "--state", state, "--label", label],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def _handle_session_start() -> None:
    """Report working state on session start; inject context."""
    _report_state("working")
    context_output(
        "SessionStart",
        "[herdr] Session state reported as working.",
    ).print_and_exit()


def _handle_subagent_stop(event: dict) -> None:
    """Derive aggregate state from subagent status and report."""
    # SubagentStop does not support hookSpecificOutput, so no context injection.
    # Determine state from event payload.
    subagent_result = event.get("subagent_result", {}) or {}
    if isinstance(subagent_result, dict) and subagent_result.get("blocked"):
        _report_state("blocked")
    else:
        _report_state("idle")


def main() -> None:
    if not _herdr_available():
        sys.exit(0)

    raw = read_stdin(timeout=2)
    if not raw:
        # No event data; report working as a safe default for SessionStart.
        _report_state("working")
        return

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    event_type = event.get("hook_event_name") or event.get("type", "")

    if event_type == "SessionStart":
        _handle_session_start()
    elif event_type == "SubagentStop":
        _handle_subagent_stop(event)
    else:
        # Unknown event type; no-op.
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error(HOOK_NAME, e)
    finally:
        sys.exit(0)
