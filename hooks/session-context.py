#!/usr/bin/env python3
"""
SessionStart Hook: Learning Context Loader

Loads relevant learned patterns at session start from SQLite database.
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

from learning_db import get_high_confidence_patterns, get_stats


def main():
    """Load learned patterns at session start."""
    try:
        cwd = os.getcwd()

        # Get high-confidence patterns
        patterns = get_high_confidence_patterns(min_confidence=0.7, project_path=cwd, limit=10)

        if not patterns:
            return  # Silent when no relevant patterns

        # Print context information
        print(f"[learned-context] Loaded {len(patterns)} high-confidence patterns")

        # Group by error type
        by_type = {}
        for p in patterns:
            et = p.get("error_type", "unknown")
            by_type[et] = by_type.get(et, 0) + 1

        type_summary = ", ".join(f"{et}({count})" for et, count in sorted(by_type.items()))
        print(f"[learned-context] Types: {type_summary}")

        # Show stats
        stats = get_stats()
        pattern_stats = stats.get("patterns", {})
        if pattern_stats.get("total_patterns", 0) > 0:
            high_conf = pattern_stats.get("high_confidence", 0) or 0
            total = pattern_stats.get("total_patterns", 1)
            print(f"[learned-context] {high_conf}/{total} patterns at high confidence")

    except Exception as e:
        # Log to stderr if debug enabled, but never fail
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[learned-context] Error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
