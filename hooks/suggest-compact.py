#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse hook: Strategic Compact Advisor

Counts Edit and Write tool calls per session and emits a suggestion to run
/compact when the call count reaches a configured threshold. Periodic reminders
are emitted every 25 calls after the threshold.

This is an ADVISORY hook — it always exits 0 and never blocks tool execution.
Exit 2 would block the tool call, which is wrong for an advisory signal.

ADR: adr/ADR-103-strategic-compact.md

Configuration:
  COMPACT_THRESHOLD  env var - suggestion threshold (default: 50, clamped 1-10000)

Output (to stdout as JSON hook response):
  At threshold:       [strategic-compact] {N} tool calls reached — consider
                      /compact if transitioning phases
  Every 25 after:     [strategic-compact] {N} tool calls — good checkpoint for
                      /compact if context is stale
  Otherwise:          exits 0 silently

State:
  Counter persisted to session-keyed temp file via get_state_file("compact-count")
  from hooks.lib.hook_utils. Uses file locking to reduce race window.
"""

import fcntl
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_state_file
from stdin_timeout import read_stdin

# --- Configuration -----------------------------------------------------------

_DEFAULT_THRESHOLD = 50
_REMINDER_INTERVAL = 25
_TRACKED_TOOLS = frozenset({"Edit", "Write"})
_EVENT_NAME = "PreToolUse"

# --- Helpers -----------------------------------------------------------------


def _get_threshold() -> int:
    """Read COMPACT_THRESHOLD env var, clamped to [1, 10000]."""
    try:
        raw = int(os.environ.get("COMPACT_THRESHOLD", str(_DEFAULT_THRESHOLD)))
        return max(1, min(10000, raw))
    except (ValueError, TypeError):
        return _DEFAULT_THRESHOLD


def _get_and_increment_count() -> int:
    """Read, increment, and persist the call counter; return the new count.

    Uses an exclusive flock to reduce the race window on concurrent invocations.
    Falls back to count=1 if the state file cannot be read or parsed.
    """
    state_file = get_state_file("compact-count")
    count = 0

    try:
        with open(state_file, "a+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read().strip()
                if content:
                    count = int(content)
                count += 1
                f.seek(0)
                f.truncate()
                f.write(str(count))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (ValueError, OSError):
        count = 1

    return count


# --- Main --------------------------------------------------------------------


def main() -> None:
    try:
        _run()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(
                f"[suggest-compact] HOOK-ERROR: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)


def _run() -> None:
    debug = bool(os.environ.get("CLAUDE_HOOKS_DEBUG"))

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        empty_output(_EVENT_NAME).print_and_exit(0)
        return

    tool_name = event.get("tool_name", "")
    if tool_name not in _TRACKED_TOOLS:
        empty_output(_EVENT_NAME).print_and_exit(0)
        return

    threshold = _get_threshold()
    count = _get_and_increment_count()

    if debug:
        print(
            f"[suggest-compact] tool={tool_name} count={count} threshold={threshold}",
            file=sys.stderr,
        )

    # Decide whether to emit a suggestion
    if count == threshold:
        msg = f"[strategic-compact] {count} tool calls reached — consider /compact if transitioning phases"
        context_output(_EVENT_NAME, msg).print_and_exit(0)
    elif count > threshold and (count - threshold) % _REMINDER_INTERVAL == 0:
        msg = f"[strategic-compact] {count} tool calls — good checkpoint for /compact if context is stale"
        context_output(_EVENT_NAME, msg).print_and_exit(0)
    else:
        empty_output(_EVENT_NAME).print_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(
                f"[suggest-compact] HOOK-ERROR: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
