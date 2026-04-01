#!/usr/bin/env python3
"""UserPromptSubmit hook: inject autonomous behavioral context for AFK sessions.

Detects SSH/tmux/screen/headless sessions and injects a posture block that
instructs Claude to work proactively without requiring confirmation (ADR-143).

Environment:
    CLAUDE_AFK_MODE  - Control override: 'always' (default), 'auto', or 'never'
    SSH_CONNECTION   - Set by SSH daemon when connected via SSH
    SSH_TTY          - Set when SSH allocates a TTY
    SSH_CLIENT       - Set by SSH daemon (older form)
    TMUX             - Set by tmux when inside a tmux session
    STY              - Set by GNU screen when inside a screen session

Always exits 0 (advisory, never blocking).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from hook_utils import context_output, empty_output

EVENT_NAME = "UserPromptSubmit"

AFK_CONTEXT = """<afk-mode>
The terminal is unfocused — the user is not actively watching.
Work proactively. Complete multi-step tasks without asking for confirmation.
If you can determine the next logical step, take it.
Produce concise task-completion summaries when finishing long-running work.
</afk-mode>"""


def is_afk() -> bool:
    """Return True if the session appears to be AFK (unattended).

    NOTE: Do NOT use sys.stdin.isatty() or sys.stdout.isatty() here.
    Claude Code pipes stdin (event JSON) and captures stdout (hook output),
    so both are always non-TTY in hook context — the check would always
    return True, activating AFK mode on every session regardless of type.
    """
    # SSH indicators
    if os.environ.get("SSH_CONNECTION"):
        return True
    if os.environ.get("SSH_TTY"):
        return True
    if os.environ.get("SSH_CLIENT"):
        return True
    # Multiplexer indicators
    if os.environ.get("TMUX"):
        return True
    if os.environ.get("STY"):
        return True
    return False


def main() -> None:
    mode = os.environ.get("CLAUDE_AFK_MODE", "always").strip().lower()

    if mode == "always":
        context_output(EVENT_NAME, AFK_CONTEXT).print_and_exit()

    if mode == "never":
        empty_output(EVENT_NAME).print_and_exit()

    # Default: auto-detect
    if is_afk():
        context_output(EVENT_NAME, AFK_CONTEXT).print_and_exit()
    else:
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
