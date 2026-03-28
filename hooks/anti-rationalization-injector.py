#!/usr/bin/env python3
"""UserPromptSubmit hook: inject anti-rationalization warnings based on task keywords.

Scans the user prompt for task-type keywords and injects relevant warnings
to combat rationalization patterns (ADR-125).

Environment: CLAUDE_USER_PROMPT (set by UserPromptSubmit hooks)
Always exits 0 (advisory, never blocking).
"""

import os
import re
import sys

# Pre-compiled patterns for speed (<50ms target)
PATTERNS = [
    (
        re.compile(r"\b(?:fix|debug|broken|error|failing)\b", re.IGNORECASE),
        "[anti-rationalization] Task type: FIX. Required: run tests and show output. Do not mark complete without test evidence.",
    ),
    (
        re.compile(r"\b(?:refactor|clean\s*up|restructure|simplify)\b", re.IGNORECASE),
        "[anti-rationalization] Task type: REFACTOR. Tests must pass before AND after. No behavior change allowed.",
    ),
    (
        re.compile(r"\b(?:add\s+feature|implement|create|build)\b", re.IGNORECASE),
        "[anti-rationalization] Task type: IMPLEMENT. Only build what was asked. YAGNI applies. No phantom features.",
    ),
    (
        re.compile(r"\b(?:complete|done|finish|finalize)\b", re.IGNORECASE),
        "[anti-rationalization] Task type: COMPLETE. Provide evidence of completion (test output, file paths, validation results).",
    ),
    (
        re.compile(r"\b(?:quick|simple|easy|just)\b", re.IGNORECASE),
        "[anti-rationalization] CAUTION: 'Simple changes' cause complex bugs. Full verification required regardless.",
    ),
]


def main():
    try:
        prompt = os.environ.get("CLAUDE_USER_PROMPT", "")
        if not prompt:
            return

        messages = []
        for pattern, message in PATTERNS:
            if pattern.search(prompt):
                messages.append(message)

        if messages:
            print("\n".join(messages))
    except Exception as e:
        print(f"[anti-rationalization] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
    sys.exit(0)
