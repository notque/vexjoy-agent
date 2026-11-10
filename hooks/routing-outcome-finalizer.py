#!/usr/bin/env python3
# hook-version: 1.2.1
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

WEAK-POSITIVE UPGRADE (C6, ADR router-improvement-program): explicit acceptance
almost never appears, so healthy routes sat at confidence 0.5 forever (signal
starvation). A REPEAT dispatch of the same agent:skill pair with no intervening
failure is weak evidence the route works — the user kept re-using it. So a
would-be-NEUTRAL entry upgrades to weak_success (small bounded boost, see
routing_outcome_score.WEAK_BOOST_DELTA / WEAK_CONFIDENCE_CAP) when ALL hold:
  - the entry itself is clean (no tool errors — the failure path is untouched),
  - the same key was finalized NON-FAILURE earlier THIS session (per-key
    history in the bridge state file; sessions start fresh),
  - the turn carries NO rejection signal, even an unattributable one (a
    multi-dispatch turn with a complaint upgrades nothing — conservative).
The upgrade reads dispatch HISTORY, not prompt text: the reaction detector and
its neutral classification are byte-identical. First dispatch of a pair plus an
unrelated next prompt stays a neutral no-op exactly as before. Failure, decay,
and explicit-acceptance paths are unchanged.

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
``errors`` flag (recorded by action A). The user reaction is a turn-level
signal. It names a ROUTE only when every live pending dispatch shares one route
key. /do Phase 4 fans out several agents per turn, and one "that's wrong"
cannot be pinned to one of N different routes. So (v1.2.0):

| Live pending dispatches | Rejection | Acceptance |
|---|---|---|
| one route key (1 or N dispatches) | failure, applied to ONE entry | success, applied to ONE entry |
| two or more route keys | IGNORED | weak_success on each clean entry, basis `acceptance_shared` |

- One route key, N dispatches: the reaction scores the first clean entry. The
  others stay neutral, so one "thanks" is one boost, not N.
- Two or more keys, rejection: ignored. Decaying every sibling for one
  complaint punishes correct routes (the expensive direction).
- Two or more keys, acceptance: the user accepted the combined result, so each
  clean entry takes the bounded weak boost (WEAK_BOOST_DELTA, capped at
  WEAK_CONFIDENCE_CAP). It cannot push a route past the cap.

Before v1.2.0 a reaction counted only with exactly one pending dispatch, and
the Stop fallback drained every entry first: 0 of 37 reactions scored.

Design Principles:
- SILENT (touches state/DB only; no context injection)
- Non-blocking: every RUNTIME path exits 0 (finally: sys.exit(0))
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
    # v1.2.0: subject widened from that/this to it/that/this, and "still"
    # allowed ("it's still broken"). Every arm stays anchored on a complaint
    # word about the prior work. `(?! to\b)` keeps the dummy-it statement "it is
    # wrong to assume a cache" out.
    r"\b(it|that|this)(?:'?s| is) (still )?(wrong|worse|broken|failing|not (right|working|fixed|what i (wanted|asked for|meant)))\b(?! to\b)",
    r"\b(it|that|this) isn'?t (right|working|fixed|correct|what i (wanted|asked for|meant))\b",
    r"\bnot what i (wanted|asked for|meant)\b",
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
    r"\b(it|that|this) (still )?(didn'?t|did not|doesn'?t|does not) work\b",
    # Clause-leading only: "the CI is still failing on main" names a new task.
    r"^\s*still (broken|wrong|failing|not working|not fixed|doesn'?t work)\b",
    r"\byou (broke|messed up|got it wrong|misunderstood|did the wrong thing)\b",
    # Sole surviving re-route signal: anchored on the literal complaint "wrong".
    r"\bwrong (agent|skill|route|routing)\b",
    r"\b(fix|undo) (your|the) (mistake|error|mess)\b",
]

