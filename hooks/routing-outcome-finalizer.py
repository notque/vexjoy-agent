#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: Routing Outcome Finalizer (next-turn resolution)

Resolves each /do-routed dispatch's outcome at the SINGLE point where the
next-turn signal exists: the user's next prompt. This is the deferred work the
SubagentStop validator can't do — a hook firing when a subagent stops cannot
see whether the USER accepted the result, asked for rework, or re-routed the
same intent. Those signals live in the NEXT user turn. This hook reads them.

Resolution per still-pending dispatch (drained atomically, scored ONCE) —
THREE-WAY (T4):

    failure  = tool errors recorded for THIS dispatch  OR  clear user rejection
    success  = explicit acceptance / affirmation of the prior work
    neutral  = otherwise (unrelated / new-topic next prompt — no complaint, no
               acceptance) => NO-OP: no boost, no decay, no count change

then boost (success) / decay (failure) / no-op (neutral) the routing/{key} row,
ONCE, and clear the pending list so a re-delivered prompt resolves nothing
further (idempotent).

SIGNAL FIDELITY (T4): the prior detector boosted EVERYTHING that was not an
unambiguous failure — including neutral new-topic prompts — inflating success
counts so no real signal could surface. Success now requires a POSITIVE marker;
a new-topic prompt is neutral, leaving room for future negatives.

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
# GOVERNING PRINCIPLE — ASYMMETRIC COSTS => NEAR-ZERO FALSE POSITIVES:
# A MISSED rejection falls back to SUCCESS = the old proxy floor (never worse).
# A FALSE rejection decays a route that actually WORKED = strictly worse than the
# proxy. So the bar is near-zero false-positives; recall is secondary. When in
# any doubt, classify SUCCESS. Only decay on an unambiguous complaint about the
# just-completed work.
#
# PROSE RE-ROUTE DETECTION REMOVED (HIGH-2): the old `_REROUTE_PATTERNS` ("use a
# different approach", "should have used … agent/skill", …) were the biggest
# false-positive source — they fired on instructional/spec prose like "explain
# when to use a different approach", "we should have used a cache, and document
# the skill matrix", "try a different approach to memoization". Re-route is rare
# and unreliable to detect from prose; capturing it is not worth poisoning
# route-health. The ONLY surviving re-route signal is the complaint-anchored
# literal "wrong agent/skill/route/routing" (it requires the word "wrong"), kept
# inside the rejection set below.
#
# REJECTION markers fire FAILURE. Each is an unambiguous complaint about the
# immediately-prior work, matched as whole-phrase / word-boundary regexes so a
# substring (e.g. "wrong" inside an unrelated new request) does NOT trip them.
# "revert/undo/roll back" require a complaint OBJECT (it|that|this|your) — never
# the spec-shaped "the change" — so "undo the change only if the checksum fails"
# / "roll back the change on failure" are NOT complaints.
#
# CLAUSE-SCOPING: rejection markers are tested ONLY against the FIRST clause of
# the prompt (split on `, . ; \n`). The first clause is the user's immediate
# reaction; a later clause is new work. So "thanks, that worked. redo it for the
# other file" and "we should have used a cache, and document the skill matrix"
# score SUCCESS.
#
# INSTRUCTIONAL/CONDITIONAL EXCLUSION: if the first clause carries an
# instructional / conditional / explanatory cue — should, when, if, whether,
# explain, document, how to, can you, try — the clause is a feature request or
# spec, NOT a complaint, so it scores SUCCESS regardless of marker presence.
# ("the migration should roll back the change on failure" is a requirement;
# "document when to use a different agent" is a docs task.)
#
# ACCEPTANCE PRECEDENCE: if an acceptance marker appears in the first clause, the
# turn scores SUCCESS even when a later clause looks rework-shaped. (Bare rework
# verbs "redo/start over/try again" no longer fire at all — see C1 note below —
# so acceptance precedence now guards only genuine first-clause complaints.)
# -----------------------------------------------------------------------------
_REJECTION_PATTERNS = [
    r"that'?s (wrong|worse|broken|not (right|what i wanted))",
    r"this (is|isn'?t) (wrong|worse|broken|not (right|what i wanted))",
    r"\bnot what i (wanted|asked for)\b",
    # NOTE: the STANDALONE rework arms `\b(redo|re-?do) (it|that|this)\b` and
    # `\b(start over|try again)\b` were REMOVED (codex C1). Bare imperatives like
    # "redo it for the other file", "start over on the README", "try again with a
    # smaller batch size" are benign FOLLOW-UPS (apply same work elsewhere / new
    # task / parameter change), NOT complaints about the just-completed route, so
    # firing FAILURE on them decayed a route that SUCCEEDED — strictly worse than
    # the proxy floor. Recall loss is the safe direction (asymmetric costs). Genuine
    # complaints that happen to contain these verbs still fire via their COMPLAINT
    # clause: "that's wrong, redo it" → `that's wrong`; "no, that's not what I asked
    # for" → leading-no arm; "revert that, you broke the build" → `revert that` /
    # `you broke`.
    # Complaint-anchored only: object must be it/that/this/your (the prior work),
    # NOT "the change" — that is a conditional/spec use ("roll back the change on
    # failure", "undo the change only if …"), excluded by the cue guard too.
    r"\b(revert|undo|roll ?back) (it|that|this|your)\b",
    r"\bthat (didn'?t|did not) work\b",
    r"\bthis (didn'?t|did not) work\b",
    r"\byou (broke|messed up|got it wrong)\b",
    # Sole surviving re-route signal: anchored on the literal complaint "wrong".
    r"\bwrong (agent|skill|route|routing)\b",
    r"\b(fix|undo) (your|the) (mistake|error|mess)\b",
]

