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


def test_statistics():
    """get_stats reports the documented keys."""
    init_db()
    stats = get_stats()
    assert {"total_learnings", "by_category", "high_confidence"} <= stats.keys()
    assert stats["total_learnings"] >= 0


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
