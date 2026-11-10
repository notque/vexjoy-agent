#!/usr/bin/env python3
# hook-version: 2.1.1
"""
Stop / SessionEnd Hook: Routing-Outcome Fallback

Resolves routed dispatches that the next-turn finalizer will never see.

Stop fires after EVERY turn, before the user's next message exists. The
UserPromptSubmit finalizer (routing-outcome-finalizer.py) needs that message to
read acceptance or rejection. Draining every pending entry on Stop scored 291
of 291 outcomes as `default_no_complaint` and left the finalizer nothing. So:

| Event      | Resolves                                             | Leaves pending |
|------------|------------------------------------------------------|----------------|
| Stop       | errored entries; entries older than STOP_STALE_AGE_SEC | everything else |
| SessionEnd | every pending entry                                  | nothing        |

`.claude/settings.json` registers this hook under both `Stop` and `SessionEnd`.
Where a runtime mirrors only the `Stop` entry (Codex), a clean entry from a
session's last turn stays pending and its decision row keeps a NULL outcome.

An errored entry scores failure whatever the user says next, so Stop resolves
it at once. A stale entry means the session ran STOP_STALE_AGE_SEC with no user
turn. SessionEnd is the true session end: no next prompt can come.

Outcome is the deterministic floor, this dispatch's own `errors` flag:
errors => failure (decay); clean => NEUTRAL no-op. A clean run carries no
acceptance evidence, so it never boosts.

Each resolved entry is written through `record_resolved_outcome`: confidence,
basis counter, route-events.jsonl, and the outcome on its
`evidence_route_decisions` row.

Renamed from session-learning-recorder.py, which mixed this routing telemetry
with a learning-gap warning. The learning loop is retired; this fallback is
routing telemetry and stays.

Design Principles:
- Routing telemetry only — records no learnings, injects no context
- Silent (emits only the empty hook envelope)
- Non-blocking (always exits 0)
- Fast execution (<50ms target)
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import sys
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error
from stdin_timeout import read_stdin

EVENT_NAME = "Stop"
SESSION_END_EVENT = "SessionEnd"
_SOURCE = "hook:routing-outcome-stop-fallback"


def finalize_routing_outcomes(session_id: str, session_end: bool = False) -> int:
    """Resolve the pending dispatches this event may resolve. Returns the count.

    ``session_end=False`` (Stop): take only errored and stale entries; clean
    recent entries stay pending for the UserPromptSubmit finalizer.
    ``session_end=True`` (SessionEnd): take every pending entry.

    Never double-resolves: both takes remove entries under the state lock, so
    anything a resolver already scored is absent here. Best-effort, silent,
    never raises.
    """
    resolved = 0
    try:
        from routing_outcome_state import (
            MAX_PENDING_AGE_SEC,
            STOP_STALE_AGE_SEC,
            finalize_pending_outcomes,
            record_outcome_history,
            take_resolvable_pending_outcomes,
        )

        if session_end:
            pending = finalize_pending_outcomes(session_id)
        else:
            pending = take_resolvable_pending_outcomes(session_id, STOP_STALE_AGE_SEC)
        if not pending:
            return 0
        import time

        # Lazy: a Stop with nothing to resolve pays no learning_db_v2 import.
        from learning_db_v2 import init_db
        from routing_outcome_score import decision_row_exists, record_resolved_outcome

        # LOW-1: decision_row_exists no longer self-inits; ensure the schema
        # exists once before the per-key existence checks below.
        init_db()
        now = time.time()
        history_updates: dict[str, str] = {}
        try:
            for item in pending:
                # Every entry here is already cleared from state. One bad entry
                # is dropped on its own: it must not abort the loop and lose
                # the entries after it.
                if not isinstance(item, dict):
                    continue  # malformed entry: do not score
                key = item.get("key")
                if not isinstance(key, str) or not key:
                    continue  # a key that is not a string names no route
                try:
                    created = float(item.get("created", now))
                except (TypeError, ValueError):
                    continue  # malformed entry: drop, do not score
                if now - created > MAX_PENDING_AGE_SEC:
                    continue  # drop abandoned provisional entry, do not score
                # Deterministic floor (T4): errors => failure (decay); a clean
                # run carries no acceptance evidence => NEUTRAL no-op.
                # Basis is the failure-axis label only (no next turn => a non-error
                # entry is default_no_complaint), recorded for route-health's
                # silent-success report.
                errors = bool(item.get("errors"))
                if errors:
                    reason = "tool-errors"
                elif session_end:
                    reason = "session-end-no-reaction"
                else:
                    reason = "stale-no-reaction"
                decision_id = item.get("decision_id")
                try:
                    if not decision_row_exists(key):
                        continue  # no row to score (orphaned); drop quietly
                    record_resolved_outcome(
                        session_id=session_id,
                        key=key,
                        outcome="failure" if errors else "neutral",
                        basis="tool_errors_only" if errors else "default_no_complaint",
                        reason=reason,
                        source=_SOURCE,
                        decision_id=decision_id if isinstance(decision_id, str) and decision_id else None,
                    )
                except Exception as e:
                    hook_error("routing-outcome-stop-fallback:entry", e)
                    continue
                resolved += 1
                # Feed the finalizer's repeat-dispatch check, as the finalizer does:
                # a failure resolved here must block the next weak boost for its
                # key. Failure wins over a clean same-key entry in one run.
                if history_updates.get(key) != "failure":
                    history_updates[key] = "failure" if errors else "neutral"
        finally:
            # Written even when the loop stops early: a failure already
            # resolved above must still reach the per-session history.
            record_outcome_history(session_id, history_updates)

    except Exception as e:
        hook_error("routing-outcome-stop-fallback", e)
    return resolved


_BYPASS_ENV = "ROUTING_OUTCOME_STOP_FALLBACK_BYPASS"


def main():
    """Resolve the pending routing outcomes this Stop or SessionEnd may resolve."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(
                "[routing-outcome-stop-fallback] Bypassed via ROUTING_OUTCOME_STOP_FALLBACK_BYPASS=1", file=sys.stderr
            )
        sys.exit(0)

    session_end = False
    try:
        event_data = read_stdin(timeout=2)
        if event_data:
            event = json.loads(event_data)
            session_end = event.get("hook_event_name") == SESSION_END_EVENT
            finalize_routing_outcomes(get_session_id(event), session_end=session_end)
    except Exception as e:
        hook_error("routing-outcome-stop-fallback", e)
    if not session_end:  # SessionEnd takes no hook output; print nothing.
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)  # Never block
