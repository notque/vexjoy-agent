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
    """
    from learning_db_v2 import get_db_path, init_db

    try:
        init_db()  # ensure schema/file exist before SELECT
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


def apply_outcome(key: str, failure: bool) -> float:
    """Boost (success) or decay (failure) the routing row. Returns new confidence.

    Caller MUST gate on decision_row_exists(key) first.
    """
    from learning_db_v2 import boost_confidence, decay_confidence

    if failure:
        return decay_confidence("routing", key, delta=DECAY_DELTA)
    return boost_confidence("routing", key, delta=BOOST_DELTA)
