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


def apply_outcome(key: str, outcome: str) -> float:
    """Apply a THREE-WAY routing outcome. Returns new (or unchanged) confidence.

    ``outcome`` is one of:
      - ``"failure"`` — decay the row (errors or attributable rejection).
      - ``"success"`` — boost the row (acceptance / continuation).
      - ``"neutral"`` — NO-OP: no boost, no decay, no count change, no schema
        migration. Returns the row's current confidence unchanged. Neutral is the
        new default for unrelated/new-topic next prompts and clean autonomous Stop
        runs — signal-fidelity fix so future data can contain real negatives
        instead of being drowned by boost-everything.

    A bare ``True``/``False`` is still accepted for back-compat (True=>failure,
    False=>success) but callers should pass an explicit outcome string.

    Any other string raises ``ValueError`` — an unrecognized outcome (e.g. a
    typo) must surface as a bug, never silently boost confidence.

    Caller MUST gate on decision_row_exists(key) first.
    """
    from learning_db_v2 import boost_confidence, decay_confidence

    # Back-compat: legacy callers passed a `failure` bool.
    if outcome is True:
        outcome = FAILURE
    elif outcome is False:
        outcome = SUCCESS

    if outcome == NEUTRAL:
        return _current_confidence(key)  # no-op: read-only, no count change
    if outcome == FAILURE:
        return decay_confidence("routing", key, delta=DECAY_DELTA)
    if outcome == SUCCESS:
        return boost_confidence("routing", key, delta=BOOST_DELTA)
    # Unknown/typo outcome must NOT silently boost. Callers pass the literal
    # SUCCESS/FAILURE/NEUTRAL constants; an unrecognized string is a bug to
    # surface, not a default boost that inflates confidence.
    raise ValueError(f"unknown routing outcome {outcome!r}; expected one of {SUCCESS!r}, {FAILURE!r}, {NEUTRAL!r}")
