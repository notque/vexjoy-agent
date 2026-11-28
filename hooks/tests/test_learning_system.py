#!/usr/bin/env python3
"""
Tests for the learning hook system (v2 unified database).

Run with: python3 -m pytest hooks/tests/test_learning_system.py -v
"""

import sys
import uuid
from pathlib import Path

import pytest

# Add parent lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import learning_db_v2 as ldb


@pytest.fixture(autouse=True)
def _isolate_learning_db(tmp_path, monkeypatch):
    """Give each test a fresh learning DB so earlier tests cannot contaminate.

    Scripts tests may delete and reimport learning_db_v2, creating a second
    module object.  Ensure sys.modules points at our copy and reset its
    _initialized flag so init_db() reruns against the temp directory.
    """
    sys.modules["learning_db_v2"] = ldb
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    monkeypatch.setattr(ldb, "_initialized", False)


# Module-level aliases used by tests.
get_stats = ldb.get_stats
init_db = ldb.init_db
record_learning = ldb.record_learning


def test_record_error_learning_and_boost_past_threshold():
    """An error learning keyed by signature becomes high-confidence after boosts."""
    init_db()
    topic, signature = "missing_file", f"sig-{uuid.uuid4().hex[:16]}"

    result = record_learning(
        topic=topic,
        key=signature,
        value="Test error -> Test solution",
        category="error",
        confidence=0.55,
        source="test",
        error_signature=signature,
        error_type=topic,
    )
    assert result["is_new"] is True
    assert result["confidence"] < 0.7

    for _ in range(3):
        ldb.boost_confidence(topic, signature, delta=0.12)

    with ldb.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM learnings WHERE error_signature = ? AND confidence >= 0.7",
            (signature,),
        ).fetchone()
    assert row is not None


def test_confidence_updates_stay_bounded():
    """Boost raises confidence, decay lowers it, and both clamp to [0, 1]."""
    init_db()
    topic, key = "test-confidence", f"conf-test-{uuid.uuid4().hex[:8]}"

    result = record_learning(
        topic=topic, key=key, value="Confidence test entry", category="error", confidence=0.55, source="test"
    )
    conf = ldb.boost_confidence(topic, key, delta=0.12)
    assert conf > result["confidence"]

    for _ in range(15):
        conf = ldb.decay_confidence(topic, key, delta=0.18)
    assert conf >= 0.0

    for _ in range(25):
        conf = ldb.boost_confidence(topic, key, delta=0.12)
    assert 0.5 < conf <= 1.0


def test_fix_type_recording():
    """fix_type and fix_action are stored on the row."""
    init_db()
    topic, key = "syntax_error", f"sig-{uuid.uuid4().hex[:16]}"

    record_learning(
        topic=topic,
        key=key,
        value="Fix type test error -> Use skill to fix",
        category="error",
        confidence=0.65,
        source="test",
        error_signature=key,
        error_type=topic,
        fix_type="skill",
        fix_action="systematic-debugging",
    )

    with ldb.get_connection() as conn:
        row = conn.execute(
            "SELECT fix_type, fix_action FROM learnings WHERE topic = ? AND key = ?", (topic, key)
        ).fetchone()
    assert row is not None
    assert (row["fix_type"], row["fix_action"]) == ("skill", "systematic-debugging")


def test_concurrent_read_modify_writes_do_not_lose_updates():
    """BEGIN IMMEDIATE serializes concurrent accumulate_rightsizing/boost/decay/record_session writes."""
    import threading

    init_db()
    record_learning(
        topic="routing",
        key="conc:skill",
        value="v",
        category="effectiveness",
        confidence=0.5,
        source="test",
    )

    n_threads = 6
    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []

    def worker(idx: int) -> None:
        try:
            barrier.wait(timeout=5.0)
            ldb.accumulate_rightsizing(tier=2, critical=1, high=2, medium=3, tokens=100, wall_clock_s=10)
            if idx % 2 == 0:
                ldb.boost_confidence("routing", "conc:skill", delta=0.05)
            else:
                ldb.decay_confidence("routing", "conc:skill", delta=0.05)
            ldb.record_session("conc-sess", files_modified=1, tools_used=2)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert not errors, f"concurrent write errors: {errors!r}"
    with ldb.get_connection() as conn:
        rs = conn.execute("SELECT value, observation_count FROM learnings WHERE key = 'rightsizing:tier2'").fetchone()
        assert rs["observation_count"] == n_threads
        assert f"reviews: {n_threads}" in rs["value"]
        assert f"sum_critical: {n_threads}" in rs["value"]
        assert f"sum_tokens: {n_threads * 100}" in rs["value"]

        rt = conn.execute("SELECT success_count, failure_count FROM learnings WHERE key = 'conc:skill'").fetchone()
        assert rt["success_count"] == n_threads // 2
        assert rt["failure_count"] == n_threads // 2

        sess = conn.execute("SELECT files_modified, tools_used FROM sessions WHERE session_id = 'conc-sess'").fetchone()
        assert sess["files_modified"] == n_threads
        assert sess["tools_used"] == n_threads * 2


