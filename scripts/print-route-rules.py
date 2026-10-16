#!/usr/bin/env python3
"""Print /do's Phase 2 routing rules so /d applies the same text.

The rules live once, in `skills/meta/do/SKILL.md`, from the line
"**Routing rules (ALL apply):**" up to "**Section validator (before
dispatch):**". That span holds the section-integrity, FORCE-route,
pipeline-selection, multi-agent, and specificity rules, the combination
doctrine, and the Step 0b skill-greediness gate, agent-greediness gate,
pairing rule, and fallback reason. /d prints it instead of copying it, so the
two routers cannot drift. `scripts/tests/test_print_route_rules.py` fails when
either anchor moves.

Usage:
    python3 scripts/print-route-rules.py

Exit codes:
    0 -- rules printed
    1 -- /do's SKILL.md is missing or an anchor is gone (message on stderr)
"""

from __future__ import annotations

import sys
from pathlib import Path

START = "**Routing rules (ALL apply):**"
END = "**Section validator (before dispatch):**"

_SCRIPTS_DIR = Path(__file__).resolve().parent


def do_skill_path() -> Path | None:
    """/do's SKILL.md in the repo layout (skills/meta/do) or the flat installed layout (skills/do)."""
    base = _SCRIPTS_DIR.parent
    for candidate in (base / "skills" / "meta" / "do" / "SKILL.md", base / "skills" / "do" / "SKILL.md"):
        if candidate.is_file():
            return candidate
    return None


def extract_rules(text: str) -> str:
    """The rule span of /do's SKILL.md. Raises ValueError when an anchor is missing or out of order."""
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"anchors {START!r} and {END!r} not found in order")
    return text[start:end].strip() + "\n"


def main() -> int:
    path = do_skill_path()
    if path is None:
        print("[print-route-rules] skills/meta/do/SKILL.md not found", file=sys.stderr)
        return 1
    try:
        sys.stdout.write(extract_rules(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        print(f"[print-route-rules] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
