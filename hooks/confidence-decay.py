#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Stop Hook: Decay stale learnings and prune dead entries.

Runs at session end to maintain learning database hygiene:
- Prunes entries with confidence < 0.3 and last_seen > 90 days
- Decays confidence by 0.05 for entries untouched > 30 days

Design Principles:
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- Conservative parameters to avoid over-pruning
- Runs after session-summary.py in the Stop chain
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Lazy imports
        sys.path.insert(0, str(Path(__file__).parent / "lib"))
        from learning_db_v2 import decay_confidence, get_connection, init_db, prune

        init_db()

        # Step 1: Prune dead entries (confidence < 0.3, older than 90 days)
        pruned = prune(min_confidence=0.3, older_than_days=90)

        # Step 2: Decay stale entries (untouched > 30 days, confidence > 0.3)
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        decayed = 0

        with get_connection() as conn:
            stale_rows = conn.execute(
                "SELECT topic, key FROM learnings WHERE last_seen < ? AND confidence > 0.3",
                (cutoff,),
            ).fetchall()

        for row in stale_rows:
            decay_confidence(row["topic"], row["key"], delta=0.05)
            decayed += 1

        if debug or pruned > 0 or decayed > 0:
            print(
                f"[confidence-decay] pruned={pruned} decayed={decayed}",
                file=sys.stderr,
            )

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(f"[confidence-decay] Error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
