#!/usr/bin/env python3
# hook-version: 1.1.0
"""SessionStart hook: inject autonomous behavioral context for AFK sessions.

Injects a posture block that instructs Claude to work proactively without
requiring confirmation (ADR-143). In the default 'always' mode it injects on
every session without detecting anything, so the block states the configured
mode; it never claims the user is or is not watching. In 'auto' mode it
injects only for SSH/tmux/screen sessions and says that is what it saw.

Environment:
    CLAUDE_AFK_MODE  - Control override: 'always' (default), 'auto', or 'never'
    SSH_CONNECTION   - Set by SSH daemon when connected via SSH
    SSH_TTY          - Set when SSH allocates a TTY
    SSH_CLIENT       - Set by SSH daemon (older form)
    TMUX             - Set by tmux when inside a tmux session
    STY              - Set by GNU screen when inside a screen session

Always exits 0 (advisory, never blocking).
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from hook_utils import context_output, empty_output, hook_error

EVENT_NAME = "SessionStart"

_AFK_GUIDANCE = (
    "Work proactively. Complete multi-step tasks without asking for confirmation.\n"
    "If you can determine the next logical step, take it.\n"
    "Produce concise task-completion summaries when finishing long-running work.\n"
    "Actions that CLAUDE.md reserves for owner approval still need that approval."
)

# 'always' mode detects nothing, so the block states the setting.
AFK_CONTEXT = (
    "<afk-mode>\n"
    'AFK mode is set to "always" (CLAUDE_AFK_MODE), so work as if the user may not be watching '
    "the terminal. This is the configured mode; nothing checked whether anyone is watching.\n"
    f"{_AFK_GUIDANCE}\n"
    "</afk-mode>"
)

# 'auto' mode saw an SSH/tmux/screen session, which suggests but does not prove
# that nobody is watching.
AFK_AUTO_CONTEXT = (
    "<afk-mode>\n"
    'AFK mode is "auto" (CLAUDE_AFK_MODE) and this session runs over SSH, tmux or screen, so work as '
    "if the user may not be watching the terminal. Nothing checked whether anyone is watching.\n"
    f"{_AFK_GUIDANCE}\n"
    "</afk-mode>"
)


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


_BYPASS_ENV = "AFK_MODE_BYPASS"


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[afk-mode] Bypassed via AFK_MODE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    mode = os.environ.get("CLAUDE_AFK_MODE", "always").strip().lower()

    if mode == "always":
        context_output(EVENT_NAME, AFK_CONTEXT).print_and_exit()

    if mode == "never":
        empty_output(EVENT_NAME).print_and_exit()

    # Default: auto-detect
    if is_afk():
        context_output(EVENT_NAME, AFK_AUTO_CONTEXT).print_and_exit()
    else:
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("afk-mode", e)
    finally:
        sys.exit(0)
