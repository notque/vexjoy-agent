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
        from hook_utils import hook_error
        from learning_db_v2 import decay_confidence, get_connection, init_db, prune, prune_ancillary

        init_db()

        # Step 1: Prune dead entries (confidence < 0.3, older than 90 days)
        pruned = prune(min_confidence=0.3, older_than_days=90)

        # Step 1b: Prune old rows from ancillary tables
        ancillary_counts = prune_ancillary()
        if os.environ.get("CLAUDE_HOOKS_DEBUG") or any(v > 0 for v in ancillary_counts.values()):
            pruned_parts = ", ".join(f"{t}={c}" for t, c in ancillary_counts.items() if c > 0)
            if pruned_parts:
                print(f"[confidence-decay] Ancillary pruning: {pruned_parts}", file=sys.stderr)

        # Step 2: Decay stale entries (untouched > 30 days).
        # Routing rows pull toward neutral 0.5 (T5); every other topic keeps the
        # monotonic -0.05-toward-0 decay (confidence > 0.3 gate).
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        decayed = 0

        with get_connection() as conn:
            # Non-routing: old behavior.
            stale_rows = conn.execute(
                "SELECT topic, key FROM learnings WHERE last_seen < ? AND confidence > 0.3 AND topic != 'routing'",
                (cutoff,),
            ).fetchall()

            # Routing: pull toward 0.5 in-place, without touching last_seen or
            # success/failure counts (this is staleness, not an outcome).
            #
            # Floor guard (confidence > 0.5): staleness must NEVER raise routing
            # confidence. Pulling a sub-floor row (e.g. conf 0.20/0.28 with
            # fail>=3) toward 0.5 would lift it back over FLOOR_CONFIDENCE=0.30
            # and corrupt the floor-demote path the moment negative signal
            # accrues. Prune does not protect these rows: it requires
            # older_than_days=90, but staleness fires at >30 days, so a recently
            # failed sub-floor row survives prune yet is stale. So skip every
            # row at or below the 0.5 baseline (preserve the negative evidence);
            # only above-baseline rows decay downward toward neutral. Scoped to
            # routing because only routing pulls toward 0.5 and only routing has
            # a floor-demote gate; non-routing keeps its monotonic -0.05 path.
            # The > 0.5 bound also drops no-op rows already at exactly 0.5 from
            # rowcount, so `decayed` counts only rows that actually changed.
            routing_updated = conn.execute(
                "UPDATE learnings "
                "SET confidence = confidence + (0.5 - confidence) * 0.1 "
                "WHERE last_seen < ? AND topic = 'routing' AND confidence > 0.5",
                (cutoff,),
            ).rowcount
            conn.commit()

        for row in stale_rows:
            decay_confidence(row["topic"], row["key"], delta=0.05)
            decayed += 1
        decayed += routing_updated

        if debug or pruned > 0 or decayed > 0:
            print(
                f"[confidence-decay] pruned={pruned} decayed={decayed}",
                file=sys.stderr,
            )

    except Exception as e:
        hook_error("confidence-decay", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
