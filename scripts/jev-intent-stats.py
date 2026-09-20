#!/usr/bin/env python3
"""Report /d proposed-intent alignment rates from learning.db."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

from learning_db_v2 import jev_intent_alignment_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Show /d intent-difference rates by Jev model and transport.")
    parser.add_argument("--days", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = jev_intent_alignment_stats(args.days)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if not rows:
        print("No proposed-intent alignment judgments recorded.")
        return 0
    print(
        "agent_model\tagent_effort\truntime\tjudge_model\ttransport\tjudgments\tmeasured\tdifferences\trate\treviews\troute_mismatches\tclarifications"
    )
    for row in rows:
        rate = row["material_difference_rate"]
        rate_text = "-" if rate is None else f"{rate:.1%}"
        print(
            f"{row['agent_model'] or '-'}\t{row['agent_effort'] or '-'}\t{row['agent_runtime'] or '-'}\t"
            f"{row['model'] or '-'}\t{row['transport']}\t{row['judgments']}\t{row['measured_differences']}\t"
            f"{row['material_differences']}\t{rate_text}\t{row['reviews']}\t{row['route_mismatches']}\t"
            f"{row['clarifications']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
