#!/usr/bin/env python3
# hook-version: 2.0.0
"""
UserPromptSubmit hook — stub retained for settings.json compatibility.

Previously injected anti-rationalization warnings based on task-type keywords.
Removed because the /do skill already handles anti-rationalization injection in
Phase 3 (ENHANCE) based on task type, making this a duplicate injection point.

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

            print(f"[anti-rationalization-injector] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