# ACCEPTANCE markers: when one appears in the FIRST clause it takes precedence
# over any later rejection-shaped clause (acceptance precedence). Word-boundary
# anchored so a substring cannot trip them.
#
# v1.2.0 widened the set. Each marker JUDGES THE WORK ("looks great", "that's
# right", "it works") or releases it ("merge it", "commit it"). Left out on
# purpose: bare "yes", "yeah", "okay", "sure", and "sounds good" answer a
# question or approve a plan, and do not say the finished work was good.
_ACCEPTANCE_PATTERNS = [
    r"\b(thanks|thank you|thx|great|perfect|looks good|lgtm|nice work|well done|that worked)\b",
    r"\b(works now|that fixed it|that did it|good job)\b",
    r"\b(merge it|ship it|ship that|approve|approved)\b",
    r"\b(awesome|excellent|amazing|fantastic|brilliant|beautiful|love (it|that|this))\b",
    r"\b(good|great|nice) (work|stuff|one)\b|\b(nicely|well) done\b|\b(much|way|a lot) better\b",
    r"\b(looks|seems|works|working) (really |very |pretty )?(good|great|right|fine|correct|perfect|well)\b",
    r"\bthat'?s (right|correct|good|better|exactly (it|right|what i (wanted|needed|asked for)))\b",
    r"\bexactly what i (wanted|needed|asked for)\b",
    r"\b(it|that|this) (works|worked)\b|\bworking now\b",
    r"\b(commit|push) it\b",
]

# A clause that is ONLY one of these words is a terse verdict ("nice", "cool").
# Inside a longer clause they are too common to trust ("a nice to have").
_BARE_ACCEPTANCE_RE = re.compile(r"^\s*(nice|good|cool|sweet|exactly|correct)\s*!*\s*$", re.IGNORECASE)

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
#   - the marker starts within the clause's first words
#     (_MAX_ACCEPTANCE_MARKER_OFFSET) — a reaction leads; a marker deep in the
#     clause is task text ("put the logo where it looks good")
#   - no negation token in the clause ("not perfect", "doesn't work")
#   - no contrast token in the clause, and the next clause does not open with
#     one ("great, but the tests fail") — praise that leads into a complaint
#   - the clause does not open with a task verb ("make a great landing page",
#     "write the perfect README" — markers buried in new task text)
#   - no instructional/conditional/request cue ("can you make it perfect", "if
#     it looks good then merge", "i want a great header")
#   - the clause is short (<= _MAX_ACCEPTANCE_CLAUSE_WORDS words). Raised from
#     8 to 12 in v1.2.0: dictated prompts carry no punctuation, so a real
#     reaction runs on into the next request.
# The looser `_ACCEPTANCE_RE` alone still serves acceptance PRECEDENCE inside
# `is_rejection` (there a loose match only prevents a decay — the safe side).
_NEGATION_RE = re.compile(
    r"\b(not|no|never|hardly|isn'?t|wasn'?t|aren'?t|doesn'?t|don'?t|didn'?t|can'?t|won'?t)\b",
    re.IGNORECASE,
)
_CONTRAST_RE = re.compile(r"\b(but|however|though|although|except|still|yet|unless)\b", re.IGNORECASE)
_TASK_VERB_LEAD_RE = re.compile(
    r"^\s*(make|build|write|add|create|fix|update|implement|refactor|run|generate"
    r"|design|deploy|install|set up|remove|delete|rename|move|check)\b",
    re.IGNORECASE,
)
# Request cues that veto an acceptance boost only. They are not added to
# `_INSTRUCTIONAL_CUE_RE`, because there they would also veto a rejection, and
# "that's wrong, i want the old one back" is a real complaint.
_REQUEST_CUE_RE = re.compile(
    r"\b(can we|could (you|we)|would you|please|let'?s|(i|we) (want|need|would like)|need to|want to|make sure)\b",
    re.IGNORECASE,
)
_MAX_ACCEPTANCE_CLAUSE_WORDS = 12
_MAX_ACCEPTANCE_MARKER_OFFSET = 3  # marker starts at word index <= 3
_MAX_REJECTION_MARKER_OFFSET = 3

_REJECTION_RE = re.compile("|".join(_REJECTION_PATTERNS), re.IGNORECASE)
_ACCEPTANCE_RE = re.compile("|".join(_ACCEPTANCE_PATTERNS), re.IGNORECASE)
_INSTRUCTIONAL_CUE_RE = re.compile("|".join(_INSTRUCTIONAL_CUE_PATTERNS), re.IGNORECASE)

# LEADING FILLER (v1.2.0). Spoken and typed prompts open with a filler word that
# carries no verdict: "okay, that's wrong", "oh great that worked". The clause
# splitter made the filler the whole first clause, so the reaction behind it was
# never tested. Filler is stripped before the first clause is taken. "yes",
# "yeah", "no", and "right" are NOT filler: they carry meaning.
_LEADING_FILLER_RE = re.compile(
    r"^\s*(?:(?:ok(?:ay)?|oh|well(?! done)|alright|all right|so|hm+|um+|uh+|hey|wait|and|then|now)\b[\s,.!-]*)+",
    re.IGNORECASE,
)

