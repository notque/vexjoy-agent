#!/usr/bin/env python3
"""Tests for outcome-basis capture and storage (ADR: silent-failure-outcome-quality).

The routing feedback loop scores a dispatch success on silence — no complaint is
read as success. This is the "silent-failure" blind spot. This PR labels each
finalized outcome with its evidence basis (one of three values) and counts those
labels per route, so route-health can report what share of outcomes rest on
silence vs a real signal. Boost/decay is unchanged — label and counter only.

Covers:
- outcome_basis() maps (errors, reaction_failure) to the three labels.
- _record_basis increments the right per-(key, basis) counter; best-effort.
- apply_outcome(basis=...) writes the counter AND boosts/decays exactly as before.
- apply_outcome(basis=None) is byte-identical to the pre-PR behavior (regression).

Uses a throwaway learning.db via CLAUDE_LEARNING_DIR — never the real DB.

Run with: python3 -m pytest hooks/tests/test_routing_outcome_basis.py -v
"""

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point the learning DB at a throwaway dir; force a fresh init."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    yield {"db_dir": db_dir, "ldb": ldb}


def _seed_routing_row(ldb, key: str) -> None:
    """Write a routing decision row so boost/decay has a row to act on."""
    ldb.record_learning(
        topic="routing",
        key=key,
        value=f"routing-decision: {key}",
        category="effectiveness",
        source="test:basis",
    )


def _basis_count(ldb, key: str, basis: str) -> int:
    """Read one per-(key, basis) counter; 0 if absent."""
    with ldb.get_connection() as conn:
        row = conn.execute(
            "SELECT count FROM routing_outcome_basis WHERE key = ? AND basis = ?",
            (key, basis),
        ).fetchone()
    return row["count"] if row else 0


# --- outcome_basis() pure mapping -------------------------------------------


def test_outcome_basis_tool_errors():
    from routing_outcome_score import outcome_basis

    # errors win even if a reaction also fired.
    assert outcome_basis(errors=True, reaction_failure=False) == "tool_errors_only"
    assert outcome_basis(errors=True, reaction_failure=True) == "tool_errors_only"


def test_outcome_basis_rejection():
    from routing_outcome_score import outcome_basis

    assert outcome_basis(errors=False, reaction_failure=True) == "rejection_detected"


def test_outcome_basis_default_no_complaint():
    from routing_outcome_score import outcome_basis

    # clean accepted/neutral OR multi-dispatch ignored reaction => silent success.
    assert outcome_basis(errors=False, reaction_failure=False) == "default_no_complaint"


# --- _record_basis storage --------------------------------------------------


def test_record_basis_increments_counter(db_env):
    from routing_outcome_score import _record_basis

    ldb = db_env["ldb"]
    _record_basis("a:b", "default_no_complaint")
    _record_basis("a:b", "default_no_complaint")
    _record_basis("a:b", "rejection_detected")

    assert _basis_count(ldb, "a:b", "default_no_complaint") == 2
    assert _basis_count(ldb, "a:b", "rejection_detected") == 1
    assert _basis_count(ldb, "a:b", "tool_errors_only") == 0


def test_record_basis_never_raises(monkeypatch):
    """Best-effort: a DB failure is swallowed (bridge never-block contract)."""
    import routing_outcome_score as ros

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(ros, "get_db_path", _boom, raising=False)
    # Must not raise.
    ros._record_basis("x:y", "tool_errors_only")


# --- apply_outcome(basis=...) wiring ----------------------------------------


def test_apply_outcome_success_records_basis_and_boosts(db_env):
    from routing_outcome_score import BOOST_DELTA, apply_outcome

    ldb = db_env["ldb"]
    _seed_routing_row(ldb, "ag:sk")
    new_conf = apply_outcome("ag:sk", failure=False, basis="default_no_complaint")

    # Boost applied (effectiveness baseline 0.50 + BOOST_DELTA).
    assert new_conf == pytest.approx(0.50 + BOOST_DELTA)
    assert _basis_count(ldb, "ag:sk", "default_no_complaint") == 1


def test_apply_outcome_failure_records_basis_and_decays(db_env):
    from routing_outcome_score import DECAY_DELTA, apply_outcome

    ldb = db_env["ldb"]
    _seed_routing_row(ldb, "ag:sk")
    new_conf = apply_outcome("ag:sk", failure=True, basis="tool_errors_only")

    assert new_conf == pytest.approx(0.50 - DECAY_DELTA)
    assert _basis_count(ldb, "ag:sk", "tool_errors_only") == 1


# --- regression: basis=None must be byte-identical to pre-PR behavior -------


def test_apply_outcome_basis_none_no_counter_written(db_env):
    from routing_outcome_score import apply_outcome

    ldb = db_env["ldb"]
    _seed_routing_row(ldb, "ag:sk")
    apply_outcome("ag:sk", failure=False)  # basis defaults None

    with ldb.get_connection() as conn:
        rows = conn.execute("SELECT COUNT(*) AS n FROM routing_outcome_basis").fetchone()
    assert rows["n"] == 0


def test_apply_outcome_basis_none_boosts_identically(db_env):
    from routing_outcome_score import BOOST_DELTA, DECAY_DELTA, apply_outcome

    ldb = db_env["ldb"]
    _seed_routing_row(ldb, "ag:sk")
    boosted = apply_outcome("ag:sk", failure=False)
    assert boosted == pytest.approx(0.50 + BOOST_DELTA)
    decayed = apply_outcome("ag:sk", failure=True)
    assert decayed == pytest.approx(0.50 + BOOST_DELTA - DECAY_DELTA)
