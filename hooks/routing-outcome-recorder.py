#!/usr/bin/env python3
# hook-version: 1.2.0
"""
SubagentStop Hook: Routing Outcome Validator (action B, formerly /do Phase 5)

VALIDATES each routing decision's pending outcome — it NO LONGER applies
boost/decay. Scoring moved to the next-turn resolution point: UserPromptSubmit
(routing-outcome-finalizer.py) finalizes from tool-errors + user reaction +
re-route, with Stop (errored or stale) and SessionEnd fallbacks. See adr/learn-step-to-hook.md.

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

  - Reads the banners of a BACKGROUND dispatch: scores route-fit and records
    rightsizing. PostToolUse:Agent fires at launch for a background agent and
    carries no reply, so the banners are first readable here. The agent id
    joins this event to the route key
    (routing_outcome_state.register_async_dispatch). A foreground dispatch is
    never registered: routing-decision-recorder.py reads its banners. See
    hooks/lib/route_fit.py and hooks/lib/rightsizing_banner.py.

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

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from routing_outcome_state import (
    drain_pending_outcomes,
    requeue_pending_outcomes,
    revalidate_pending_outcomes,
)
from stdin_timeout import read_stdin

EVENT_NAME = "SubagentStop"


_SOURCE = "hook:routing-outcome-recorder"


def score_background_banners(event: dict, session_id: str) -> str | None:
    """Read the banners off a finished background dispatch's reply.

    Records the rightsizing banner and scores the route-fit banner. Returns the
    route-fit verdict, or None when this agent was not a registered background
    /do dispatch or its reply carries no route-fit banner. The claim removes
    the registration, so a re-delivered SubagentStop records nothing twice.
    """
    agent_id = event.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        return None
    from routing_outcome_state import claim_async_dispatch

    route = claim_async_dispatch(session_id, agent_id)
    if route is None:
        return None
    from route_fit import record_route_fit, subagent_final_text

    output = subagent_final_text(event)
    if not output:
        return None
    lowered = output.lower()
    if "rightsizing:" not in lowered and "route-fit:" not in lowered:
        return None  # no banner: pay no learning_db_v2 import
    from learning_db_v2 import init_db

    init_db()
    # Rightsizing first and on its own: a failure here must not cost the
    # route-fit verdict, and the reverse.
    try:
        from rightsizing_banner import record_rightsizing

        record_rightsizing(output, session_id, source=_SOURCE)
    except Exception as e:
        hook_error("routing-outcome-recorder:rightsizing", e)
    return record_route_fit(output, route["key"], session_id, route["decision_id"] or None)


def _max_requeue() -> int:
    """Re-queue cap (for debug logging). Mirrors routing_outcome_state."""
    from routing_outcome_state import MAX_REQUEUE_ATTEMPTS

    return MAX_REQUEUE_ATTEMPTS


_BYPASS_ENV = "ROUTING_OUTCOME_RECORDER_BYPASS"


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[routing-outcome-recorder] Bypassed via ROUTING_OUTCOME_RECORDER_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    try:
        raw = read_stdin(timeout=2)
        if not raw:
            return
        event = json.loads(raw)

        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type and event_type != EVENT_NAME:
            return

        session_id = event.get("session_id") or ""

        # Before the drain: a negative verdict discards its own pending entry,
        # and the drain below must not put it back.
        try:
            verdict = score_background_banners(event, session_id)
            if verdict and os.environ.get("CLAUDE_HOOKS_DEBUG"):
                print(f"[routing-outcome-recorder] route-fit: {verdict}", file=sys.stderr)
        except Exception as e:
            hook_error("routing-outcome-recorder:route-fit", e)

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
            # The drain already cleared these from state: one malformed entry
            # (not a dict, or a key that is not a string) is dropped here and
            # must not abort the loop and lose every entry after it.
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if not isinstance(key, str) or not key:
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
