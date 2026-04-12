#!/usr/bin/env python3
"""Routing-table drift check.

Verifies that every skill present in skills/INDEX.json is also mentioned
in skills/do/references/routing-tables.md. A skill absent from the routing
table is invisible to any process that consults the reference docs, which
means users and the router's documentation are silently out of sync.

Usage:
    python3 scripts/check-routing-drift.py
    python3 scripts/check-routing-drift.py --verbose

Exit codes:
    0 - All skills in INDEX.json are present in routing-tables.md
    1 - One or more skills are absent from routing-tables.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
ROUTING_TABLES = REPO_ROOT / "skills" / "do" / "references" / "routing-tables.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Show all skills checked")
    args = parser.parse_args()

    if not SKILLS_INDEX.exists():
        print(f"ERROR: {SKILLS_INDEX} not found", file=sys.stderr)
        return 1

    if not ROUTING_TABLES.exists():
        print(f"ERROR: {ROUTING_TABLES} not found", file=sys.stderr)
        return 1

    with open(SKILLS_INDEX) as f:
        idx = json.load(f)

    index_skills = sorted(idx.get("skills", {}).keys())
    routing_text = ROUTING_TABLES.read_text()

    missing = [s for s in index_skills if s not in routing_text]
    present = [s for s in index_skills if s in routing_text]

    if args.verbose:
        print(f"Checked {len(index_skills)} skills against routing-tables.md")
        print(f"  Present: {len(present)}")
        print(f"  Missing: {len(missing)}")

    if missing:
        print(f"\nFAIL: {len(missing)} skill(s) in INDEX.json absent from routing-tables.md:")
        for skill in missing:
            print(f"  {skill}")
        print("\nAdd each missing skill to skills/do/references/routing-tables.md before merging.")
        return 1

    if args.verbose:
        print("\nPASS: routing-tables.md is in sync with INDEX.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