# ACCEPTANCE markers: when one appears in the FIRST clause it takes precedence
# over any later rejection-shaped clause (acceptance precedence). Word-boundary
# anchored so a substring cannot trip them.
_ACCEPTANCE_PATTERNS = [
    r"\b(thanks|thank you|thx|great|perfect|looks good|lgtm|nice work|well done|that worked)\b",
    r"\b(works now|that fixed it|that did it|good job)\b",
    r"\b(merge it|ship it|ship that|approve|approved)\b",
]

# INSTRUCTIONAL / CONDITIONAL / EXPLANATORY cues. A first clause carrying any of
# these describes a feature/spec/docs task or a conditional, NOT a complaint
# about the prior work => SUCCESS. `if` is matched at a word boundary that also
# allows a leading non-word char so "only if" / "if the" are caught.
_INSTRUCTIONAL_CUE_PATTERNS = [
    r"\b(should|when|whether|explain|document|how to|can you|try)\b",
    r"(?:^|\W)if\b",
]

# ACCEPTANCE-BOOST GUARDS (precision over recall — mirror of the rejection
# detector's asymmetric-cost rule, inverted): a MISSED acceptance stays NEUTRAL,
# the T4 floor (no harm); a FALSE acceptance boosts a route on a NEW-task prompt,
# inflating exactly the silent-success share acceptance detection exists to
# shrink. So the boost path (`is_acceptance`) fires only when the acceptance
# clause LEADS the prompt (first clause) or stands alone, AND:
#   - no negation token in the clause ("not perfect", "doesn't work")
#   - the clause does not open with a task verb ("make a great landing page",
#     "write the perfect README" — markers buried in new task text)
#   - no instructional/conditional cue ("can you make it perfect", "if it
#     looks good then merge")
#   - the clause is terse (<= _MAX_ACCEPTANCE_CLAUSE_WORDS words) — genuine
#     reactions are short; long clauses are task descriptions.
# The looser `_ACCEPTANCE_RE` alone still serves acceptance PRECEDENCE inside
# `is_rejection` (there a loose match only prevents a decay — the safe side).
_NEGATION_RE = re.compile(
    r"\b(not|no|never|hardly|isn'?t|wasn'?t|aren'?t|doesn'?t|don'?t|didn'?t|can'?t|won'?t)\b",
    re.IGNORECASE,
)
_TASK_VERB_LEAD_RE = re.compile(
    r"^\s*(make|build|write|add|create|fix|update|implement|refactor|run|generate"
    r"|design|deploy|install|set up|remove|delete|rename|move|check)\b",
    re.IGNORECASE,
)
_MAX_ACCEPTANCE_CLAUSE_WORDS = 8

_REJECTION_RE = re.compile("|".join(_REJECTION_PATTERNS), re.IGNORECASE)
_ACCEPTANCE_RE = re.compile("|".join(_ACCEPTANCE_PATTERNS), re.IGNORECASE)
_INSTRUCTIONAL_CUE_RE = re.compile("|".join(_INSTRUCTIONAL_CUE_PATTERNS), re.IGNORECASE)

