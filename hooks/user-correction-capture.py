#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Capture user corrections and capability gap signals.

Detects two classes of high-signal user input:
1. Corrections ("no, that's wrong", "actually...") → category="correction"
2. Capability gaps ("can you also...", "I wish you could...") → category="feature_request"

Records to learning.db via record_learning(). Silent on no match.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id
from learning_db_v2 import record_learning
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

CORRECTION_PATTERNS = [
    r"\bno[,.]?\s+that'?s\s+(wrong|not right|incorrect)",
    r"^actually[,\s]",
    r"\bi\s+said\b.+\bnot\b",
    r"\bdon'?t\s+do\s+that\b",
    r"\bstop\s+doing\b",
    r"\bthat'?s\s+incorrect\b",
    r"^wrong[\.\s,]",
    r"\bi\s+already\s+told\s+you\b",
    r"\bnot\s+what\s+i\s+asked\b",
]

GAP_PATTERNS = [
    r"\bcan\s+you\s+also\b",
    r"\bis\s+there\s+a\s+way\s+to\b",
    r"\bi\s+wish\s+you\s+could\b",
    r"\bit\s+would\s+be\s+nice\s+if\b",
    r"\bcan\s+you\s+do\b",
    r"\bdo\s+you\s+support\b",
]


def generate_key(text: str) -> str:
    """MD5 hash of normalized first 200 chars for deduplication."""
    normalized = text[:200].lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


def main():
    try:
        hook_input = json.loads(read_stdin(timeout=2))
        prompt = (hook_input.get("prompt") or "").strip()
        if not prompt:
            empty_output(EVENT_NAME).print_and_exit()

        cwd = hook_input.get("cwd") or str(Path.cwd())
        session_id = hook_input.get("session_id") or get_session_id()
        window = prompt[:500]

        # Check corrections first (higher signal)
        for pattern in CORRECTION_PATTERNS:
            if re.search(pattern, window, re.IGNORECASE):
                record_learning(
                    topic="user-correction",
                    key=generate_key(prompt),
                    value=prompt[:300],
                    category="correction",
                    confidence=0.70,
                    tags=["correction", pattern.split(r"\\")[0][:30]],
                    source="hook:user-correction-capture",
                    source_detail=f"pattern:{pattern}",
                    project_path=cwd,
                    session_id=session_id,
                )
                print(f"[user-correction] captured: {prompt[:80]}")
                empty_output(EVENT_NAME).print_and_exit()

        # Check capability gaps
        for pattern in GAP_PATTERNS:
            if re.search(pattern, window, re.IGNORECASE):
                record_learning(
                    topic="capability-gap",
                    key=generate_key(prompt),
                    value=prompt[:300],
                    category="feature_request",
                    confidence=0.50,
                    tags=["feature-request", "capability-gap"],
                    source="hook:user-correction-capture",
                    source_detail=f"pattern:{pattern}",
                    project_path=cwd,
                    session_id=session_id,
                )
                print(f"[capability-gap] captured: {prompt[:80]}")
                empty_output(EVENT_NAME).print_and_exit()

        # No match — silent exit
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[user-correction-capture] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
