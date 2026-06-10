#!/usr/bin/env python3
"""Tests for staleness decay toward neutral (0.5) on routing rows (spec T5).

The confidence-decay Stop hook decays entries untouched > 30 days. For
`topic='routing'` rows it must pull confidence TOWARD 0.5 instead of the
monotonic -0.05-toward-0 used for every other topic:

    conf += (0.5 - conf) * 0.1

Floor guard: staleness must never RAISE routing confidence, so only rows
above 0.5 decay (downward toward 0.5). A stale routing row above 0.5 drops
toward 0.5; one at or below 0.5 is skipped (preserves negative evidence so a
sub-floor row stays floor-demote-eligible); a fresh routing row (last_seen
within 30 days) is untouched. Non-routing rows keep the old -0.05 behavior.
The decay never touches last_seen, observation_count, or success/failure
counts.

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR - never the real DB.

Run with: python3 -m pytest hooks/tests/test_confidence_decay_neutral.py -v
"""

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
HOOK_PATH = HOOKS_DIR / "confidence-decay.py"

STALE = (datetime.now() - timedelta(days=45)).isoformat()
FRESH = (datetime.now() - timedelta(days=2)).isoformat()


def _seed(db_path: Path, topic: str, key: str, confidence: float, last_seen: str) -> None:
    """Insert one learning row directly, bypassing boost/decay helpers."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO learnings
            (topic, key, value, category, confidence, source,
             observation_count, success_count, failure_count,
             first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (topic, key, "v", "effectiveness", confidence, "seed", 5, 3, 0, last_seen, last_seen),
    )
    conn.commit()
    conn.close()


def _read(db_path: Path, topic: str, key: str) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT confidence, last_seen, observation_count, success_count, failure_count "
        "FROM learnings WHERE topic = ? AND key = ?",
        (topic, key),
    ).fetchone()
    conn.close()
    return row


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return db_dir / "learning.db"


def _run_hook(env_dir: Path) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env["CLAUDE_LEARNING_DIR"] = str(env_dir.parent)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="",
        capture_output=True,
        text=True,
        env=env,
    )


def test_stale_routing_above_half_pulls_down_toward_half(db):
    _seed(db, "routing", "implementer:tdd", 0.90, STALE)
    res = _run_hook(db)
    assert res.returncode == 0
    new = _read(db, "routing", "implementer:tdd")["confidence"]
    # 0.90 + (0.5 - 0.90) * 0.1 = 0.86
    assert new == pytest.approx(0.86, abs=1e-6)


def test_stale_routing_below_half_is_not_rescued(db):
    # Floor guard: staleness must never RAISE confidence. A below-baseline row
    # is skipped, not pulled up toward 0.5 (which would erase negative evidence).
    _seed(db, "routing", "rare:skill", 0.32, STALE)
    res = _run_hook(db)
    assert res.returncode == 0
    assert _read(db, "routing", "rare:skill")["confidence"] == pytest.approx(0.32, abs=1e-6)


def test_stale_routing_subfloor_stays_floor_eligible(db):
    # Finding [104]/[105]: a sub-floor routing row (conf < FLOOR_CONFIDENCE=0.30,
    # fail>=3, n>=5) must NOT be rescued above the 0.30 floor by staleness decay.
    # Prune does not protect it: prune needs last_seen > 90 days, but this row is
    # only 45 days stale, so it reaches the staleness UPDATE. Assert confidence
    # did not rise and the row stays floor-demote-eligible (< 0.30).
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO learnings
            (topic, key, value, category, confidence, source,
             observation_count, success_count, failure_count,
             first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("routing", "bad:pair", "v", "effectiveness", 0.28, "seed", 5, 1, 3, STALE, STALE),
    )
    conn.commit()
    conn.close()
    res = _run_hook(db)
    assert res.returncode == 0
    new = _read(db, "routing", "bad:pair")["confidence"]
    assert new == pytest.approx(0.28, abs=1e-6)  # unchanged, not raised to 0.302
    assert new < 0.30  # still floor-demote-eligible


def test_fresh_routing_row_untouched(db):
    _seed(db, "routing", "fresh:pair", 0.90, FRESH)
    res = _run_hook(db)
    assert res.returncode == 0
    assert _read(db, "routing", "fresh:pair")["confidence"] == pytest.approx(0.90, abs=1e-6)


def test_non_routing_keeps_old_minus_005(db):
    _seed(db, "error_pattern", "missing_file", 0.90, STALE)
    res = _run_hook(db)
    assert res.returncode == 0
    # old behavior: monotonic -0.05
    assert _read(db, "error_pattern", "missing_file")["confidence"] == pytest.approx(0.85, abs=1e-6)


def test_staleness_decay_does_not_touch_counts_or_last_seen(db):
    _seed(db, "routing", "no:sidefx", 0.90, STALE)
    _run_hook(db)
    row = _read(db, "routing", "no:sidefx")
    assert row["last_seen"] == STALE
    assert row["observation_count"] == 5
    assert row["success_count"] == 3
    assert row["failure_count"] == 0


def test_hook_exits_zero_on_empty_db(db):
    res = _run_hook(db)
    assert res.returncode == 0


def test_stale_routing_at_half_is_noop_and_not_counted(db):
    # Finding #15: a row already at the 0.5 baseline is a no-op; the > 0.5 guard
    # excludes it so it is neither changed nor counted in the `decayed` metric.
    _seed(db, "routing", "neutral:pair", 0.50, STALE)
    res = _run_hook(db)
    assert res.returncode == 0
    assert _read(db, "routing", "neutral:pair")["confidence"] == pytest.approx(0.50, abs=1e-6)
    assert "decayed=0" in res.stderr or "decayed" not in res.stderr
