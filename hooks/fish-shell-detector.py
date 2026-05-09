#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Fish Shell Detection

Detects Fish shell users and injects the fish-shell-config skill.
Runs once at session start to provide Fish-specific guidance.

Detection Logic:
- Check $SHELL environment variable for "fish"
- Check if ~/.config/fish/ directory exists

Output Format:
- [fish-shell] Detected Fish shell user
- [auto-skill] fish-shell-config

Design Principles:
- Lightweight detection (no complex processing)
- Non-blocking (always exits 0)
- Fast execution (<50ms target, depends on filesystem responsiveness)
"""

import os
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output

EVENT_NAME = "SessionStart"


def is_fish_shell() -> bool:
    """
    Detect if the user is using Fish shell.

    Returns:
        True if Fish shell is detected, False otherwise
    """
    # Check $SHELL environment variable
    shell = os.environ.get("SHELL", "")
    if "fish" in shell.lower():
        return True

    # Fallback: check if Fish config directory exists
    # Handle environments without HOME (containers, CI) gracefully
    try:
        fish_config_dir = Path.home() / ".config" / "fish"
        if fish_config_dir.is_dir():
            return True
    except (RuntimeError, OSError):
        # Path.home() can raise RuntimeError if HOME is not set
        # is_dir() can raise OSError for permission/filesystem issues
        pass

    return False


def get_fish_injection() -> str:
    """Get the context injection for Fish shell users.

    Emits only tags. The fish-shell-config skill carries its own knowledge.
    ADR hook-injection-condensation: removed tutorial block.
    """
    return "[fish-shell] Detected Fish shell user\n[auto-skill] fish-shell-config"


def main():
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        if not is_fish_shell():
            # Silent for non-Fish users
            empty_output(EVENT_NAME).print_and_exit()

        # Log detection for debugging visibility
        if debug:
            shell = os.environ.get("SHELL", "")
            print(f"[fish-shell] Detected Fish shell: SHELL={shell}", file=sys.stderr)

        # Inject Fish shell context
        injection = get_fish_injection()
        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        # Always log error to stderr for observability
        if debug:
            print(f"[fish-shell] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[fish-shell] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
