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
``errors`` flag (recorded by action A). The user reaction is a turn-level signal
that can only be ATTRIBUTED when exactly ONE dispatch is pending this turn —
/do Phase 4 fans out multiple agents per turn, and a single "that's wrong"
cannot be pinned to one of N parallel siblings. So:

  - single pending dispatch  => failure = ``errors OR rejection``
  - >1 pending dispatches     => failure = ``errors`` per entry ONLY; the
                                  turn-level reaction is IGNORED (it would
                                  otherwise broadcast a decay across correct
                                  siblings — the sibling-misattribution bug on
                                  the reaction axis).

This makes the parallel-fan-out case at-least-as-good as the old proxy (never
worse): clean siblings default to success exactly as the deterministic floor
did, while a genuine single-dispatch rejection is still captured.

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
#
# CLAUSE-SCOPING (HIGH-2 precision): rejection/re-route markers are tested ONLY
# against the FIRST clause of the prompt (split on `. ; \n`). The first clause is
# the user's immediate reaction to the prior work; a later clause is new work,
# not a complaint. So "thanks, that worked. redo it for the other file" or
# "great, now start over on the README" score SUCCESS — the reaction clause is
# acceptance/neutral; "redo it"/"start over" land in a SEPARATE clause that
# describes the NEXT task. Greedy `.*` in re-route patterns is replaced with the
# bounded `[^.;\n]{0,40}` so a reroute marker cannot span unrelated clauses.
#
# ACCEPTANCE PRECEDENCE: if an acceptance marker appears in the first clause, the
# turn scores SUCCESS even when a later clause contains "redo/start over" (that's
# new work, not a complaint about the prior route).
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
# brand-new unrelated request (which is neutral => success). Bounded
# `[^.;\n]{0,40}` (NOT greedy `.*`) keeps a marker from spanning unrelated clauses.
_REROUTE_PATTERNS = [
    r"\b(use|try|switch to|route (this )?to) (a )?different (agent|skill|approach)\b",
    r"\bwrong (agent|skill|route|routing)\b",
    r"\bre-?route\b",
    r"\bthat'?s the wrong (agent|skill|approach)\b",
    r"\b(should|shouldn'?t) (have )?(use|used|been) [^.;\n]{0,40}(agent|skill)\b",
]

# ACCEPTANCE markers: when one appears in the FIRST clause it takes precedence
# over any later rejection-shaped clause (acceptance precedence). Word-boundary
# anchored so a substring cannot trip them.
_ACCEPTANCE_PATTERNS = [
    r"\b(thanks|thank you|thx|great|perfect|looks good|lgtm|nice work|well done|that worked)\b",
    r"\b(merge it|ship it|ship that|approve|approved)\b",
]

_REJECTION_RE = re.compile("|".join(_REJECTION_PATTERNS), re.IGNORECASE)
_REROUTE_RE = re.compile("|".join(_REROUTE_PATTERNS), re.IGNORECASE)
_ACCEPTANCE_RE = re.compile("|".join(_ACCEPTANCE_PATTERNS), re.IGNORECASE)

# Clause boundary: split on sentence/clause terminators so only the user's
# immediate reaction (the first clause) is tested for rejection.
_CLAUSE_SPLIT_RE = re.compile(r"[.;\n]")


def _first_clause(prompt: str) -> str:
    """The user's immediate reaction: text up to the first `. ; \\n` terminator.

    Empty/whitespace leading clauses are skipped so a prompt that opens with a
    bare terminator still yields the first substantive clause.
    """
    for part in _CLAUSE_SPLIT_RE.split(prompt):
        if part.strip():
            return part
    return prompt


def is_rejection(prompt: str) -> bool:
    """High-precision: True only on a clear rejection / rework / re-route signal
    in the user's IMMEDIATE reaction (the first clause).

    Precision rules (HIGH-2):
    - Clause-scoped: only the FIRST clause is tested. A rejection verb in a later
      clause ("thanks. redo it for the other file") is NEW work, not a complaint.
    - Acceptance precedence: an acceptance marker in the first clause => not a
      rejection, even if a later clause looks rework-shaped.
    Conservative by design — ambiguous prompts (a NEW request that merely
    contains the word "wrong") return False. Returns False on empty / non-string
    input.
    """
    if not prompt or not isinstance(prompt, str):
        return False
    first = _first_clause(prompt)
    if _ACCEPTANCE_RE.search(first):
        return False  # acceptance precedence — later "redo" clauses are new work
    return bool(_REJECTION_RE.search(first) or _REROUTE_RE.search(first))


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

        from learning_db_v2 import init_db
        from routing_outcome_score import apply_outcome, decision_row_exists
        from routing_outcome_state import (
            MAX_PENDING_AGE_SEC,
            requeue_pending_outcomes,
            revalidate_pending_outcomes,
        )

        # LOW-1: init the schema ONCE per scoring block, not per key
        # (decision_row_exists no longer calls init_db itself).
        init_db()
        now = time.time()

        # HIGH-1: a turn-level rejection can only be ATTRIBUTED to a route when
        # exactly ONE dispatch is pending resolution this turn. /do Phase 4 fans
        # out multiple agents per turn; a single "that's wrong" cannot be pinned
        # to one of N parallel siblings, so broadcasting it would re-decay
        # correct routes (the sibling-misattribution bug on the reaction axis).
        # Rule: when >1 dispatches are pending, IGNORE the turn-level reaction and
        # resolve each entry by its OWN per-entry `errors` flag (an entry with
        # tool errors still fails; a clean sibling defaults to success). The
        # reaction is applied ONLY in the unambiguous single-dispatch case. Stale
        # entries (dropped by the age check below) do not count toward the live
        # pending population for this decision.
        live = [it for it in pending if it.get("key") and (now - float(it.get("created", now))) <= MAX_PENDING_AGE_SEC]
        attributable = len(live) == 1

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        to_revalidate: list[dict] = []
        to_requeue: list[dict] = []
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            # Drop abandoned provisional entries; never score a stale one.
            created = float(item.get("created", now))
            if now - created > MAX_PENDING_AGE_SEC:
                continue
            # MED-1: a pending entry whose decision row was NEVER written is an
            # orphan — route it through the attempt-bounded requeue (increments
            # attempts, dropped at MAX_REQUEUE_ATTEMPTS) so a never-written-row
            # key cannot linger up to 24h. `revalidate` (preserves attempts) is
            # reserved for entries whose row IS visible but aren't finalizable.
            # At UserPromptSubmit every visible-row entry IS finalizable, so the
            # only no-score path here is the orphan path => requeue.
            if not decision_row_exists(key):
                to_requeue.append(item)
                continue
            # Per-entry attribution (HIGH-1): own error flag => failure. The
            # turn-level rejection is OR'd in ONLY when it is attributable (a
            # single pending dispatch this turn); with >1 pending it is ignored.
            reaction_failure = rejected if attributable else False
            failure = bool(item.get("errors")) or reaction_failure
            new_conf = apply_outcome(key, failure)
            if debug:
                outcome = "failure" if failure else "success"
                if item.get("errors"):
                    reason = "tool-errors"
                elif reaction_failure:
                    reason = "rejection"
                elif rejected and not attributable:
                    reason = "rejection-ignored-multi-dispatch"
                else:
                    reason = "accepted/neutral"
                print(
                    f"[routing-outcome-finalizer] {outcome} routing/{key} ({reason}) conf={new_conf:.4f}",
                    file=sys.stderr,
                )

        if to_requeue:
            requeue_pending_outcomes(session_id, to_requeue)
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
