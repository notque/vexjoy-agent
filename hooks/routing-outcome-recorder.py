#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStop Hook: Routing Outcome Recorder (action B, formerly /do Phase 5)

Records whether each routing decision succeeded or failed, replacing the
hand-run `learning-db.py record-routing-outcome ...` step from /do Phase 5.

Ordering dependency (HIGH, A-before-B): PostToolUse:Agent fires BEFORE
SubagentStop, so the decision row written by routing-decision-recorder.py
(action A) is NORMALLY committed when this hook runs. A drops a per-session
pending-outcome bridge entry (routing key + observed error flag); this hook
drains it and applies the same confidence semantics the old CLI used:
  - no errors -> boost_confidence("routing", key, 0.05)  [success]
  - errors    -> decay_confidence("routing", key, 0.08)  [failure]
If a pending key is drained before its decision row is visible (mistiming), the
entry is RE-QUEUED (bounded, requeue_pending_outcomes) so a late-landing row
gets scored on a subsequent stop instead of being silently dropped.

Verdict source (HIGH, per-agent attribution): each pending entry carries its
OWN ``errors`` flag, recorded by action A from THAT dispatch's structured tool
result (hook_utils.is_tool_error). We score each key by its own flag. We do NOT
scan the whole subagent transcript for substrings and OR that into every key's
verdict — that broadcast (a) cross-attributes one agent's error onto sibling
keys drained from the same session, and (b) false-positives on prose that
merely mentions "permission denied"/"traceback". The structured per-agent flag
is strictly more accurate, so the transcript substring scan was DROPPED. See
adr/learn-step-to-hook.md (HIGH-2 attribution decision).

----------------------------------------------------------------------------
FIDELITY TRADEOFF (read before changing the verdict logic)

A hook CANNOT observe what the old LLM Phase 5 could: "the user rejected the
result," "the user asked for rework next turn," "the user accepted it." Those
signals live in the NEXT user turn, which does not exist when SubagentStop
fires. So this hook uses a DETERMINISTIC FLOOR, scored PER AGENT from that
dispatch's own recorded error flag:
    success = no tool errors recorded for this dispatch
    failure = tool errors recorded for this dispatch
This is a strictly LOWER-FIDELITY proxy than the old LLM evaluation. It will
miss silent-rejection failures (clean tool stream, user discards the work) and
may score a recovered-from-error run as failure. Accepted deliberately: an
automatic signal on every route beats a perfect signal skipped half the time.
See adr/learn-step-to-hook.md.
----------------------------------------------------------------------------

Crash-safe on missing decision record: the old CLI exits 1 when no decision
row exists for the key. boost_confidence/decay_confidence are no-ops on a
missing row (they return 0.0), so we DON'T rely on the return value to tell
"missing row" from "decayed to zero" — both are 0.0. Instead we run a KEYED
row-existence pre-check (decision_row_exists) BEFORE calling boost/decay: no
row => re-queue (bounded), never crash; row present => score it, even when its
confidence is a legitimate 0.0. The pre-check is an exact (topic, key) lookup
with NO row cap — a prior top-1000 confidence-DESC scan dropped decayed rows
once the table grew past 1000 (data loss). The hook exits 0 regardless.

Design Principles:
- SILENT (records to DB, stderr only on debug)
- Non-blocking: every RUNTIME path after module load exits 0 (the finally:
  sys.exit(0)). A failure at module-load time (import error) is not caught here
  and is treated as non-blocking by the harness.
- Fast execution (<50ms target); lazy imports
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from routing_outcome_state import drain_pending_outcomes, requeue_pending_outcomes
from stdin_timeout import read_stdin

EVENT_NAME = "SubagentStop"


def decision_row_exists(key: str) -> bool:
    """True iff a routing decision row was already written for ``key``.

    KEYED existence check (CRITICAL fix). The old implementation paged the
    routing/effectiveness slice via query_learnings(..., limit=1000), which
    orders ``confidence DESC``. Once that table exceeds 1000 rows a decayed
    (low-confidence) decision row falls outside the window, so this returned
    False and the outcome was silently skipped — defeating the pre-check and
    losing data. We now do an exact-key lookup with no row cap.

    query_learnings has no key filter, so we run a direct READ-ONLY,
    parameterized SELECT against the same learning.db (get_db_path), matching
    the (topic, key) UNIQUE constraint action A writes on. We deliberately do
    NOT edit learning_db_v2.py — only read its DB path + open a connection.
    Category is included to match action A's exact write (always
    'effectiveness'); topic+key alone is unique, so category only narrows.
    """
    from learning_db_v2 import get_db_path, init_db

    try:
        init_db()  # ensure schema/file exist before SELECT
        import sqlite3

        conn = sqlite3.connect(get_db_path(), timeout=5.0)
        try:
            row = conn.execute(
                "SELECT 1 FROM learnings WHERE topic = ? AND key = ? AND category = ? LIMIT 1",
                ("routing", key, "effectiveness"),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except Exception:
        # Best-effort: on any read failure, treat as "exists unknown" => do not
        # score (skip), never crash. The pending entry is re-queued by main()
        # so a transient read failure does not lose the outcome.
        return False


def _max_requeue() -> int:
    """Re-queue cap (for debug logging). Mirrors routing_outcome_state."""
    from routing_outcome_state import MAX_REQUEUE_ATTEMPTS

    return MAX_REQUEUE_ATTEMPTS


def apply_outcome(key: str, failure: bool) -> float:
    """Boost (success) or decay (failure) the routing row. Returns new confidence.

    Caller MUST gate this on decision_row_exists(key): boost/decay are no-ops
    on a missing row and return 0.0, indistinguishable from a legitimate
    decayed-to-zero confidence.
    """
    from learning_db_v2 import boost_confidence, decay_confidence

    if failure:
        return decay_confidence("routing", key, delta=0.08)
    return boost_confidence("routing", key, delta=0.05)


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
            return  # nothing to score

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        # HIGH (A-before-B): pending entries whose decision row is not yet
        # visible are re-queued (bounded) so a late-landing row gets scored on a
        # subsequent stop, rather than being dropped.
        to_requeue: list[dict] = []
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            if not decision_row_exists(key):
                # Decision row not visible yet (ordering mistiming) OR a read
                # failure. Re-queue (bounded) instead of dropping; never crash.
                to_requeue.append(item)
                if debug:
                    print(
                        f"[routing-outcome-recorder] no decision row for '{key}' — re-queued "
                        f"(attempt {int(item.get('attempts', 0)) + 1}/{_max_requeue()})",
                        file=sys.stderr,
                    )
                continue
            # Per-agent attribution (HIGH-2): score by THIS dispatch's own error
            # flag only. No session-wide transcript scan broadcast across keys.
            failure = bool(item.get("errors"))
            new_conf = apply_outcome(key, failure)
            if debug:
                outcome = "failure" if failure else "success"
                print(
                    f"[routing-outcome-recorder] {outcome} routing/{key} conf={new_conf:.4f}",
                    file=sys.stderr,
                )

        if to_requeue:
            requeue_pending_outcomes(session_id, to_requeue)

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[routing-outcome-recorder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
