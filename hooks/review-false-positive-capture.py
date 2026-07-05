#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Capture review false-positive signals.

Detects when a user disputes a code-review finding (e.g. "false positive",
"that finding is wrong", "reviewer was wrong about X"). Records to
learning.db with topic="review-false-positive", category="review".

Tries to extract reviewer agent name and source file from the prompt
(best-effort). Structured recording with full metadata is available via
the `record-review-fp` subcommand in scripts/learning-db.py.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error
from learning_db_v2 import record_learning
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Patterns that signal the user is disputing a review finding.
# Ordered by specificity (most specific first).
FP_PATTERNS = [
    r"\bfalse\s+positive\b",
    r"\bnot\s+a\s+(real\s+)?(bug|issue|problem|defect)\b",
    r"\bthat\s+finding\s+is\s+(wrong|incorrect|invalid)\b",
    r"\breview(er)?\s+(was|is)\s+wrong\b",
    r"\bdisagree\s+with\s+(the\s+)?review\b",
    r"\bthat('?s| is)\s+not\s+an?\s+(issue|bug|problem)\b",
    r"\breview\s+(finding|point)\s+.{0,40}(wrong|incorrect|doesn'?t\s+apply)\b",
    r"\bnot\s+actually\s+a\s+(bug|issue|problem)\b",
]

# Best-effort extraction of reviewer agent name from prompt text.
_REVIEWER_AGENTS = [
    "reviewer-code",
    "reviewer-domain",
    "reviewer-perspectives",
    "reviewer-system",
    "code-reviewer",
    "code-review",
]

_REVIEWER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in _REVIEWER_AGENTS) + r")\b",
    re.IGNORECASE,
)

# Best-effort extraction of file paths from prompt text.
_FILE_PATTERN = re.compile(r"(?:^|\s)([\w./-]+\.(?:py|ts|tsx|js|jsx|go|rs|md|yaml|yml|json|sh|sql))\b")


def generate_key(text: str) -> str:
    """MD5 hash of normalized first 200 chars for deduplication."""
    normalized = text[:200].lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


def extract_reviewer(text: str) -> str:
    """Best-effort reviewer agent name from prompt text."""
    m = _REVIEWER_PATTERN.search(text)
    return m.group(1).lower() if m else "unknown"


def extract_source_file(text: str) -> str:
    """Best-effort source file path from prompt text."""
    m = _FILE_PATTERN.search(text)
    return m.group(1) if m else "unknown"


def main():
    try:
        hook_input = json.loads(read_stdin(timeout=2))
        prompt = (hook_input.get("prompt") or "").strip()
        if not prompt:
            empty_output(EVENT_NAME).print_and_exit()

        cwd = hook_input.get("cwd") or str(Path.cwd())
        session_id = hook_input.get("session_id") or get_session_id()
        window = prompt[:500]

        for pattern in FP_PATTERNS:
            if re.search(pattern, window, re.IGNORECASE):
                reviewer = extract_reviewer(window)
                source_file = extract_source_file(window)

                value = (
                    f"finding: {prompt[:200]} | reviewer: {reviewer} | reason: user-disputed | source: {source_file}"
                )

                tags = ["false-positive"]
                if reviewer != "unknown":
                    tags.append(reviewer)

                record_learning(
                    topic="review-false-positive",
                    key=generate_key(prompt),
                    value=value,
                    category="review",
                    confidence=0.70,
                    tags=tags,
                    source="hook:review-false-positive-capture",
                    source_detail=f"pattern:{pattern}",
                    project_path=cwd,
                    session_id=session_id,
                )
                print(
                    f"[review-fp] captured: reviewer={reviewer} source={source_file} prompt={prompt[:60]}",
                    file=sys.stderr,
                )
                empty_output(EVENT_NAME).print_and_exit()

        # No match -- silent exit
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("review-false-positive-capture", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
