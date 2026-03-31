#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Learning Context Loader

Loads relevant learned patterns at session start from unified learning database.
Injects high-confidence solutions into context.

Design Principles:
- SILENT unless meaningful patterns found
- Project-aware (loads patterns for current directory)
- High-confidence only (>0.7 threshold)
- Fast execution (<50ms target)
- Non-blocking (always exits 0)
"""

import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output
from learning_db_v2 import get_stats, query_learnings

EVENT_NAME = "SessionStart"


def main():
    """Load learned patterns at session start."""
    try:
        cwd = os.getcwd()

        # Get high-confidence learnings
        learnings = query_learnings(
            category="error",
            min_confidence=0.7,
            project_path=cwd,
            limit=10,
        )

        if not learnings:
            empty_output(EVENT_NAME).print_and_exit()

        # Aggregate context lines
        lines = []
        lines.append(f"[learned-context] Loaded {len(learnings)} high-confidence patterns")

        # Group by error type
        by_type = {}
        for p in learnings:
            et = p.get("error_type") or p.get("topic", "unknown")
            by_type[et] = by_type.get(et, 0) + 1

        type_summary = ", ".join(f"{et}({count})" for et, count in sorted(by_type.items()))
        lines.append(f"[learned-context] Types: {type_summary}")

        # Show stats
        stats = get_stats()
        total = stats.get("total_learnings", 0)
        if total > 0:
            high_conf = stats.get("high_confidence", 0)
            lines.append(f"[learned-context] {high_conf}/{total} patterns at high confidence")

        context_output(EVENT_NAME, "\n".join(lines)).print_and_exit()

    except Exception as e:
        # Log to stderr if debug enabled, but never fail
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[learned-context] Error: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