# LEADING "no"/"nope" REACTION (dead-pattern fix). The old rejection regex
# `\b(no,? that'?s|nope,? that'?s)\b` was written to span a comma ("no, that's")
# but the clause splitter severs "no" from "that's" FIRST, so it could never
# match — a genuine complaint "no, that's not what I asked for" silently fell
# back to SUCCESS. This special-case detects the leading bare reaction token
# WITHOUT depending on comma-adjacency the splitter destroys:
#   (1) `^\s*(no|nope)\b` — the reaction must be at the ABSOLUTE START of the
#       RAW prompt, so "no" inside "there is no cache" or "undo is hard" / a
#       mid-sentence "nope" never qualifies; AND
#   (2) a `that'?s` complaint marker anywhere in the prompt — a negation/fault
#       ("that's wrong", "that's not what I asked for"). The complaint anchor
#       keeps the leading "no" from firing on benign "no, go ahead and ship it".
_LEADING_NO_RE = re.compile(r"^\s*(no|nope)\b", re.IGNORECASE)
_THATS_COMPLAINT_RE = re.compile(
    r"\bthat'?s (wrong|worse|broken|not (right|what i (wanted|asked for)))\b",
    re.IGNORECASE,
)

# Clause boundary: split on sentence/clause terminators (incl. comma) so only the
# user's immediate reaction (the first clause) is tested for rejection. The comma
# split lets "we should have used a cache, and document …" surface its cue-laden
# first clause and lets "revert that, you broke the build" test "revert that".
_CLAUSE_SPLIT_RE = re.compile(r"[.,;\n]")


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
    """High-precision: True only on an UNAMBIGUOUS complaint about the prior work
    in the user's IMMEDIATE reaction (the first clause).

    Precision rules (asymmetric-cost — near-zero false positives, recall second):
    - Clause-scoped: only the FIRST clause is tested. A rework verb in a later
      clause ("thanks. redo it for the other file") is NEW work, not a complaint.
    - Acceptance precedence: an acceptance marker in the first clause => not a
      rejection, even if a later clause looks rework-shaped.
    - Instructional/conditional exclusion: a first clause carrying should / when /
      if / whether / explain / document / how to / can you / try is a feature
      request, spec, or conditional ("should roll back on failure", "document when
      to use a different agent") — NOT a complaint => not a rejection.
    Conservative by design — when in any doubt, return False (=> SUCCESS), which
    falls back to the old proxy floor. Returns False on empty / non-string input.
    """
    if not prompt or not isinstance(prompt, str):
        return False
    first = _first_clause(prompt)
    if _ACCEPTANCE_RE.search(first):
        return False  # acceptance precedence — later "redo" clauses are new work
    if _INSTRUCTIONAL_CUE_RE.search(first):
        return False  # instructional/conditional/spec clause — not a complaint
    # Dead-pattern fix: a leading bare "no"/"nope" reaction at the ABSOLUTE start
    # of the raw prompt, paired with a `that's <complaint>` anywhere, is a genuine
    # rejection the comma-splitter would otherwise hide (it severs "no" from
    # "that's"). Anchored at ^ so "no" inside "there is no cache" never fires.
    if _LEADING_NO_RE.match(prompt) and _THATS_COMPLAINT_RE.search(prompt):
        return True
    return bool(_REJECTION_RE.search(first))


