#!/usr/bin/env python3
"""Tests for apply_outcome (hooks/lib/routing_outcome_score.py) — three-way + guard.

apply_outcome maps a routing outcome onto a confidence delta:
  - success => boost
  - failure => decay
  - neutral => no-op (read-only)
  - anything else (typo / unknown) => ValueError, NEVER a silent boost.

The last case is the regression guard: pre-fix an unrecognized string fell
through to boost, silently inflating confidence (the skeptic's finding 3a).

All tests point the learning DB at a throwaway dir via CLAUDE_LEARNING_DIR and
seed one routing row first — apply_outcome assumes the caller gated on
decision_row_exists. The live DB is never touched.

Run: python3 -m pytest hooks/tests/test_apply_outcome.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"


@pytest.fixture()
def seeded_key(tmp_path, monkeypatch):
    """Throwaway DB with one routing/effectiveness row; yields its key."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    key = "agent-x:skill-x"
    ldb.record_learning(topic="routing", key=key, value="v", category="effectiveness", source="routing:decision")
    yield key


def _conf(key: str) -> float:
    import routing_outcome_score as ros

    return ros._current_confidence(key)


def test_unknown_outcome_raises_not_boosts(seeded_key) -> None:
    """A typo'd outcome string raises ValueError instead of silently boosting."""
    import routing_outcome_score as ros

    before = _conf(seeded_key)
    with pytest.raises(ValueError, match="unknown routing outcome"):
        ros.apply_outcome(seeded_key, "succes")  # typo
    after = _conf(seeded_key)
    assert after == before  # confidence untouched by the rejected call


def test_neutral_is_noop(seeded_key) -> None:
    """Neutral leaves confidence unchanged."""
    import routing_outcome_score as ros

    before = _conf(seeded_key)
    returned = ros.apply_outcome(seeded_key, ros.NEUTRAL)
    assert returned == before
    assert _conf(seeded_key) == before


def test_success_boosts(seeded_key) -> None:
    """Success raises confidence."""
    import routing_outcome_score as ros

    before = _conf(seeded_key)
    ros.apply_outcome(seeded_key, ros.SUCCESS)
    assert _conf(seeded_key) > before


def test_failure_decays(seeded_key) -> None:
    """Failure lowers confidence."""
    import routing_outcome_score as ros

    before = _conf(seeded_key)
    ros.apply_outcome(seeded_key, ros.FAILURE)
    assert _conf(seeded_key) < before


def test_no_outcome_and_no_failure_raises(seeded_key) -> None:
    """Both outcome and failure= unset is an illegal call: clear ValueError, no boost.

    None is only an internal sentinel for the failure= back-compat path, never a
    valid outcome. The guard rejects it before any confidence change.
    """
    import routing_outcome_score as ros

    before = _conf(seeded_key)
    with pytest.raises(ValueError, match="requires an outcome or a failure="):
        ros.apply_outcome(seeded_key)  # no positional outcome, no failure kwarg
    assert _conf(seeded_key) == before  # confidence untouched


def test_legacy_bool_back_compat(seeded_key) -> None:
    """True=>failure (decay), False=>success (boost) still honored."""
    import routing_outcome_score as ros

    base = _conf(seeded_key)
    ros.apply_outcome(seeded_key, False)  # success
    boosted = _conf(seeded_key)
    assert boosted > base
    ros.apply_outcome(seeded_key, True)  # failure
    assert _conf(seeded_key) < boosted
