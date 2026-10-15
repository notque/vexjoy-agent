#!/usr/bin/env python3
# hook-version: 2.0.1
"""
UserPromptSubmit hook — stub retained for settings.json compatibility.

Previously detected creation requests before model processing and injected
ADR enforcement reminders. Removed because the /do skill already handles
creation request detection in Phase 1 (CLASSIFY), and this hook caused
false positives on any prompt containing "create".

File kept so settings.json registration does not break. Hook does nothing.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, hook_error

_BYPASS_ENV = "CREATION_REQUEST_ENFORCER_USERPROMPT_BYPASS"


def main():
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(
                "[creation-request-enforcer-userprompt] Bypassed via CREATION_REQUEST_ENFORCER_USERPROMPT_BYPASS=1",
                file=sys.stderr,
            )
        sys.exit(0)

    empty_output("UserPromptSubmit").print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hook_error("creation-request-enforcer-userprompt", e)
    finally:
        sys.exit(0)
