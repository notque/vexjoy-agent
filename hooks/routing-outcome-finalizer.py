#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Routing Outcome Finalizer (next-turn resolution)

Resolves each /do-routed dispatch's outcome at the SINGLE point where the
next-turn signal exists: the user's next prompt. This is the deferred work the
SubagentStop validator can't do — a hook firing when a subagent stops cannot
see whether the USER accepted the result, asked for rework, or re-routed the
same intent. Those signals live in the NEXT user turn. This hook reads them.

Resolution per still-pending dispatch (drained atomically, scored ONCE):

    failure  = tool errors recorded for THIS dispatch  OR  clear user rejection
    success  = otherwise (acceptance, OR neutral / new topic — no complaint)

then boost (success) / decay (failure) the routing/{key} row, ONCE, and clear
the pending list so a re-delivered prompt resolves nothing further (idempotent).

HIGH-PRECISION FAILURE DETECTION (critical):
A FALSE failure poisons route-health worse than recording nothing — it decays a
route that actually worked. So failure fires ONLY on strong, unambiguous
markers (rejection/rework verbs, or a re-route of the same intent). Everything
else — including prompts that merely mention the word "wrong" in a NEW,
unrelated request — defaults to SUCCESS, matching the old LLM's "user accepted"
default. The marker sets below are module-level constants, conservative and
tunable. This is deliberately NOT full semantic judgment: it is a high-precision
deterministic detector that errs toward success on ambiguity.

Per-agent attribution is preserved: each pending entry carries its OWN tool
``errors`` flag (recorded by action A). The user reaction is a session-level
signal; combined per entry as ``errors OR rejection``.

Design Principles:
- SILENT (touches state/DB only; no context injection)
- Non-blocking: every RUNTIME path exits 0 (finally: sys.exit(0))
- Fast execution (<50ms target); lazy imports
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from routing_outcome_state import finalize_pending_outcomes
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# -----------------------------------------------------------------------------
# Reaction marker sets (module-level constants — conservative + tunable).
#
# REJECTION markers fire FAILURE. Kept deliberately strong/unambiguous: each is
# a phrase a user uses to reject or demand rework of the immediately-prior work.
# Matched as whole-phrase / word-boundary regexes so a substring like the word
# "wrong" inside an unrelated new request does NOT trip them (see the benign
# "wrong" non-decay test). Tune by adding/removing entries here.
# -----------------------------------------------------------------------------
_REJECTION_PATTERNS = [
    r"that'?s (wrong|worse|broken|not (right|what i wanted))",
    r"this (is|isn'?t) (wrong|worse|broken|not (right|what i wanted))",
    r"\bnot what i (wanted|asked for)\b",
    r"\b(redo|re-?do) (it|that|this)\b",
    r"\b(revert|undo|roll ?back) (it|that|this|your|the (change|edit|commit))\b",
    r"\bthat (didn'?t|did not) work\b",
    r"\bthis (didn'?t|did not) work\b",
    r"\b(start over|try again)\b",
    r"\byou (broke|messed up|got it wrong)\b",
    r"\b(no,? that'?s|nope,? that'?s)\b",
    r"\bwrong (agent|skill|approach|route|routing)\b",
    r"\b(fix|undo) (your|the) (mistake|error|mess)\b",
]

# RE-ROUTE markers fire FAILURE too: the user redirects the SAME intent to a
# different agent/skill/approach, i.e. the route was wrong. Distinct from a
# brand-new unrelated request (which is neutral => success).
_REROUTE_PATTERNS = [
    r"\b(use|try|switch to|route (this )?to) (a )?different (agent|skill|approach)\b",
    r"\bwrong (agent|skill|route|routing)\b",
    r"\bre-?route\b",
    r"\bthat'?s the wrong (agent|skill|approach)\b",
    r"\b(should|shouldn'?t) (have )?(use|used|been) .*(agent|skill)\b",
]

# ACCEPTANCE markers are documented for clarity / future tuning, but they are NOT
# required: acceptance and neutral both resolve to SUCCESS. They exist so the
# classifier can be made stricter later without restructuring.
_ACCEPTANCE_PATTERNS = [
    r"\b(thanks|thank you|great|perfect|looks good|lgtm|nice work|well done)\b",
    r"\b(merge it|ship it|ship that|approve|approved)\b",
]

_REJECTION_RE = re.compile("|".join(_REJECTION_PATTERNS), re.IGNORECASE)
_REROUTE_RE = re.compile("|".join(_REROUTE_PATTERNS), re.IGNORECASE)


def is_rejection(prompt: str) -> bool:
    """High-precision: True only on a clear rejection / rework / re-route signal.

    Conservative by design — ambiguous prompts (a NEW request that merely
    contains the word "wrong") return False so the prior dispatch is not falsely
    decayed. Returns False on empty / non-string input.
    """
    if not prompt or not isinstance(prompt, str):
        return False
    return bool(_REJECTION_RE.search(prompt) or _REROUTE_RE.search(prompt))


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
        # Atomic read-AND-clear: makes finalization idempotent — a re-delivered
        # or duplicate prompt finds an empty pending list and scores nothing.
        pending = finalize_pending_outcomes(session_id)
        if not pending:
            return  # no routed dispatches awaiting resolution this turn

        prompt = (event.get("prompt") or "").strip()
        rejected = is_rejection(prompt)

        # Lazy: only import the scorer (and thus learning_db_v2) when there is
        # actually something to resolve.
        import time

        from routing_outcome_score import apply_outcome, decision_row_exists
        from routing_outcome_state import MAX_PENDING_AGE_SEC, revalidate_pending_outcomes

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        now = time.time()
        seen_keys: set[str] = set()
        to_revalidate: list[dict] = []
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            # Drop abandoned provisional entries; never score a stale one.
            created = float(item.get("created", now))
            if now - created > MAX_PENDING_AGE_SEC:
                continue
            # A row whose decision write is still not visible (rare at this
            # point) is put back so a later resolver scores it — never dropped,
            # never double-counted.
            if not decision_row_exists(key):
                to_revalidate.append(item)
                continue
            # Per-agent attribution: THIS dispatch's own error flag, OR a
            # session-level clear rejection => failure. Else success.
            failure = bool(item.get("errors")) or rejected
            new_conf = apply_outcome(key, failure)
            seen_keys.add(key)
            if debug:
                outcome = "failure" if failure else "success"
                reason = "tool-errors" if item.get("errors") else ("rejection" if rejected else "accepted/neutral")
                print(
                    f"[routing-outcome-finalizer] {outcome} routing/{key} ({reason}) conf={new_conf:.4f}",
                    file=sys.stderr,
                )

        if to_revalidate:
            revalidate_pending_outcomes(session_id, to_revalidate)

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[routing-outcome-finalizer] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