def test_instruction_compliance_utc_and_julianday_window():
    """instruction_compliance writes UTC ISO and queries via julianday across legacy 'T' and UTC rows."""
    from datetime import datetime, timedelta, timezone

    init_db()
    ldb.record_instruction_compliance_batch([("M01", True, "s1", True), ("M01", False, "s1", True)])
    with ldb.get_connection() as conn:
        ts_vals = [r[0] for r in conn.execute("SELECT timestamp FROM instruction_compliance").fetchall()]
        assert len(ts_vals) == 2
        for ts in ts_vals:
            dt = datetime.fromisoformat(ts)
            assert dt.tzinfo == timezone.utc

        # Insert a legacy naive 'T' row inside the window and an expired row outside the window.
        recent_legacy = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
        expired_legacy = (datetime.now(timezone.utc) - timedelta(days=45)).replace(tzinfo=None).isoformat()
        conn.execute(
            "INSERT INTO instruction_compliance (instruction_id, compliant, session_id, directive_expected, timestamp) "
            "VALUES ('M01', 0, 's-legacy', 1, ?), ('M01', 0, 's-old', 1, ?)",
            (recent_legacy, expired_legacy),
        )
        conn.commit()

    rates = ldb.query_instruction_skip_rate(days=30)
    assert len(rates) == 1
    assert rates[0]["instruction_id"] == "M01"
    # 2 UTC rows + 1 recent legacy 'T' row = 3 scored observations (2 skipped); expired row excluded.
    assert rates[0]["scored_observations"] == 3
    assert rates[0]["scored_non_compliant"] == 2


def test_prune_ancillary_utc_alignment_governance_and_sessions():
    """governance_events and sessions store UTC timestamps so prune_ancillary does not skew by timezone."""
    from datetime import datetime, timedelta, timezone

    init_db()
    ldb.record_governance_event("hook_blocked", event_id="gov-fresh", blocked=True)
    ldb.record_session("sess-fresh", files_modified=1)
    old_utc = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    with ldb.get_connection() as conn:
        gov_ts = conn.execute("SELECT created_at FROM governance_events WHERE id = 'gov-fresh'").fetchone()[0]
        sess_ts = conn.execute("SELECT start_time FROM sessions WHERE session_id = 'sess-fresh'").fetchone()[0]
        assert datetime.fromisoformat(gov_ts).tzinfo == timezone.utc
        assert datetime.fromisoformat(sess_ts).tzinfo == timezone.utc

        conn.execute(
            "INSERT INTO governance_events (id, event_type, blocked, created_at) VALUES ('gov-old', 'hook_blocked', 1, ?)",
            (old_utc,),
        )
        conn.execute(
            "INSERT INTO sessions (session_id, start_time) VALUES ('sess-old', ?)",
            (old_utc,),
        )
        conn.commit()

    counts = ldb.prune_ancillary(governance_days=1, sessions_days=1)
    assert counts["governance_events"] == 1
    assert counts["sessions"] == 1
    with ldb.get_connection() as conn:
        assert [r[0] for r in conn.execute("SELECT id FROM governance_events").fetchall()] == ["gov-fresh"]
        assert [r[0] for r in conn.execute("SELECT session_id FROM sessions").fetchall()] == ["sess-fresh"]


def test_record_evidence_route_decision_uses_single_connection_and_is_atomic(monkeypatch):
    """record_evidence_route_decision writes both tables in one connection/transaction."""
    init_db()
    conn_opens = 0
    real_get_connection = ldb.get_connection

    from contextlib import contextmanager

    @contextmanager
    def counting_conn():
        nonlocal conn_opens
        conn_opens += 1
        with real_get_connection() as conn:
            yield conn

    monkeypatch.setattr(ldb, "get_connection", counting_conn)
    row = ldb.record_evidence_route_decision(
        session_id="s-atomic",
        agent="general-purpose",
        skill="programming",
        decision_id="dec-atomic-1",
    )
    assert conn_opens == 1
    assert row["decision_id"] == "dec-atomic-1"

    # Negative/atomicity check: if the companion event write fails, the decision row rolls back.
    def boom(*_args, **_kwargs):
        raise RuntimeError("injected event write failure")

    monkeypatch.setattr(ldb, "_upsert_evidence_event", boom)
    with pytest.raises(RuntimeError, match="injected event write failure"):
        ldb.record_evidence_route_decision(
            session_id="s-atomic",
            agent="general-purpose",
            skill="programming",
            decision_id="dec-atomic-rollback",
        )
    with real_get_connection() as conn:
        found = conn.execute(
            "SELECT decision_id FROM evidence_route_decisions WHERE decision_id = 'dec-atomic-rollback'"
        ).fetchone()
    assert found is None


def test_concurrent_update_evidence_route_outcome_serializes_with_begin_immediate():
    """Concurrent update_evidence_route_outcome calls fill N distinct open rows without lock races."""
    import threading

    init_db()
    n_threads = 6
    for i in range(n_threads):
        ldb.record_evidence_route_decision(
            session_id="s-conc-outcome",
            agent="general-purpose",
            skill="programming",
            decision_id=f"dec-conc-{i}",
        )

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []

    def worker(idx: int) -> None:
        try:
            barrier.wait(timeout=5.0)
            ldb.update_evidence_route_outcome(
                route_key="general-purpose:programming",
                session_id="s-conc-outcome",
                outcome="success",
                outcome_basis=f"worker-{idx}",
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert not errors, f"concurrent outcome update errors: {errors!r}"
    with ldb.get_connection() as conn:
        rows = conn.execute(
            "SELECT decision_id, outcome, outcome_basis FROM evidence_route_decisions WHERE session_id = 's-conc-outcome'"
        ).fetchall()
    assert len(rows) == n_threads
    assert all(r["outcome"] == "success" for r in rows)
    assert len({r["outcome_basis"] for r in rows}) == n_threads
