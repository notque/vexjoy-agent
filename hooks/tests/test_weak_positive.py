#!/usr/bin/env python3
"""Weak-positive routing signal (ADR router-improvement-program C6).

A repeat dispatch of the same agent:skill pair with no intervening failure
counts as WEAK success in the UserPromptSubmit finalizer: a small boost,
bounded so repetition alone can never make a pair high-confidence.

Covers, in order:
  1. apply_outcome weak semantics: smaller-than-acceptance delta; cap
     enforced; counts still accrue at the cap; failure/decay and explicit
     acceptance byte-identical to pre-C6 (the regression direction matters as
     much as the new signal — a loop that gets optimistic by accident is
     worse than one that learns nothing).
  2. Session outcome history in the bridge state file: round-trip, bound.
  3. Finalizer end-to-end (subprocess): first dispatch stays neutral; repeat
     gets the weak boost; intervening tool error blocks it; explicit
     acceptance and attributable rejection unchanged; a rejection turn (even
     unattributable) suppresses the upgrade.
  4. Fixture replay (hooks/tests/fixtures/weak_positive_replay.jsonl): a
     0.5/n=1 weight moves upward, the cap holds after many repeats, and the
     row crosses the n>=5 evidence gate — while shadow-policy thresholds
     (demote floor, tiebreak, evidence gate) still read correctly.

All tests isolate via CLAUDE_LEARNING_DIR + CLAUDE_ROUTING_STATE_DIR; the
live learning DB and /tmp state are never touched.

Run: python3 -m pytest hooks/tests/test_weak_positive.py -v
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
FINALIZER = HOOKS_DIR / "routing-outcome-finalizer.py"
FIXTURE = Path(__file__).parent / "fixtures" / "weak_positive_replay.jsonl"
SCRIPTS_LIB = HOOKS_DIR.parent / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Throwaway learning DB + routing state dir; both env vars set so the
    in-process seeding and the finalizer subprocess agree on locations."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setenv("CLAUDE_ROUTING_STATE_DIR", str(state_dir))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return {"db_dir": db_dir, "state_dir": state_dir, "ldb": ldb}


def _row(key: str) -> dict:
    """Read the routing weight row straight from the throwaway DB."""
    from learning_db_v2 import get_db_path

    conn = sqlite3.connect(get_db_path())
    try:
        r = conn.execute(
            "SELECT confidence, observation_count, success_count, failure_count "
            "FROM learnings WHERE topic = 'routing' AND key = ?",
            (key,),
        ).fetchone()
    finally:
        conn.close()
    assert r is not None, f"no routing row for {key}"
    return {"confidence": r[0], "n": r[1], "success": r[2], "failure": r[3]}


def _seed(ldb, key: str) -> None:
    ldb.record_learning(
        topic="routing",
        key=key,
        value=f"routing-decision: {key}",
        category="effectiveness",
        source="replay-fixture",
    )


# --- 1. apply_outcome weak semantics -----------------------------------------


class TestApplyOutcomeWeak:
    KEY = "agent-x:skill-x"

    @pytest.fixture(autouse=True)
    def _seeded(self, env):
        _seed(env["ldb"], self.KEY)
        self.ldb = env["ldb"]

    def test_weak_boosts_by_weak_delta(self):
        import routing_outcome_score as ros

        before = _row(self.KEY)
        ros.apply_outcome(self.KEY, ros.WEAK_SUCCESS)
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"] + ros.WEAK_BOOST_DELTA)
        assert after["success"] == before["success"] + 1

    def test_weak_delta_smaller_than_acceptance_boost(self):
        import routing_outcome_score as ros

        assert ros.WEAK_BOOST_DELTA < ros.BOOST_DELTA < ros.DECAY_DELTA

    def test_cap_enforced_counts_still_accrue(self):
        """Many weak boosts stop at the cap; success_count keeps counting."""
        import routing_outcome_score as ros

        for _ in range(20):
            ros.apply_outcome(self.KEY, ros.WEAK_SUCCESS)
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(ros.WEAK_CONFIDENCE_CAP)
        assert after["confidence"] <= ros.WEAK_CONFIDENCE_CAP + 1e-9
        assert after["success"] == 20  # evidence accrues past the cap

    def test_weak_only_row_stays_below_high_confidence(self):
        """Repetition alone can never make a pair high-confidence (>= 0.70)."""
        import routing_outcome_score as ros

        for _ in range(50):
            ros.apply_outcome(self.KEY, ros.WEAK_SUCCESS)
        assert _row(self.KEY)["confidence"] < 0.70

    def test_weak_never_lowers_a_row_above_the_cap(self):
        """Explicit acceptances may push past the cap; weak leaves it there."""
        import routing_outcome_score as ros

        for _ in range(5):  # 0.50 + 5*0.05 = 0.75 > cap
            ros.apply_outcome(self.KEY, ros.SUCCESS)
        high = _row(self.KEY)["confidence"]
        assert high > ros.WEAK_CONFIDENCE_CAP
        ros.apply_outcome(self.KEY, ros.WEAK_SUCCESS)
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(high)  # unchanged, not lowered
        assert after["success"] == 6

    # -- regression direction: failure/decay and explicit paths unchanged --

    def test_failure_decay_unchanged_after_weak_boosts(self):
        import routing_outcome_score as ros

        for _ in range(3):
            ros.apply_outcome(self.KEY, ros.WEAK_SUCCESS)
        before = _row(self.KEY)
        ros.apply_outcome(self.KEY, ros.FAILURE)
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"] - ros.DECAY_DELTA)
        assert after["failure"] == before["failure"] + 1

    def test_explicit_success_delta_unchanged(self):
        import routing_outcome_score as ros

        before = _row(self.KEY)["confidence"]
        ros.apply_outcome(self.KEY, ros.SUCCESS)
        assert _row(self.KEY)["confidence"] == pytest.approx(before + ros.BOOST_DELTA)

    def test_neutral_still_noop(self):
        import routing_outcome_score as ros

        before = _row(self.KEY)
        ros.apply_outcome(self.KEY, ros.NEUTRAL)
        assert _row(self.KEY) == before


# --- 2. session outcome history -----------------------------------------------


class TestOutcomeHistory:
    def test_roundtrip(self, env):
        from routing_outcome_state import get_outcome_history, record_outcome_history

        assert get_outcome_history("s1") == {}
        record_outcome_history("s1", {"a:b": "neutral", "c:d": "failure"})
        assert get_outcome_history("s1") == {"a:b": "neutral", "c:d": "failure"}
        record_outcome_history("s1", {"a:b": "weak_success"})  # latest wins
        assert get_outcome_history("s1")["a:b"] == "weak_success"

    def test_bounded_evicts_oldest(self, env):
        from routing_outcome_state import MAX_HISTORY_KEYS, get_outcome_history, record_outcome_history

        record_outcome_history("s1", {f"k{i}:s": "neutral" for i in range(MAX_HISTORY_KEYS + 5)})
        history = get_outcome_history("s1")
        assert len(history) == MAX_HISTORY_KEYS
        assert "k0:s" not in history  # oldest insertion evicted
        assert f"k{MAX_HISTORY_KEYS + 4}:s" in history

    def test_sessions_are_isolated(self, env):
        from routing_outcome_state import get_outcome_history, record_outcome_history

        record_outcome_history("s1", {"a:b": "neutral"})
        assert get_outcome_history("s2") == {}


# --- 3. finalizer end-to-end ---------------------------------------------------


def _finalize(prompt: str, session: str = "sess-1") -> subprocess.CompletedProcess:
    """Run the real finalizer hook against the throwaway env."""
    event = {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": prompt}
    res = subprocess.run(
        [sys.executable, str(FINALIZER)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert res.returncode == 0, res.stderr  # non-blocking contract
    return res


def _pend(key: str, errors: bool = False, session: str = "sess-1") -> None:
    from routing_outcome_state import append_pending_outcome

    append_pending_outcome(session, key, errors)


class TestFinalizerWeakPositive:
    KEY = "agent-x:skill-x"

    @pytest.fixture(autouse=True)
    def _seeded(self, env):
        _seed(env["ldb"], self.KEY)
        self.env = env

    def test_first_dispatch_neutral_prompt_stays_noop(self):
        """Regression: neutral stays neutral for an unrelated next prompt."""
        before = _row(self.KEY)
        _pend(self.KEY)
        _finalize("now refactor the parser module")
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"])
        assert after["success"] == 0 and after["failure"] == 0

    def test_repeat_dispatch_gets_weak_boost(self):
        import routing_outcome_score as ros

        _pend(self.KEY)
        _finalize("now refactor the parser module")  # 1st: neutral, history recorded
        before = _row(self.KEY)
        _pend(self.KEY)
        _finalize("add a retry to the fetch helper")  # repeat: weak boost
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"] + ros.WEAK_BOOST_DELTA)
        assert after["success"] == 1 and after["failure"] == 0

    def test_weak_outcome_event_logged(self):
        _pend(self.KEY)
        _finalize("now refactor the parser module")
        _pend(self.KEY)
        _finalize("add a retry to the fetch helper")
        lines = (self.env["db_dir"] / "route-events.jsonl").read_text().splitlines()
        events = [json.loads(ln) for ln in lines]
        weak = [e for e in events if e.get("outcome") == "weak_success"]
        assert len(weak) == 1
        assert weak[0]["key"] == self.KEY
        assert weak[0]["reason"] == "repeat-dispatch-no-failure"
        assert weak[0]["routing_relevant"] is True

    def test_intervening_tool_error_blocks_weak_boost(self):
        import routing_outcome_score as ros

        _pend(self.KEY)
        _finalize("now refactor the parser module")  # neutral, history=neutral
        _pend(self.KEY, errors=True)
        _finalize("add a retry to the fetch helper")  # failure: decay, history=failure
        decayed = _row(self.KEY)
        assert decayed["confidence"] == pytest.approx(0.50 - ros.DECAY_DELTA)
        assert decayed["failure"] == 1
        _pend(self.KEY)
        _finalize("sort the report output by date")  # repeat AFTER failure: no boost
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(decayed["confidence"])
        assert after["success"] == 0

    def test_explicit_acceptance_path_unchanged_on_repeat(self):
        """An acceptance turn still earns the FULL boost, never the weak one."""
        import routing_outcome_score as ros

        _pend(self.KEY)
        _finalize("now refactor the parser module")  # history=neutral
        before = _row(self.KEY)
        _pend(self.KEY)
        _finalize("thanks, that worked")
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"] + ros.BOOST_DELTA)

    def test_attributable_rejection_still_decays_on_repeat(self):
        """Regression: the failure path outranks the weak signal."""
        import routing_outcome_score as ros

        _pend(self.KEY)
        _finalize("now refactor the parser module")  # history=neutral
        before = _row(self.KEY)
        _pend(self.KEY)
        _finalize("that's wrong, the tests fail")
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"] - ros.DECAY_DELTA)
        assert after["failure"] == 1

    def test_rejection_turn_suppresses_weak_even_unattributable(self, env):
        """Multi-dispatch turn + a complaint: nothing gets the weak upgrade."""
        other = "agent-y:skill-y"
        _seed(env["ldb"], other)
        _pend(self.KEY)
        _finalize("now refactor the parser module")  # history[KEY]=neutral
        before = _row(self.KEY)
        _pend(self.KEY)
        _pend(other)  # 2 live pendings => reaction unattributable
        _finalize("that's wrong, the tests fail")
        after = _row(self.KEY)
        assert after["confidence"] == pytest.approx(before["confidence"])  # no boost, no decay
        assert after["success"] == 0 and after["failure"] == 0

    def test_weak_basis_counter_recorded(self):
        _pend(self.KEY)
        _finalize("now refactor the parser module")
        _pend(self.KEY)
        _finalize("add a retry to the fetch helper")
        from learning_db_v2 import get_db_path

        conn = sqlite3.connect(get_db_path())
        try:
            r = conn.execute(
                "SELECT count FROM routing_outcome_basis WHERE key = ? AND basis = 'repeat_dispatch_weak'",
                (self.KEY,),
            ).fetchone()
        finally:
            conn.close()
        assert r is not None and r[0] == 1


# --- 4. fixture replay ----------------------------------------------------------


def _replay_fixture(env) -> None:
    """Drive the pipeline exactly as the hooks do: a dispatch event records the
    decision row + pending entry (action A); a prompt event runs the REAL
    finalizer hook as a subprocess."""
    session = "replay-1"
    for line in FIXTURE.read_text().splitlines():
        event = json.loads(line)
        if event["type"] == "dispatch":
            _seed(env["ldb"], event["key"])
            _pend(event["key"], errors=event["errors"], session=session)
        else:
            _finalize(event["text"], session=session)


class TestFixtureReplay:
    KEY_A = "python-general-engineer:test-driven-development"  # 12 clean repeats
    KEY_B = "golang-general-engineer:go-patterns"  # clean, FAILURE, clean

    def test_replay_moves_weight_up_and_cap_holds(self, env):
        import routing_outcome_score as ros

        _replay_fixture(env)
        a = _row(self.KEY_A)
        # Before: 0.5 / n=1 (the starved baseline). After 12 dispatches / 11
        # repeats: capped confidence, full evidence trail.
        assert a["n"] == 12
        assert a["success"] == 11
        assert a["failure"] == 0
        assert a["confidence"] == pytest.approx(ros.WEAK_CONFIDENCE_CAP)
        assert a["confidence"] <= ros.WEAK_CONFIDENCE_CAP + 1e-9  # cap holds
        assert a["confidence"] < 0.70  # never high-confidence on repetition alone

    def test_replay_intervening_failure_blocks_weak(self, env):
        _replay_fixture(env)
        b = _row(self.KEY_B)
        # neutral, then tool-error decay, then a repeat that must NOT boost.
        # NOTE: confidence reads 0.50, not 0.42 — the recorder's upsert
        # (record_learning: confidence = max(confidence, excluded.confidence))
        # re-floors a decayed row to the 0.5 default on the NEXT dispatch.
        # Pre-existing action-A behavior, untouched here. What C6 must prove:
        # the repeat after a failure earns NO weak boost — success stays 0 and
        # confidence never rises above the recorder's floor.
        assert b["n"] == 3
        assert b["failure"] == 1
        assert b["success"] == 0
        assert b["confidence"] <= 0.50 + 1e-9

    def test_replayed_row_crosses_evidence_gate(self, env):
        """A weak-signal row with n>=5 is evidence-eligible; the shadow-policy
        thresholds (evidence gate, demote floor, tiebreak) read it correctly."""
        _replay_fixture(env)
        sys.path.insert(0, str(SCRIPTS_LIB))
        import route_policy

        a = _row(self.KEY_A)
        assert a["n"] >= route_policy.MIN_OBSERVATIONS
        weights = {self.KEY_A: a}
        # Evidence-eligible + healthy: the pick stands on merit, not on the gate.
        result = route_policy.health_adjust({"key": self.KEY_A, "confidence": 0.9}, [], weights, [])
        assert result["action"] == "keep"
        assert "semantic pick stands" in result["reason"]
        # A capped weak-only row can never sit on the demote floor.
        assert not route_policy._is_floor(a)
        # Threshold regression: a genuine floor row still demotes ...
        floor = {"confidence": 0.20, "n": 6, "success": 1, "failure": 4}
        healthy = {"confidence": 0.65, "n": 12, "success": 11, "failure": 0}
        moved = route_policy.health_adjust(
            {"key": "bad:route", "confidence": 0.9},
            [self.KEY_A],
            {"bad:route": floor, self.KEY_A: healthy},
            [],
        )
        assert moved["action"] == "demote"
        # ... and the evidence gate still protects an n<5 pick from demotion.
        fresh = {"confidence": 0.10, "n": 2, "success": 0, "failure": 2}
        kept = route_policy.health_adjust(
            {"key": "new:route", "confidence": 0.9},
            [self.KEY_A],
            {"new:route": fresh, self.KEY_A: healthy},
            [],
        )
        assert kept["action"] == "keep"
