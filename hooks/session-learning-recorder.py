#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Stop Hook: Session Learning Gap Detector

Fires at session end to check whether the session recorded any learnings.
Prints a gap warning for substantive sessions with zero learnings, or a
summary count when learnings were captured.

Design Principles:
- Observability only, not enforcement
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
- Silent on trivial sessions
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error
from learning_db_v2 import get_connection, init_db
from stdin_timeout import read_stdin

EVENT_NAME = "Stop"

SUBSTANTIVE_TOOL_THRESHOLD = 5


def count_session_learnings(session_id: str) -> int:
    """Count learnings recorded for this session.

    Falls back to time-based query (last hour) if no session_id match.
    """
    init_db()

    with get_connection() as conn:
        # Primary: match by session_id
        row = conn.execute(
            "SELECT COUNT(*) FROM learnings WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        count = row[0] if row else 0

        if count > 0:
            return count

        # Fallback: learnings recorded in the last hour
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) FROM learnings WHERE last_seen >= ?",
            (cutoff,),
        ).fetchone()
        return row[0] if row else 0


def finalize_routing_outcomes(session_id: str) -> None:
    """Stop fallback: resolve any STILL-pending routed dispatches.

    The next-turn finalizer (UserPromptSubmit, routing-outcome-finalizer.py)
    resolves a dispatch's outcome from tool-errors + user reaction + re-route.
    But an autonomous / headless run may end with NO next user prompt, leaving
    its dispatches provisional forever. This fallback resolves whatever the
    UserPromptSubmit finalizer did not, using the DETERMINISTIC FLOOR — this
    dispatch's own ``errors`` flag alone (no next-turn signal):
    errors => failure (decay); a CLEAN autonomous run => NEUTRAL no-op (T4).
    A clean Stop run carries no acceptance evidence, so it must NOT boost — the
    old "else boost" inflated success counts on every quiet session. It NEVER
    double-resolves: finalize_pending_outcomes atomically
    read-and-clears, so anything UserPromptSubmit already scored (and cleared)
    is simply absent here. Best-effort, silent, never raises.
    """
    try:
        from routing_outcome_score import apply_outcome, decision_row_exists
        from routing_outcome_state import (
            MAX_PENDING_AGE_SEC,
            finalize_pending_outcomes,
        )

        pending = finalize_pending_outcomes(session_id)
        if not pending:
            return
        import time

        # LOW-1: decision_row_exists no longer self-inits; ensure the schema
        # exists once before the per-key existence checks below.
        init_db()
        now = time.time()
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            if now - float(item.get("created", now)) > MAX_PENDING_AGE_SEC:
                continue  # drop abandoned provisional entry, do not score
            if not decision_row_exists(key):
                continue  # no row to score (orphaned); drop quietly at session end
            # Deterministic floor (T4): errors => failure (decay); a clean
            # autonomous run carries no acceptance evidence => NEUTRAL no-op.
            # Basis is the failure-axis label only (no next turn => a non-error
            # entry is default_no_complaint), recorded for route-health's
            # silent-success report. It never changes the boost/decay/no-op.
            errors = bool(item.get("errors"))
            outcome = "failure" if errors else "neutral"
            basis = "tool_errors_only" if errors else "default_no_complaint"
            apply_outcome(key, outcome, basis=basis)

    except Exception as e:
        hook_error("session-learning-recorder", e)


def is_substantive_session(event: dict) -> bool:
    """Determine if the session was substantive enough to warrant a gap check."""
    session_data = event.get("session_data", {})

    # Check tool call count
    tool_uses = session_data.get("tool_uses", [])
    if len(tool_uses) > SUBSTANTIVE_TOOL_THRESHOLD:
        return True

    # Check if files were modified
    files_modified = session_data.get("files_modified", [])
    if len(files_modified) > 0:
        return True

    return False


def main():
    """Check learning gap at session end."""
    try:
        event_data = read_stdin(timeout=2)
        if not event_data:
            empty_output(EVENT_NAME).print_and_exit()

        event = json.loads(event_data)
        session_id = event.get("session_id") or get_session_id()

        # Stop fallback: resolve routed dispatches the next-turn finalizer never
        # saw (autonomous / no-next-prompt runs). Runs BEFORE the trivial-session
        # gate so an outcome is recorded even on otherwise-quiet sessions.
        finalize_routing_outcomes(session_id)

        # Skip trivial sessions
        if not is_substantive_session(event):
            empty_output(EVENT_NAME).print_and_exit()

        learning_count = count_session_learnings(session_id)

        if learning_count == 0:
            print(
                "[learning-gap] Substantive session with 0 learnings recorded. Consider recording insights.",
                file=sys.stderr,
            )
        else:
            print(
                f"[learning-summary] Session recorded {learning_count} learnings",
                file=sys.stderr,
            )

        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("session-learning-recorder", e)
    empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
