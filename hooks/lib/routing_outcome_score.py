"""Shared routing-outcome scoring: decision-row existence + boost/decay apply.

Used by the SubagentStop validator (existence check only), the UserPromptSubmit
finalizer, and the Stop fallback finalizer. Centralizing this here keeps the
keyed read-only existence query and the boost/decay deltas identical across all
three resolution points, and keeps the (read-only) coupling to learning_db_v2 in
ONE place. learning_db_v2.py itself is never edited — we only read its DB path,
init the schema, and call its public boost/decay/record helpers.
"""

import sqlite3

# Route-health parity with the old `record-routing-outcome` CLI: identical
# deltas and the routing/effectiveness slice (topic=routing, key={agent}:{skill}).
BOOST_DELTA = 0.05
DECAY_DELTA = 0.08

# WEAK-POSITIVE signal (ADR router-improvement-program C6): a repeat dispatch
# of the same agent:skill pair with no intervening failure is weak evidence the
# route works — the user kept re-using it. Bounded so repetition alone can
# never make a pair high-confidence:
#   - WEAK_BOOST_DELTA (0.02) < acceptance boost (0.05) < failure decay (0.08):
#     one failure erases four weak boosts; explicit signals always dominate.
#   - WEAK_CONFIDENCE_CAP (0.65) sits strictly below the 0.70 high-confidence /
#     injection threshold: crossing 0.70 requires explicit acceptance. The cap
#     clamps the DELTA (never lowers a row already above it from explicit
#     boosts); success_count still increments at the cap, so n keeps accruing
#     toward the evidence gate (n >= 5) while confidence stays bounded.
WEAK_BOOST_DELTA = 0.02
WEAK_CONFIDENCE_CAP = 0.65

# Basis label for a weak-positive outcome (route-health reports it as its own
# line — neither strong feedback nor silent default-success).
BASIS_REPEAT_WEAK = "repeat_dispatch_weak"


def decision_row_exists(key: str) -> bool:
    """True iff a routing decision row was already written for ``key``.

    KEYED existence check with NO row cap. boost/decay are no-ops on a missing
    row and return 0.0 (indistinguishable from a legitimate decayed-to-zero
    confidence), so callers MUST gate scoring on this before applying an
    outcome. A prior top-1000 confidence-DESC scan dropped low-confidence rows
    once the table exceeded 1000 rows (data loss); the exact (topic, key,
    category) SELECT avoids that.

    Read-only: opens learning_db_v2's DB path directly. learning_db_v2.py is not
    edited (a pre-existing SQLi false-positive trips the commit security gate),
    only read. Category matches action A's exact write ('effectiveness');
    topic+key alone is unique so category only narrows.

    LOW-1: this function NO LONGER calls ``init_db()`` per key. Callers that
    invoke it in a loop MUST call ``init_db()`` once before the loop (the
    finalizer does so at the top of its scoring block). The DB path/file is
    expected to already exist by the time an outcome is being scored (action A
    wrote a decision row through ``init_db`` first). If the file is genuinely
    absent the SELECT raises and is caught below => treated as "unknown" (skip),
    identical to the prior best-effort behavior.
    """
    from learning_db_v2 import get_db_path

    try:
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
        # Best-effort: on any read failure treat as "unknown" => caller skips
        # scoring (and re-queues), never crashes, never double-counts.
        return False


SUCCESS = "success"
FAILURE = "failure"
NEUTRAL = "neutral"
WEAK_SUCCESS = "weak_success"

# Sentinel for "no positional outcome supplied" — distinct from any valid
# outcome and from None, so the public `outcome` type is `str | bool` (None is
# NOT a valid outcome). Callers that omit `outcome` MUST pass the `failure=`
# kwarg; supplying neither is rejected.
_OUTCOME_UNSET: object = object()


def _current_confidence(key: str) -> float:
    """Read-only current confidence for routing/{key}; 0.0 if absent."""
    from learning_db_v2 import get_db_path

    try:
        conn = sqlite3.connect(get_db_path(), timeout=5.0)
        try:
            row = conn.execute(
                "SELECT confidence FROM learnings WHERE topic = ? AND key = ? LIMIT 1",
                ("routing", key),
            ).fetchone()
            return float(row[0]) if row else 0.0
        finally:
            conn.close()
    except Exception:
        return 0.0


def outcome_basis(errors: bool, reaction_failure: bool, reaction_success: bool = False) -> str:
    """The evidence basis for a finalized outcome — one of four labels.

    Pure and module-level so tests import it directly. Order matters: a tool
    error is the strongest, most attributable signal, so it wins even when a
    user reaction also fired; a failure reaction outranks a success reaction.

      tool_errors_only     dispatch's own error flag fired (a real signal)
      rejection_detected   user complaint fired, no error (a real signal)
      acceptance_detected  explicit positive marker fired (a real signal)
      default_no_complaint neutral on silence — the silent-success case

    `default_no_complaint` covers clean neutral entries AND the multi-dispatch
    case where the turn reaction is ignored: in both, no signal scored THIS
    entry. `reaction_success` defaults False so every pre-existing two-arg
    caller and test is unchanged.
    """
    if errors:
        return "tool_errors_only"
    if reaction_failure:
        return "rejection_detected"
    if reaction_success:
        return "acceptance_detected"
    return "default_no_complaint"


