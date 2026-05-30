#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SubagentStop Hook: Routing Outcome Recorder (action B, formerly /do Phase 5)

Records whether each routing decision succeeded or failed, replacing the
hand-run `learning-db.py record-routing-outcome ...` step from /do Phase 5.

Ordering dependency (honored structurally): PostToolUse:Agent fires BEFORE
SubagentStop, so the decision row written by routing-decision-recorder.py
(action A) is already committed when this hook runs. A drops a per-session
pending-outcome bridge entry (routing key + observed error flag); this hook
drains it and applies the same confidence semantics the old CLI used:
  - no errors / no re-route -> boost_confidence("routing", key, 0.05)  [success]
  - errors detected         -> decay_confidence("routing", key, 0.08)  [failure]

SubagentStop carries transcript_path; we scan it for additional tool-error
evidence to refine the verdict beyond what A observed.

----------------------------------------------------------------------------
FIDELITY TRADEOFF (read before changing the verdict logic)

A hook CANNOT observe what the old LLM Phase 5 could: "the user rejected the
result," "the user asked for rework next turn," "the user accepted it." Those
signals live in the NEXT user turn, which does not exist when SubagentStop
fires. So this hook uses a DETERMINISTIC FLOOR:
    success = no tool errors AND no re-route observed in this dispatch
    failure = tool errors detected
This is a strictly LOWER-FIDELITY proxy than the old LLM evaluation. It will
miss silent-rejection failures (clean tool stream, user discards the work) and
may score a recovered-from-error run as failure. Accepted deliberately: an
automatic signal on every route beats a perfect signal skipped half the time.
See adr/learn-step-to-hook.md.
----------------------------------------------------------------------------

Crash-safe on missing decision record: the old CLI exits 1 when no decision
row exists for the key. boost_confidence/decay_confidence are no-ops on a
missing row (they return 0.0), so we DON'T rely on the return value to tell
"missing row" from "decayed to zero" — both are 0.0. Instead we run a cheap
row-existence pre-check (decision_row_exists) BEFORE calling boost/decay: no
row => skip, never crash; row present => score it, even when its confidence is
a legitimate 0.0. (The hook exits 0 regardless, per the always-exit-0 contract.)

Design Principles:
- SILENT (records to DB, stderr only on debug)
- Non-blocking (always exits 0)
- Fast execution (<50ms target); lazy imports
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from routing_outcome_state import drain_pending_outcomes
from stdin_timeout import read_stdin

EVENT_NAME = "SubagentStop"

# Tool-error indicators scanned in the subagent transcript.
_ERROR_INDICATORS = (
    "permission denied",
    "no such file",
    "command not found",
    "traceback (most recent call last)",
    "fatal:",
    "syntaxerror",
)


def transcript_has_errors(transcript_path: str) -> bool:
    """Best-effort scan of the subagent transcript for tool-error evidence."""
    if not transcript_path:
        return False
    path = Path(transcript_path)
    if not path.exists() or not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return False
    return any(ind in content for ind in _ERROR_INDICATORS)


def decision_row_exists(key: str) -> bool:
    """True iff a routing decision row was already written for ``key``.

    Row-existence pre-check that replaces the None-return sentinel: it lets the
    caller distinguish "no decision row" (skip) from "row decayed to 0.0"
    (score it) WITHOUT relying on boost/decay's return value, which is 0.0 in
    both cases. Reads only the routing/effectiveness slice, including
    test-source and graduated rows so the outcome path matches what action A
    wrote.
    """
    from learning_db_v2 import query_learnings

    rows = query_learnings(
        topic="routing",
        category="effectiveness",
        exclude_graduated=False,
        exclude_test_sources=False,
        limit=1000,
    )
    return any(r.get("key") == key for r in rows)


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

        # Transcript-level error evidence applies to this subagent run.
        transcript_errors = transcript_has_errors(event.get("transcript_path", ""))

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            if not decision_row_exists(key):
                # No decision row for this key — skip, never crash. (Pre-check,
                # not a 0.0-return sentinel: a row at confidence 0.0 still scores.)
                if debug:
                    print(
                        f"[routing-outcome-recorder] no decision row for '{key}' — skipped",
                        file=sys.stderr,
                    )
                continue
            failure = bool(item.get("errors")) or transcript_errors
            new_conf = apply_outcome(key, failure)
            if debug:
                outcome = "failure" if failure else "success"
                print(
                    f"[routing-outcome-recorder] {outcome} routing/{key} conf={new_conf:.4f}",
                    file=sys.stderr,
                )

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[routing-outcome-recorder] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
