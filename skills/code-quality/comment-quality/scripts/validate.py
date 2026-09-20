#!/usr/bin/env python3
"""Validate the comment-quality skill's small local contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    words = (ROOT / "references/temporal-keywords.md").read_text(encoding="utf-8")
    required = [
        "name: comment-quality",
        "candidate list, not a verdict",
        "Version control owns change history",
        "Do not invent rationale",
    ]
    missing = [item for item in required if item not in skill]
    if len([line for line in words.splitlines() if line and not line.startswith("#")]) < 10:
        missing.append("temporal keyword candidates")
    for item in missing:
        print(f"missing: {item}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
