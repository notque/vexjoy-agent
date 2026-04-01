#!/usr/bin/env python3
# hook-version: 2.0.0
"""
UserPromptSubmit hook — stub retained for settings.json compatibility.

Previously re-injected CLAUDE.md, AGENTS.md, and RULES.md every 3 prompts.
Removed in ADR-158: Claude Code loads CLAUDE.md natively; re-injection was
duplicating ~3K tokens every third turn with no benefit.

File kept so settings.json registration does not break. Hook does nothing.
"""

import os
import sys
from pathlib import Path

# Add lib to path for hook_utils import
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

            print(f"[instruction-reminder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
