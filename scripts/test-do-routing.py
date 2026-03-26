#!/usr/bin/env python3
"""Validate that the /do routing tables contain expected trigger-to-skill mappings.

This is a STATIC test -- no LLM calls. It parses the routing-tables.md file and
verifies that each expected trigger phrase appears in a section that references
the expected skill name.

Exit 0 if all pass, exit 1 with details on failures.
"""

import re
import sys
from pathlib import Path

ROUTING_TABLES = Path(__file__).resolve().parent.parent / "skills" / "do" / "references" / "routing-tables.md"

TEST_CASES = [
    ("open a pull request", "pr-sync"),
    ("save my work", "git-commit-flow"),
    ("I'm stuck", "workflow-help"),
    ("why is this broken", "systematic-debugging"),
    ("clean this up", "systematic-refactoring"),
    ("review this", "comprehensive-review"),
    ("debug the goroutine leak", "systematic-debugging"),
    ("commit these changes", "git-commit-flow"),
]


def load_routing_tables(path: Path) -> str:
    """Read routing tables markdown file."""
    if not path.exists():
        print(f"FAIL: routing tables not found at {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def find_trigger_skill_association(content: str, trigger: str, skill: str) -> bool:
    """Check that `trigger` appears in a context associated with `skill`.

    Strategy:
    1. Look for the trigger phrase in the document.
    2. For each occurrence, check whether the skill name appears in the same
       table row (same line or adjacent lines within a markdown table row).
       A markdown table row is a single line starting with |.
    3. Also check the Quick Routing Examples table where trigger is in the
       Request column and skill is in the Routes To column of the same row.
    """
    lines = content.split("\n")

    for i, line in enumerate(lines):
        if trigger.lower() not in line.lower():
            continue

        # Check if skill appears on the same line (typical for table rows)
        if skill.lower() in line.lower():
            return True

        # Check a small window around the match (for multi-line contexts)
        window_start = max(0, i - 2)
        window_end = min(len(lines), i + 3)
        window = "\n".join(lines[window_start:window_end])
        if skill.lower() in window.lower():
            return True

    return False


def main() -> int:
    content = load_routing_tables(ROUTING_TABLES)

    passed = 0
    failed = 0
    failures = []

    for trigger, expected_skill in TEST_CASES:
        if find_trigger_skill_association(content, trigger, expected_skill):
            passed += 1
            print(f"  PASS: '{trigger}' -> {expected_skill}")
        else:
            failed += 1
            failures.append((trigger, expected_skill))
            print(f"  FAIL: '{trigger}' -> {expected_skill}  (not found)")

    print(f"\n{passed} passed, {failed} failed out of {len(TEST_CASES)} test cases")

    if failures:
        print("\nFailures:")
        for trigger, skill in failures:
            print(f"  - Expected '{trigger}' to be associated with '{skill}'")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
