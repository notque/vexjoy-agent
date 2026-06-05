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


def outcome_basis(errors: bool, reaction_failure: bool) -> str:
    """The evidence basis for a finalized outcome — one of three labels.

    Pure and module-level so tests import it directly. Order matters: a tool
    error is the strongest, most attributable signal, so it wins even when a
    user reaction also fired.

      tool_errors_only     dispatch's own error flag fired (a real signal)
      rejection_detected   user complaint fired, no error (a real signal)
      default_no_complaint success on silence — the silent-failure case

    `default_no_complaint` covers clean accepted/neutral AND the multi-dispatch
    case where the turn reaction is ignored: in both, no signal scored THIS
    entry, so its success rests on no complaint.
    """
    if errors:
        return "tool_errors_only"
    if reaction_failure:
        return "rejection_detected"
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


def apply_outcome(key: str, failure: bool, basis: str | None = None) -> float:
    """Boost (success) or decay (failure) the routing row. Returns new confidence.

    Caller MUST gate on decision_row_exists(key) first.

    `basis` is label-only: when given, increment its per-route counter (best
    effort) for route-health's silent-success report. It does NOT change the
    boost/decay — that is byte-identical with or without basis. Default None
    keeps every pre-PR caller and test unchanged.
    """
    from learning_db_v2 import boost_confidence, decay_confidence

    if basis:
        _record_basis(key, basis)
    if failure:
        return decay_confidence("routing", key, delta=DECAY_DELTA)
    return boost_confidence("routing", key, delta=BOOST_DELTA)
