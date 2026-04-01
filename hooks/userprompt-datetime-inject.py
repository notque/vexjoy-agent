#!/usr/bin/env python3
# hook-version: 2.0.0
"""
UserPromptSubmit hook — stub retained for settings.json compatibility.

Previously injected current date/time on every prompt. Removed because
Claude Code natively injects currentDate via getUserContext() in context.ts,
making this hook redundant and wasteful (~50 tokens per prompt).

File kept so settings.json registration does not break. Hook does nothing.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output


def main():
    empty_output("UserPromptSubmit").print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[userprompt-datetime-inject] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
