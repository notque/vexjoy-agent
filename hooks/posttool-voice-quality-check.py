#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PostToolUse:Write Hook: Voice Quality Check

Advisory-only check for AI writing patterns after blog post writes.
Cannot block — prints warnings to stderr for awareness.

Checks:
- Banned AI-sounding words (delve, leverage, robust, etc.)
- Em-dash density
- Curly quote presence
- "It's not X. It's Y." rhetorical pivot pattern
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BANNED_WORDS = re.compile(
    r"\b(delve|leverage|robust|utilize|furthermore|moreover|additionally|consequently)\b",
    re.IGNORECASE,
)

_PIVOT_PATTERN = re.compile(
    r"It'?s not [^.]+\.\s*It'?s [^.]+\.",
    re.IGNORECASE,
)


def _is_blog_post(file_path: str) -> bool:
    normalised = file_path.replace("\\", "/")
    return "content/posts/" in normalised and normalised.endswith(".md")


def _check_content(content: str) -> list:
    """Run all quality checks, return list of issue strings."""
    issues = []

    # Banned words
    banned_found = _BANNED_WORDS.findall(content)
    if banned_found:
        unique = sorted(set(w.lower() for w in banned_found))
        issues.append(f"Banned AI words: {', '.join(unique)}")

    # Em-dash count (high density = AI pattern)
    em_dashes = content.count("—")
    # Threshold: more than 5 per 1000 words is suspicious
    word_count = len(content.split())
    if word_count > 0 and em_dashes > 0:
        density = em_dashes / (word_count / 1000)
        if density > 5:
            issues.append(f"Em-dash density: {em_dashes} dashes ({density:.1f}/1k words)")

    # Curly quotes (AI models tend to produce these)
    curly_quotes = len(re.findall(r"[\u201c\u201d\u2018\u2019]", content))
    if curly_quotes > 0:
        issues.append(f"Curly quotes found: {curly_quotes} instances")

    # Rhetorical pivot pattern
    pivots = _PIVOT_PATTERN.findall(content)
    if pivots:
        issues.append(f"Rhetorical pivot pattern ('It's not X. It's Y.'): {len(pivots)} instances")

    return issues


def main():
    try:
        event_data = read_stdin(timeout=2)
        event = json.loads(event_data)

        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path or not _is_blog_post(file_path):
            return

        # Read the written file to check content
        content = ""
        try:
            content = Path(file_path).read_text()
        except (OSError, UnicodeDecodeError):
            return

        if not content:
            return

        issues = _check_content(content)

        if issues:
            detail = "; ".join(issues)
            print(f"[voice-quality] WARNING: {len(issues)} issues found — {detail}")
        else:
            print("[voice-quality] PASS: 0 issues")

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback
            print(f"[voice-quality] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