def is_acceptance(prompt: str) -> bool:
    """High-precision: True only on explicit affirmation/acceptance of the prior
    work in the user's IMMEDIATE reaction (the first clause).

    SUCCESS now requires a POSITIVE signal (T4 three-way). Without one — an
    unrelated / new-topic next prompt — the outcome is NEUTRAL (no boost), not
    success. So this detector decides boost-vs-neutral; ``is_rejection`` decides
    the failure path. Same clause-scoping and word-boundary anchoring as
    ``is_rejection`` so a substring (e.g. "great" inside "greater") never trips
    it, PLUS the boost-path guards (negation, leading task verb, instructional
    cue, clause-length cap — see the guard block above): a false boost inflates
    the silent-success share, so when in any doubt return False (=> NEUTRAL).
    Returns False on empty / non-string input.
    """
    if not prompt or not isinstance(prompt, str):
        return False
    first = _first_clause(prompt)
    if not _ACCEPTANCE_RE.search(first):
        return False
    if len(first.split()) > _MAX_ACCEPTANCE_CLAUSE_WORDS:
        return False  # task description, not a terse reaction
    if _NEGATION_RE.search(first):
        return False  # "not perfect", "doesn't work", "no thanks"
    if _TASK_VERB_LEAD_RE.match(first):
        return False  # marker buried in new task text
    if _INSTRUCTIONAL_CUE_RE.search(first):
        return False  # "can you make it perfect", "if it looks good …"
    return True


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
        accepted = is_acceptance(prompt)

        # Lazy: only import the scorer (and thus learning_db_v2) when there is
        # actually something to resolve.
        import time

        from learning_db_v2 import init_db
        from routing_outcome_score import apply_outcome, decision_row_exists, outcome_basis
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
        #
        # LOW: parse `created` defensively — a malformed entry must not abort the
        # whole turn. `_created_or_none` returns None on a bad value; such an
        # entry is excluded from `live` (not attributable) and skipped in the loop.
        def _created_or_none(it: dict) -> float | None:
            try:
                return float(it.get("created", now))
            except (TypeError, ValueError):
                return None

        live = [
            it
            for it in pending
            if it.get("key") and (c := _created_or_none(it)) is not None and (now - c) <= MAX_PENDING_AGE_SEC
        ]
        attributable = len(live) == 1

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        to_revalidate: list[dict] = []
        to_requeue: list[dict] = []
        for item in pending:
            key = item.get("key")
            if not key:
                continue
            # LOW: per-entry robustness — one malformed pending entry (e.g. a
            # non-numeric `created`) must NOT abort scoring for the rest of the
            # turn's entries. Parse defensively; skip only the bad entry.
            created = _created_or_none(item)
            if created is None:
                continue
            # Drop abandoned provisional entries; never score a stale one.
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
            # THREE-WAY per-entry resolution (T4). Per-entry error flag is the
            # only signal that is ALWAYS attributable; the turn-level
            # reaction (rejection OR acceptance) is attributable ONLY when a
            # single dispatch is pending this turn (HIGH-1) — with >1 pending it
            # is ignored so a turn signal cannot broadcast across siblings.
            #   errors          => failure (decay)              — highest precision
            #   rejection       => failure (decay)              — attributable only
            #   acceptance      => success (boost)              — attributable only
            #   otherwise       => neutral (no-op)              — new-topic default
            reaction_failure = rejected if attributable else False
            reaction_success = accepted if attributable else False
            if bool(item.get("errors")) or reaction_failure:
                outcome = "failure"
            elif reaction_success:
                outcome = "success"
            else:
                outcome = "neutral"
            # Basis is the evidence label (errors > rejection > acceptance >
            # no-complaint), recorded as a per-route counter for route-health's
            # silent-success report. acceptance_detected marks a boost earned by
            # an explicit positive marker — strong feedback, not silence.
            # Label-only: it never changes the boost/decay/no-op the three-way
            # outcome drives.
            basis = outcome_basis(bool(item.get("errors")), reaction_failure, reaction_success)
            new_conf = apply_outcome(key, outcome, basis=basis)
            # Short, secret-free cause for this dispatch's outcome. Computed
            # unconditionally (not debug-only) so the JSONL OUTCOME event carries
            # the demotion cause — an operator reading route-events.jsonl after a
            # decay can see WHY without the per-key basis table.
            if item.get("errors"):
                reason = "tool-errors"
            elif reaction_failure:
                reason = "rejection"
            elif reaction_success:
                reason = "acceptance"
            elif (rejected or accepted) and not attributable:
                reason = "reaction-ignored-multi-dispatch"
            else:
                reason = "neutral-new-topic"
            # T3: per-dispatch OUTCOME event (JSONL), append-only + failure-safe.
            # Auxiliary instrumentation for replay; route_events swallows write
            # errors so a logging failure never breaks finalization.
            # routing_relevant=True: a finalizer failure decays the row by
            # contract, so it is a routing signal route-value-eval must count.
            from route_events import record_outcome_event

            record_outcome_event(
                session=session_id,
                key=key,
                outcome=outcome,
                reason=reason,
                routing_relevant=True,
            )
            if debug:
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