# LEADING "no"/"nope" REACTION (dead-pattern fix). The old rejection regex
# `\b(no,? that'?s|nope,? that'?s)\b` was written to span a comma ("no, that's")
# but the clause splitter severs "no" from "that's" FIRST, so it could never
# match — a genuine complaint "no, that's not what I asked for" silently fell
# back to SUCCESS. This special-case detects the leading bare reaction token
# WITHOUT depending on comma-adjacency the splitter destroys:
#   (1) `^\s*(no|nope)\b` — the reaction must be at the ABSOLUTE START of the
#       prompt (after leading filler), so "no" inside "there is no cache" or
#       "undo is hard" / a mid-sentence "nope" never qualifies; AND
#   (2) a complaint marker: `that's <complaint>` anywhere in the prompt, or
#       (v1.2.0) any rejection marker in the clause right after the "no"
#       ("no, it still doesn't work"). The complaint anchor keeps the leading
#       "no" from firing on benign "no, go ahead and ship it".
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

# Prior same-session outcomes that qualify a repeat dispatch for the C6
# weak-positive upgrade: anything but a failure. A key whose LAST finalization
# was a failure gets no weak boost — that repeat has an intervening failure.
_NON_FAILURE_OUTCOMES = frozenset({"neutral", "success", "weak_success"})


def _strip_filler(prompt: str) -> str:
    """Drop leading filler words. Returns the prompt unchanged if only filler."""
    stripped = _LEADING_FILLER_RE.sub("", prompt, count=1)
    return stripped if stripped.strip() else prompt


def _clauses(prompt: str) -> list[str]:
    """Non-empty clauses of the prompt, leading filler removed, in order."""
    return [part for part in _CLAUSE_SPLIT_RE.split(_strip_filler(prompt)) if part.strip()]


def _first_clause(prompt: str) -> str:
    """The user's immediate reaction: text up to the first `. , ; \\n` terminator.

    Leading filler ("okay,", "oh") and empty leading clauses are skipped so the
    first substantive clause is returned.
    """
    parts = _clauses(prompt)
    return parts[0] if parts else prompt


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
    parts = _clauses(prompt)
    first = parts[0] if parts else prompt
    # A rejection marker can contain an acceptance word ("that's not right"
    # holds no acceptance marker, but "that isn't working well" would), so the
    # rejection match is taken first and acceptance precedence applies only
    # when no rejection marker sits in the same clause.
    # A reaction leads its clause. A marker past the first words sits in task
    # or explanation text ("there is no cache and it is wrong ...").
    match = _REJECTION_RE.search(first)
    rejected_first = bool(match) and len(first[: match.start()].split()) <= _MAX_REJECTION_MARKER_OFFSET
    if not rejected_first and _ACCEPTANCE_RE.search(first):
        return False  # acceptance precedence — later "redo" clauses are new work
    if _INSTRUCTIONAL_CUE_RE.search(first):
        return False  # instructional/conditional/spec clause — not a complaint
    # Dead-pattern fix: a leading bare "no"/"nope" reaction at the ABSOLUTE start
    # of the prompt, paired with a complaint, is a genuine rejection the
    # comma-splitter would otherwise hide (it severs "no" from the complaint).
    # Anchored at ^ so "no" inside "there is no cache" never fires.
    if _LEADING_NO_RE.match(_strip_filler(prompt)):
        if _THATS_COMPLAINT_RE.search(prompt):
            return True
        if len(parts) > 1 and _REJECTION_RE.search(parts[1]) and not _INSTRUCTIONAL_CUE_RE.search(parts[1]):
            return True
    return rejected_first


