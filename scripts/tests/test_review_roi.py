"""Tests for the `review-roi` subcommand in learning-db.py (ADR: review-tier-roi).

Covers:
- Per-tier averaging math over rightsizing:tier{N} rows (findings + cost).
- The <20 insufficient-data guard: below threshold => insufficient_data true and
  no tier labeled "best"; at/above => false.
- Cost nullability: rows with tokens "-" are skipped; an all-"-" tier reports
  avg_tokens null (n/a), not 0.
"""

from __future__ import annotations

import argparse
import importlib
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

# Force the repo hooks/lib copy of learning_db_v2 ahead of any ~/.claude copy,
# mirroring test_learning_roi.py.
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")

sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
learning_db = importlib.import_module("learning-db")
sys.path.pop(0)

sys.path.insert(0, _repo_hooks_lib)
if "learning_db_v2" in sys.modules:
    del sys.modules["learning_db_v2"]
import learning_db_v2 as _ld2_repo

for attr_name in dir(_ld2_repo):
    if hasattr(learning_db, attr_name) and not attr_name.startswith("__"):
        try:
            setattr(learning_db, attr_name, getattr(_ld2_repo, attr_name))
        except (AttributeError, TypeError):
            pass


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    learning_db_v2.init_db()
    return db_dir


def _seed_tier(tier, *, critical, high, medium, tokens="-", wall="-", reviews=1):
    """Seed a rightsizing:tier{N} row, bumping observation_count to `reviews`.

    Value uses the pipe-delimited `k: v` envelope cmd_review_roi parses.
    """
    value = (
        f"tier: {tier} | files: 10 | packages: 2 | agents_dispatched: 12 | "
        f"findings_critical: {critical} | findings_high: {high} | "
        f"findings_medium: {medium} | tokens: {tokens} | wall_clock_s: {wall}"
    )
    for _ in range(reviews):
        _ld2_repo.record_learning(
            topic="routing",
            key=f"rightsizing:tier{tier}",
            value=value,
            category="effectiveness",
            tags=["routing", "rightsizing", f"tier{tier}"],
            source="hook:routing-decision-recorder",
        )


def _run_json():
    """Invoke cmd_review_roi --json, return the parsed JSON list."""
    import json as _json

    buf = io.StringIO()
    with redirect_stdout(buf):
        learning_db.cmd_review_roi(argparse.Namespace(json=True))
    return _json.loads(buf.getvalue())


def _run_human():
    buf = io.StringIO()
    with redirect_stdout(buf):
        learning_db.cmd_review_roi(argparse.Namespace(json=False))
    return buf.getvalue()


# --- ROI averaging math (test 3) -------------------------------------------


class TestRoiMath:
    def test_per_tier_averages(self, isolated_db):
        # Two tiers, each seeded so observation_count = reviews.
        _seed_tier(1, critical=0, high=2, medium=4, reviews=14)
        _seed_tier(3, critical=1, high=3, medium=6, tokens="84000", wall="310", reviews=8)
        rows = {r["tier"]: r for r in _run_json()}

        assert rows[1]["reviews"] == 14
        assert rows[1]["avg_critical"] == 0.0
        assert rows[1]["avg_high"] == 2.0
        assert rows[1]["avg_medium"] == 4.0

        assert rows[3]["reviews"] == 8
        assert rows[3]["avg_critical"] == 1.0
        assert rows[3]["avg_tokens"] == 84000.0
        assert rows[3]["avg_wall_clock_s"] == 310.0

    def test_tiers_sorted_ascending(self, isolated_db):
        _seed_tier(4, critical=1, high=1, medium=1, reviews=11)
        _seed_tier(2, critical=0, high=1, medium=2, reviews=11)
        tiers = [r["tier"] for r in _run_json()]
        assert tiers == sorted(tiers)


# --- Insufficient-data guard (test 4) --------------------------------------


class TestInsufficientDataGuard:
    def test_below_threshold_flags_insufficient(self, isolated_db):
        # 5 + 4 = 9 findings-bearing reviews, under ROI_MIN_REVIEWS (20).
        _seed_tier(1, critical=0, high=1, medium=2, reviews=5)
        _seed_tier(2, critical=0, high=2, medium=3, reviews=4)
        rows = _run_json()
        assert all(r["insufficient_data"] is True for r in rows)
        # No tier is labeled "best" below threshold.
        assert not any(r.get("best") for r in rows)

    def test_below_threshold_human_banner(self, isolated_db):
        _seed_tier(1, critical=0, high=1, medium=2, reviews=9)
        out = _run_human()
        assert "INSUFFICIENT DATA" in out
        assert "do not act on them" in out

    def test_at_threshold_is_sufficient(self, isolated_db):
        # 20 total findings-bearing reviews meets the threshold (>= 20).
        _seed_tier(1, critical=0, high=1, medium=2, reviews=10)
        _seed_tier(3, critical=1, high=2, medium=3, reviews=10)
        rows = _run_json()
        assert all(r["insufficient_data"] is False for r in rows)

    def test_min_reviews_constant_is_20(self):
        assert learning_db.ROI_MIN_REVIEWS == 20


# --- Cost nullability (test 5) ---------------------------------------------


class TestCostNullability:
    def test_all_dash_tokens_report_null(self, isolated_db):
        # A tier whose rows all carry tokens "-" reports avg_tokens null, not 0.
        _seed_tier(1, critical=0, high=1, medium=2, reviews=21)
        row = next(r for r in _run_json() if r["tier"] == 1)
        assert row["avg_tokens"] is None
        assert row["avg_wall_clock_s"] is None

    def test_human_shows_na_for_null_cost(self, isolated_db):
        _seed_tier(1, critical=0, high=1, medium=2, reviews=21)
        out = _run_human()
        assert "n/a" in out

    def test_empty_db_reports_no_data(self, isolated_db):
        rows = _run_json()
        assert rows == []
        out = _run_human()
        assert out.strip() != ""
