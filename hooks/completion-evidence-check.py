#!/usr/bin/env python3
"""PostToolUse hook: detect completion claims without test evidence.

Scans tool output for completion language and checks whether test evidence
is present. If completion is claimed without evidence, prints an advisory
warning (ADR-125).

Environment: CLAUDE_TOOL_OUTPUT (set by PostToolUse hooks, first ~500 chars)
Always exits 0 (advisory, never blocking).
"""

import os
import re
import sys

# Pre-compiled patterns for speed
COMPLETION_PATTERN = re.compile(
    r"(?:task\s+complete|done|finished|all\s+set|looks\s+good|should\s+work"
    r"|I've\s+implemented|I've\s+fixed|changes\s+are\s+ready)",
    re.IGNORECASE,
)

EVIDENCE_PATTERN = re.compile(
    r"(?:PASS|ok\s|passed|exit\s+0|\u2713|tests\s+pass|green|SUCCESS)",
    re.IGNORECASE,
)


def main():
    try:
        output = os.environ.get("CLAUDE_TOOL_OUTPUT", "")
        if not output:
            return

        if COMPLETION_PATTERN.search(output):
            if not EVIDENCE_PATTERN.search(output):
                print(
                    "[completion-check] Completion claimed without test evidence. "
                    "Required: run tests and show output before marking complete."
                )
    except Exception as e:
        print(f"[completion-check] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