def _record_basis(key: str, basis: str) -> None:
    """Increment one per-(key, basis) counter. Best-effort; never raises.

    Bridge never-block contract: a lost basis count never blocks scoring and
    never corrupts confidence. Opens learning_db_v2's DB path directly (read +
    upsert) — learning_db_v2.py's existing functions are not called/edited (a
    pre-existing SQLi false-positive there trips the commit security gate). The
    routing_outcome_basis table is created by the v6 migration on init_db.
    """
    try:
        from learning_db_v2 import get_db_path

        conn = sqlite3.connect(get_db_path(), timeout=5.0)
        try:
            conn.execute(
                "INSERT INTO routing_outcome_basis (key, basis, count) VALUES (?, ?, 1) "
                "ON CONFLICT(key, basis) DO UPDATE SET count = count + 1",
                (key, basis),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Best-effort: swallow any DB failure. The count is advisory.
        pass


def apply_outcome(
    key: str,
    outcome: str | bool = _OUTCOME_UNSET,  # type: ignore[assignment]  # sentinel default; None is not a valid outcome
    basis: str | None = None,
    *,
    failure: bool | None = None,
) -> float:
    """Apply a THREE-WAY routing outcome. Returns new (or unchanged) confidence.

    ``outcome`` is one of:
      - ``"failure"`` — decay the row (errors or attributable rejection).
      - ``"success"`` — boost the row (acceptance / continuation).
      - ``"weak_success"`` — bounded small boost (C6 weak-positive: repeat
        dispatch of the same pair with no intervening failure). Delta is
        ``WEAK_BOOST_DELTA`` clamped so confidence never exceeds
        ``WEAK_CONFIDENCE_CAP`` via weak boosts (delta 0 at/above the cap — the
        row is never lowered). success_count still increments at the cap, so n
        keeps accruing while confidence stays bounded.
      - ``"neutral"`` — NO-OP: no boost, no decay, no count change, no schema
        migration. Returns the row's current confidence unchanged. Neutral is the
        new default for unrelated/new-topic next prompts and clean autonomous Stop
        runs — signal-fidelity fix so future data can contain real negatives
        instead of being drowned by boost-everything.

    Back-compat (two-way binary callers): pass a bare ``True``/``False`` as
    ``outcome`` OR the keyword ``failure=<bool>`` (True=>failure, False=>success).
    The ``failure=`` keyword is the legacy binary API the basis tests still use;
    it maps to FAILURE/SUCCESS and never reaches NEUTRAL.

    Any other string raises ``ValueError`` — an unrecognized outcome (e.g. a
    typo) must surface as a bug, never silently boost confidence.

    ``outcome`` is typed ``str | bool``; ``None`` is NOT a valid outcome. Omitting
    it uses an internal sentinel meaning "caller used the ``failure=`` kwarg
    form". Calling with neither a positional ``outcome`` nor a ``failure=`` kwarg
    raises ``ValueError`` immediately — there is no "no outcome" outcome.

    Caller MUST gate on decision_row_exists(key) first.

    `basis` is label-only: when given, increment its per-route counter (best
    effort) for route-health's silent-success report. It does NOT change the
    boost/decay/no-op — that is byte-identical with or without basis. Default None
    keeps every pre-PR caller and test unchanged.
    """
    from learning_db_v2 import boost_confidence, decay_confidence

    # Back-compat: the legacy binary API passes `failure=<bool>` and no positional
    # outcome. Map it to the three-way string. An explicit `outcome` wins.
    if outcome is _OUTCOME_UNSET and failure is not None:
        outcome = FAILURE if failure else SUCCESS
    # Neither form supplied (or an explicit invalid None): there is no "no
    # outcome" outcome. Reject so the illegal call surfaces clearly instead of
    # falling through to the generic unknown-string ValueError.
    if outcome is _OUTCOME_UNSET or outcome is None:
        raise ValueError("apply_outcome requires an outcome or a failure= kwarg; got neither")
    # Back-compat: legacy callers passed a `failure` bool positionally.
    if outcome is True:
        outcome = FAILURE
    elif outcome is False:
        outcome = SUCCESS

    if basis:
        _record_basis(key, basis)

    if outcome == NEUTRAL:
        return _current_confidence(key)  # no-op: read-only, no count change
    if outcome == FAILURE:
        return decay_confidence("routing", key, delta=DECAY_DELTA)
    if outcome == SUCCESS:
        return boost_confidence("routing", key, delta=BOOST_DELTA)
    if outcome == WEAK_SUCCESS:
        # Bounded: the delta shrinks to fit under the cap and clamps at 0 once
        # confidence reaches it, so repetition alone can never lift a pair past
        # WEAK_CONFIDENCE_CAP. delta=0 still increments success_count (n accrues).
        current = _current_confidence(key)
        delta = max(0.0, min(WEAK_BOOST_DELTA, WEAK_CONFIDENCE_CAP - current))
        return boost_confidence("routing", key, delta=delta)
    # Unknown/typo outcome must NOT silently boost. Callers pass the literal
    # SUCCESS/FAILURE/NEUTRAL/WEAK_SUCCESS constants; an unrecognized string is
    # a bug to surface, not a default boost that inflates confidence.
    raise ValueError(
        f"unknown routing outcome {outcome!r}; expected one of {SUCCESS!r}, {FAILURE!r}, {NEUTRAL!r}, {WEAK_SUCCESS!r}"
    )