def is_acceptance(prompt: str) -> bool:
    """High-precision: True only on explicit affirmation/acceptance of the prior
    work in the user's IMMEDIATE reaction (the first clause).

    SUCCESS now requires a POSITIVE signal (T4 three-way). Without one — an
    unrelated / new-topic next prompt — the outcome is NEUTRAL (no boost), not
    success. So this detector decides boost-vs-neutral; ``is_rejection`` decides
    the failure path. Same clause-scoping and word-boundary anchoring as
    ``is_rejection`` so a substring (e.g. "great" inside "greater") never trips
    it, PLUS the boost-path guards (marker offset, negation, contrast, leading
    task verb, instructional and request cues, clause-length cap — see the guard
    block above): a false boost inflates the silent-success share, so when in
    any doubt return False (=> NEUTRAL). Returns False on empty / non-string
    input.
    """
    if not prompt or not isinstance(prompt, str):
        return False
    parts = _clauses(prompt)
    first = parts[0] if parts else prompt
    if _BARE_ACCEPTANCE_RE.match(first):
        marker_offset = 0
    else:
        match = _ACCEPTANCE_RE.search(first)
        if not match:
            return False
        marker_offset = len(first[: match.start()].split())
    if marker_offset > _MAX_ACCEPTANCE_MARKER_OFFSET:
        return False  # marker deep in the clause: task text, not a reaction
    if len(first.split()) > _MAX_ACCEPTANCE_CLAUSE_WORDS:
        return False  # task description, not a short reaction
    if _REJECTION_RE.search(first):
        return False  # "that isn't working well" — a complaint wins
    if _NEGATION_RE.search(first):
        return False  # "not perfect", "doesn't work", "no thanks"
    if _CONTRAST_RE.search(first):
        return False  # "great but the tests fail"
    if len(parts) > 1 and (_CONTRAST_RE.match(parts[1].strip()) or _REJECTION_RE.search(parts[1])):
        return False  # "great, but the tests fail" / "great, that's wrong"
    if _TASK_VERB_LEAD_RE.match(first):
        return False  # marker buried in new task text
    if _INSTRUCTIONAL_CUE_RE.search(first) or _REQUEST_CUE_RE.search(first):
        return False  # "can you make it perfect", "if it looks good …"
    return True


_BYPASS_ENV = "ROUTING_OUTCOME_FINALIZER_BYPASS"


