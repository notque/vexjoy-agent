#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStop Hook: Routing Outcome Validator (action B, formerly /do Phase 5)

VALIDATES each routing decision's pending outcome — it NO LONGER applies
boost/decay. Scoring moved to the next-turn resolution point: UserPromptSubmit
(routing-outcome-finalizer.py) finalizes from tool-errors + user reaction +
re-route, with a Stop fallback for autonomous runs. See adr/learn-step-to-hook.md.

Why move scoring off SubagentStop: a hook firing at SubagentStop CANNOT observe
"the user rejected the result / asked for rework / accepted it" — those signals
live in the NEXT user turn, which does not exist yet here. Eagerly scoring
success="no tool errors this dispatch" is a low-fidelity floor that misses
silent-rejection failures. The pending entry is therefore left PROVISIONAL and
resolved once, on the next turn, by the finalizer.

What B still does (the A-before-B ordering guard is preserved):

  - Drains the per-session pending list (atomic), and for each entry runs the
    KEYED, no-row-cap decision-row existence check (decision_row_exists). A
    prior top-1000 confidence-DESC scan dropped decayed rows once the table grew
    past 1000 (data loss); the exact (topic, key, category) SELECT has no cap.
  - Entries whose decision row is NOT yet visible (A-before-B mistiming) are
    RE-QUEUED with attempts+1, bounded by MAX_REQUEUE_ATTEMPTS, so a late row
    gets validated on a subsequent stop instead of being dropped.
  - Entries whose decision row IS visible are REVALIDATED — put back pending
    (without advancing the re-queue counter) so the next-turn finalizer can
    resolve them. Stale entries (older than MAX_PENDING_AGE_SEC) are dropped.

Per-agent attribution (HIGH-2) is preserved end to end: each pending entry
carries its OWN ``errors`` flag recorded by action A from THAT dispatch's
structured tool result. No whole-transcript substring scan is performed (it
cross-attributed one agent's error onto sibling keys and false-positived on
prose). The finalizer scores each key by its own flag combined with the
session-level user reaction.

Design Principles:
- SILENT (touches state only, stderr only on debug)
- Non-blocking: every RUNTIME path after module load exits 0 (finally:
  sys.exit(0)).
- Fast execution (<50ms target); lazy imports
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from routing_outcome_state import (
    drain_pending_outcomes,
    requeue_pending_outcomes,
    revalidate_pending_outcomes,
)
from stdin_timeout import read_stdin

EVENT_NAME = "SubagentStop"


def _max_requeue() -> int:
    """Re-queue cap (for debug logging). Mirrors routing_outcome_state."""
    from routing_outcome_state import MAX_REQUEUE_ATTEMPTS

    return MAX_REQUEUE_ATTEMPTS


def main() -> None:
    try:
        raw = read_stdin(timeout=2)
        if not raw:
            return
        event = json.loads(raw)

        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type and event_type != EVENT_NAME:
            return

        session_id = event.get("session_id") or ""
        pending = drain_pending_outcomes(session_id)
        if not pending:
            return  # nothing to validate

        # Lazy import of the shared scorer so a B run that drains nothing pays no
        # learning_db_v2 import cost.
        from learning_db_v2 import init_db
        from routing_outcome_score import decision_row_exists

        # LOW-1: decision_row_exists no longer self-inits; init the schema ONCE
        # before the per-key loop so the keyed SELECT has a DB to open.
        init_db()

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        # HIGH (A-before-B): pending entries whose decision row is not yet
        # visible are RE-QUEUED (attempts+1, bounded) so a late-landing row gets
        # validated on a subsequent stop, rather than being dropped. Entries
        # whose row IS visible are REVALIDATED — put back pending (no attempt
        # advance) so the next-turn finalizer (UserPromptSubmit) / Stop fallback
        # can resolve them. B does NOT apply boost/decay anymore.
        to_requeue: list[dict] = []
        to_revalidate: list[dict] = []
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            if not decision_row_exists(key):
                to_requeue.append(item)
                if debug:
                    print(
                        f"[routing-outcome-recorder] no decision row for '{key}' — re-queued "
                        f"(attempt {int(item.get('attempts', 0)) + 1}/{_max_requeue()})",
                        file=sys.stderr,
                    )
                continue
            # Decision row present: keep PROVISIONAL for next-turn resolution.
            to_revalidate.append(item)
            if debug:
                print(
                    f"[routing-outcome-recorder] validated routing/{key} — pending next-turn resolution",
                    file=sys.stderr,
                )

        if to_requeue:
            requeue_pending_outcomes(session_id, to_requeue)
        if to_revalidate:
            revalidate_pending_outcomes(session_id, to_revalidate)

    except Exception as e:
        hook_error("routing-outcome-recorder", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
