#!/usr/bin/env python3
"""
Select enrichment targets from the reference depth audit.

Reads audit JSON (from audit-reference-depth.py --json --min-level 2) on stdin,
selects the top-N targets prioritized by: agents before skills, then alphabetical.

Usage:
    python3 scripts/audit-reference-depth.py --json --min-level 2 | \
        python3 scripts/select-enrichment-targets.py --max-targets 3

    python3 scripts/select-enrichment-targets.py --max-targets 5 < audit.json

Exit codes:
    0  Targets selected (JSON array on stdout)
    0  No gaps found (empty JSON array on stdout)
"""

from __future__ import annotations

import argparse
import json
import sys


def select_targets(audit_data: dict, max_targets: int) -> list[dict]:
    """Select top-N enrichment targets from audit data.

    Priority: agents before skills (agents are the primary knowledge carriers
    per PHILOSOPHY.md), then alphabetical within each group.
    """
    # The audit JSON uses "gaps" for filtered results, "all" for everything
    components = audit_data.get("gaps", audit_data.get("components", []))

    # The audit's --min-level flag already filters the output, so all
    # components in the audit data are below the target level. Pass them
    # through without a second hardcoded filter.
    gaps = components

    # Separate agents and skills
    agents = sorted(
        [g for g in gaps if g.get("kind") == "agent"],
        key=lambda g: g["name"],
    )
    skills = sorted(
        [g for g in gaps if g.get("kind") == "skill"],
        key=lambda g: g["name"],
    )

    # Agents first, then skills
    ordered = agents + skills

    # Trim to max_targets
    selected = ordered[:max_targets]

    return [
        {
            "name": t["name"],
            "kind": t.get("kind", "unknown"),
            "level": t.get("level", 0),
            "path": t.get("path", ""),
        }
        for t in selected
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Select enrichment targets from audit JSON.")
    parser.add_argument(
        "--max-targets",
        type=int,
        default=3,
        help="Maximum number of targets to select (default: 3)",
    )
    parser.add_argument(
        "--names-only",
        action="store_true",
        help="Output just a JSON array of names instead of full objects",
    )
    args = parser.parse_args()

    try:
        audit_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("[]")
        return

    selected = select_targets(audit_data, args.max_targets)

    if args.names_only:
        print(json.dumps([t["name"] for t in selected]))
    else:
        print(json.dumps(selected, indent=2))


if __name__ == "__main__":
    main()
