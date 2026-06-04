#!/usr/bin/env python3
"""Tests for staleness decay toward neutral (0.5) on routing rows (spec T5).

The confidence-decay Stop hook decays entries untouched > 30 days. For
`topic='routing'` rows it must pull confidence TOWARD 0.5 instead of the
monotonic -0.05-toward-0 used for every other topic:

    conf += (0.5 - conf) * 0.1

So a stale routing row above 0.5 drops toward 0.5, one below 0.5 rises toward
0.5, and a fresh routing row (last_seen within 30 days) is untouched.
Non-routing rows keep the old -0.05 behavior. The decay never touches
last_seen, observation_count, or success/failure counts.

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


def test_stale_routing_below_half_pulls_up_toward_half(db):
    _seed(db, "routing", "rare:skill", 0.32, STALE)
    res = _run_hook(db)
    assert res.returncode == 0
    new = _read(db, "routing", "rare:skill")["confidence"]
    # 0.32 + (0.5 - 0.32) * 0.1 = 0.338
    assert new == pytest.approx(0.338, abs=1e-6)


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