def main() -> None:
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print("[routing-outcome-finalizer] Bypassed via ROUTING_OUTCOME_FINALIZER_BYPASS=1", file=sys.stderr)
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
        from routing_outcome_score import (
            BASIS_ACCEPTANCE_SHARED,
            BASIS_REPEAT_WEAK,
            WEAK_SUCCESS,
            decision_row_exists,
            outcome_basis,
            record_resolved_outcome,
        )
        from routing_outcome_state import (
            MAX_PENDING_AGE_SEC,
            get_outcome_history,
            record_outcome_history,
            requeue_pending_outcomes,
            revalidate_pending_outcomes,
        )

        # LOW-1: init the schema ONCE per scoring block, not per key
        # (decision_row_exists no longer calls init_db itself).
        init_db()
        now = time.time()

        # C6 weak-positive: snapshot the per-key outcome history BEFORE scoring.
        # Entries resolve against the PRE-turn snapshot only, so two same-pair
        # siblings drained in one turn cannot weak-boost each other.
        history = get_outcome_history(session_id)

        # HIGH-1: a turn-level reaction names a route only when every live
        # pending dispatch shares ONE route key (see the module docstring
        # table). Stale and malformed entries do not count as live.
        #
        # LOW: parse `created` defensively — a malformed entry must not abort the
        # whole turn. `_created_or_none` returns None on a bad value; such an
        # entry is excluded from `live` (not attributable) and skipped in the loop.
        def _created_or_none(it: dict) -> float | None:
            try:
                return float(it.get("created", now))
            except (TypeError, ValueError):
                return None

        # The take above already cleared `pending` from state. An entry that
        # is not a dict, or whose key is not a string, is dropped here: it must
        # not raise and lose every other entry of the turn.
        pending = [it for it in pending if isinstance(it, dict) and isinstance(it.get("key"), str)]
        live = [
            it
            for it in pending
            if it.get("key") and (c := _created_or_none(it)) is not None and (now - c) <= MAX_PENDING_AGE_SEC
        ]
        attributable = len({it["key"] for it in live}) == 1
        # One reaction is one score. `reaction_spent` flips once the reaction
        # has scored an entry; `shared_done` holds the keys that already took
        # the shared weak boost this turn.
        reaction_spent = False
        shared_done: set[str] = set()

        debug = os.environ.get("CLAUDE_HOOKS_DEBUG")
        to_revalidate: list[dict] = []
        to_requeue: list[dict] = []
        history_updates: dict[str, str] = {}
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
            # THREE-WAY per-entry resolution (T4). The per-entry error flag is
            # always attributable. The turn-level reaction scores ONE clean
            # entry, and only when every live entry shares one route key.
            #   errors          => failure (decay)              — highest precision
            #   rejection       => failure (decay)              — attributable only
            #   acceptance      => success (boost)              — attributable only
            #   otherwise       => neutral (no-op)              — new-topic default
            errors = bool(item.get("errors"))
            takes_reaction = attributable and not errors and not reaction_spent and (rejected or accepted)
            reaction_failure = rejected and takes_reaction
            reaction_success = accepted and takes_reaction and not rejected
            if takes_reaction:
                reaction_spent = True
            if errors or reaction_failure:
                outcome = "failure"
            elif reaction_success:
                outcome = "success"
            else:
                outcome = "neutral"
            # SHARED ACCEPTANCE: two or more route keys were pending and the
            # user accepted the combined result. Each key takes ONE bounded
            # weak boost. Never on a rejection turn.
            shared_acceptance = (
                outcome == "neutral" and accepted and not rejected and not attributable and key not in shared_done
            )
            if shared_acceptance:
                shared_done.add(key)
                outcome = WEAK_SUCCESS
            # C6 WEAK-POSITIVE UPGRADE: a would-be-neutral CLEAN entry whose key
            # was finalized non-failure earlier this session is a repeat
            # dispatch with no intervening failure => small bounded boost.
            # Suppressed for the whole turn when ANY rejection fired (even an
            # unattributable multi-dispatch one): never boost on a complaint
            # turn. Failure / explicit-acceptance branches above are untouched.
            repeat_weak = outcome == "neutral" and not rejected and history.get(key) in _NON_FAILURE_OUTCOMES
            if repeat_weak:
                outcome = WEAK_SUCCESS
            # Basis is the evidence label (errors > rejection > acceptance >
            # no-complaint), recorded as a per-route counter for route-health's
            # silent-success report. acceptance_detected marks a boost earned by
            # an explicit positive marker — strong feedback, not silence.
            # acceptance_shared and repeat_dispatch_weak mark the two weak
            # signals — neither strong feedback nor silence. Label-only: it
            # never changes the boost/decay/no-op the outcome drives.
            if shared_acceptance:
                basis = BASIS_ACCEPTANCE_SHARED
            elif repeat_weak:
                basis = BASIS_REPEAT_WEAK
            else:
                basis = outcome_basis(errors, reaction_failure, reaction_success)
            # Short, secret-free cause for this dispatch's outcome. Computed
            # unconditionally (not debug-only) so the JSONL OUTCOME event carries
            # the demotion cause — an operator reading route-events.jsonl after a
            # decay can see WHY without the per-key basis table.
            if errors:
                reason = "tool-errors"
            elif reaction_failure:
                reason = "rejection"
            elif reaction_success:
                reason = "acceptance"
            elif shared_acceptance:
                reason = "acceptance-shared-multi-dispatch"
            elif repeat_weak:
                reason = "repeat-dispatch-no-failure"
            elif (rejected or accepted) and not attributable:
                reason = "reaction-ignored-multi-dispatch"
            elif rejected or accepted:
                reason = "reaction-scored-on-sibling"
            else:
                reason = "neutral-new-topic"
            # One write path for confidence, basis counter, route-events.jsonl
            # (routing_relevant=True), and this dispatch's evidence row.
            new_conf = record_resolved_outcome(
                session_id=session_id,
                key=key,
                outcome=outcome,
                basis=basis,
                reason=reason,
                source="hook:routing-outcome-finalizer",
                decision_id=item.get("decision_id") or None,
            )
            # Session history feeds the NEXT repeat's weak-positive check.
            # Failure precedence within the turn: one failed sibling marks the
            # key failed even if another same-key entry scored clean.
            if history_updates.get(key) != "failure":
                history_updates[key] = outcome
            if debug:
                print(
                    f"[routing-outcome-finalizer] {outcome} routing/{key} ({reason}) conf={new_conf:.4f}",
                    file=sys.stderr,
                )

        # Persist this turn's finalized outcomes so the NEXT dispatch of each
        # key can read them (the weak-positive signal's memory). Only actually
        # scored entries land here — requeued/stale/malformed ones never do.
        record_outcome_history(session_id, history_updates)

        if to_requeue:
            requeue_pending_outcomes(session_id, to_requeue)
        if to_revalidate:
            revalidate_pending_outcomes(session_id, to_revalidate)

    except Exception as e:
        try:
            print(f"[routing-outcome-finalizer] error: {type(e).__name__}: {e}", file=sys.stderr)
        except Exception:
            pass  # stderr write must never itself break the hook
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
