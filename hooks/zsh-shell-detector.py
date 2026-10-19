#!/usr/bin/env python3
# hook-version: 1.0.2
"""
SessionStart Hook: Zsh Shell Detection

Detects Zsh shell users and injects the shell-config skill.
Runs once at session start to provide Zsh-specific guidance.

Detection Logic:
- $SHELL contains "zsh" is the sole, authoritative signal.
- Config directories (~/.zshrc, ~/.config/zsh/) are intentionally not
  inspected — $SHELL alone determines detection, which avoids false
  positives from leftover config after a user switches shells.

Output Format:
- [zsh-shell] Detected Zsh shell user
- [auto-skill] deploy
- Call the Skill tool with `deploy`.

Design Principles:
- Lightweight detection (no complex processing)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, depends on filesystem responsiveness)
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); rerun ./install.sh in vexjoy-agent\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import os
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, hook_error

EVENT_NAME = "SessionStart"


def is_zsh_shell() -> bool:
    """
    Detect if the user is using Zsh shell.

    Returns:
        True if Zsh shell is detected, False otherwise

    Detection logic:
    - Primary: $SHELL contains "zsh" → True
    - Directory presence (~/.zshrc, ~/.config/zsh/) alone is NOT sufficient;
      $SHELL must be the confirming signal to avoid false positives from
      leftover config directories.
    """
    shell = os.environ.get("SHELL", "").lower()

    # Primary signal: $SHELL must name zsh explicitly
    if "zsh" not in shell:
        return False

    # $SHELL contains "zsh" — confirmed Zsh user.
    # Optionally verify config artifacts exist (supporting evidence only).
    # We do not require them; $SHELL alone is sufficient.
    return True


def get_zsh_injection() -> str:
    """Get the context injection for Zsh shell users.

    Emits only tags. The shell-config skill carries its own knowledge.
    """
    return "[zsh-shell] Detected Zsh shell user\n[auto-skill] deploy\nCall the Skill tool with `deploy`."


_BYPASS_ENV = "ZSH_SHELL_DETECTOR_BYPASS"


def main():
    """Main entry point for the hook."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[zsh-shell-detector] Bypassed via ZSH_SHELL_DETECTOR_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        if not is_zsh_shell():
            # Silent for non-Zsh users
            empty_output(EVENT_NAME).print_and_exit()

        # Log detection for debugging visibility
        if debug:
            shell = os.environ.get("SHELL", "")
            print(f"[zsh-shell] Detected Zsh shell: SHELL={shell}", file=sys.stderr)

        # Inject Zsh shell context
        injection = get_zsh_injection()
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        hook_error("zsh-shell-detector", e)
        # Always log error to stderr for observability
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
