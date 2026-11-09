#!/usr/bin/env python3
"""Tests for the route-health counter-metrics to the fallback rate.

The fallback rate alone is gameable: a router told to minimize it can route
every request to one specialist and score 0% with no accuracy gain. These tests
pin the counters that make that trade visible — top-2 concentration, agent
distribution entropy, the misroute rate, and the route-fit negative rate — and
pin the fallback labels (watch above 15%, alarm above 20%, no low alarm). They
also pin "not instrumented" for the two rates no hook writes, and the
route-signal verdict that route-health prints.

Runs route-health as a subprocess against a throwaway learning.db
(CLAUDE_LEARNING_DIR) so the real DB is never touched.

Run with: python3 -m pytest scripts/tests/test_route_health_counter_metrics.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLI = REPO_ROOT / "scripts" / "learning-db.py"
LIB_DIR = REPO_ROOT / "hooks" / "lib"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Throwaway learning.db; return a helper bound to it."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return {"db_dir": db_dir, "ldb": ldb, "env_dir": str(db_dir)}


def _seed_dispatches(ldb, agent: str, n: int, skill: str = "quick") -> None:
    """Write n dispatch rows for one agent (one evidence_route_decisions row each)."""
    # A routing row must exist for route-health to get past its empty-DB return.
    ldb.record_learning(
        topic="routing",
        key=f"{agent}:{skill}",
        value=f"routing-decision: agent={agent} skill={skill}",
        category="effectiveness",
        source="test:route-health",
    )
    for i in range(n):
        ldb.record_evidence_route_decision(
            session_id=f"s-{agent}-{i}",
            agent=agent,
            skill=skill,
            complexity="medium",
            decision_id=f"{agent}:{i}",
        )


def _seed_basis(ldb, key: str, basis: str, n: int) -> None:
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO routing_outcome_basis (key, basis, count) VALUES (?,?,?) "
            "ON CONFLICT(key, basis) DO UPDATE SET count = count + ?",
            (key, basis, n, n),
        )
        conn.commit()


def _seed_misroutes(ldb, n: int) -> None:
    for i in range(n):
        ldb.record_learning(
            topic="routing",
            key=f"general-purpose:quick->should-be-golang-general-engineer:go-patterns-{i}",
            value="request: x | routed_to: general-purpose:quick | should_have_been: y | reason: z",
            category="misroute",
            source="manual:misroute-feedback",
        )


def _run(env_dir: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), "route-health", *extra],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_LEARNING_DIR": env_dir},
    )


def _json(env_dir: str) -> dict:
    res = _run(env_dir, "--json")
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


# --- fallback rate and its band ---------------------------------------------


@pytest.mark.parametrize(
    ("fallback_n", "other_n", "band"),
    [
        (45, 55, "ALARM-HIGH"),  # 45% — the live 44.6% regression
        (18, 82, "WATCH"),  # 18% — above the watch line, below the alarm
        (12, 88, "OK"),  # 12%
        (5, 95, "OK"),  # 5% — low is the wanted result, never an alarm
        (0, 100, "OK"),  # 0% — the counters below carry the gaming check
    ],
)
def test_fallback_band_labels(fallback_n, other_n, band, db_env):
    ldb = db_env["ldb"]
    _seed_dispatches(ldb, "general-purpose", fallback_n)
    _seed_dispatches(ldb, "python-general-engineer", other_n)

    data = _json(db_env["env_dir"])
    assert data["fallback_count"] == fallback_n
    assert data["fallback_rate_pct"] == pytest.approx(fallback_n / (fallback_n + other_n) * 100, abs=0.1)
    assert data["fallback_band"] == band


def test_human_output_prints_the_band_explicitly(db_env):
    _seed_dispatches(db_env["ldb"], "general-purpose", 45)
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 55)

    out = _run(db_env["env_dir"]).stdout
    assert "Fallback rate:" in out
    assert "ALARM-HIGH" in out
    assert "watch above 15%" in out
    assert "alarm above 20%" in out
    assert "unmeasured starting values" in out
    assert "no low alarm" in out
    assert "alarm below" not in out


# --- the counters that make the fallback rate ungameable ---------------------


def test_routing_everything_to_one_specialist_scores_zero_fallback_but_fails_the_counters(db_env):
    """The exact gaming move: 0% fallback, and every counter says so."""
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 100)

    data = _json(db_env["env_dir"])
    assert data["fallback_rate_pct"] == 0.0
    # No low alarm: the three counters below expose the move, not the band.
    assert data["fallback_band"] == "OK"
    assert data["top2_concentration_pct"] == 100.0
    assert data["agent_entropy_bits"] == 0.0
    assert data["effective_agents"] == 1.0


def test_top2_concentration_and_entropy_on_a_spread_distribution(db_env):
    ldb = db_env["ldb"]
    for agent in ("python-general-engineer", "golang-general-engineer", "hook-development-engineer", "claude"):
        _seed_dispatches(ldb, agent, 25)

    data = _json(db_env["env_dir"])
    assert data["distinct_agents"] == 4
    assert data["top2_concentration_pct"] == 50.0
    # Four agents, evenly used => exactly 2 bits, fully normalized.
    assert data["agent_entropy_bits"] == 2.0
    assert data["agent_entropy_max_bits"] == 2.0
    assert data["agent_entropy_normalized"] == 1.0
    assert data["effective_agents"] == 4.0


def test_top2_concentration_names_the_two_agents(db_env):
    ldb = db_env["ldb"]
    _seed_dispatches(ldb, "python-general-engineer", 50)
    _seed_dispatches(ldb, "general-purpose", 30)
    _seed_dispatches(ldb, "golang-general-engineer", 20)

    data = _json(db_env["env_dir"])
    assert data["top2_agents"] == ["python-general-engineer", "general-purpose"]
    assert data["top2_concentration_pct"] == 80.0
    assert data["top2_target_pct"] == 50.0
    out = _run(db_env["env_dir"]).stdout
    assert "Top-2 agent concentration: 80.0%" in out
    assert "target below 50%" in out
    assert "Agent distribution entropy:" in out


def test_shifting_fallback_traffic_onto_one_agent_lowers_entropy(db_env, tmp_path, monkeypatch):
    """ "Fallback went down" cannot be claimed when traffic merely moved."""
    ldb = db_env["ldb"]
    _seed_dispatches(ldb, "general-purpose", 40)
    _seed_dispatches(ldb, "python-general-engineer", 30)
    _seed_dispatches(ldb, "golang-general-engineer", 30)
    before = _json(db_env["env_dir"])

    # Same traffic, fallbacks re-routed wholesale to the incumbent specialist.
    with ldb.get_connection() as conn:
        conn.execute(
            "UPDATE evidence_route_decisions SET agent = ? WHERE agent = ?",
            ("python-general-engineer", "general-purpose"),
        )
        conn.commit()
    after = _json(db_env["env_dir"])

    assert after["fallback_rate_pct"] < before["fallback_rate_pct"]
    assert after["agent_entropy_bits"] < before["agent_entropy_bits"]
    assert after["top2_concentration_pct"] > before["top2_concentration_pct"]


# --- misroute and route-fit rates -------------------------------------------


def test_misroute_rate_counts_recorded_misroutes(db_env):
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 50)
    _seed_misroutes(db_env["ldb"], 5)

    data = _json(db_env["env_dir"])
    assert data["misroute_count"] == 5
    assert data["misroute_rate_pct"] == 10.0
    assert data["misroute_rate_instrumented"] is True
    assert "Misroute rate: 5/50" in _run(db_env["env_dir"]).stdout


def test_misroute_rate_with_no_rows_is_not_instrumented(db_env):
    """No hook writes misroute rows: zero rows must not read as a 0% rate."""
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 50)

    data = _json(db_env["env_dir"])
    assert data["misroute_count"] == 0
    assert data["misroute_rate_pct"] is None
    assert data["misroute_rate_instrumented"] is False
    out = _run(db_env["env_dir"]).stdout
    assert "Misroute rate: not instrumented" in out
    assert "Misroute rate: 0/50" not in out


def test_correction_rate_with_no_rows_is_not_instrumented(db_env):
    """No hook writes user-correction rows: report the gap, not 0%."""
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 5)

    data = _json(db_env["env_dir"])
    assert data["correction_rate_pct"] is None
    assert data["correction_rate_instrumented"] is False
    out = _run(db_env["env_dir"]).stdout
    assert "Correction rate: not instrumented" in out
    assert "drew correction language" not in out


def test_correction_rate_prints_when_rows_exist(db_env):
    ldb = db_env["ldb"]
    _seed_dispatches(ldb, "python-general-engineer", 5)
    ldb.record_learning(
        topic="user-correction",
        key="c-1",
        value="correction: wrong file",
        category="correction",
        source="hook:test-correction",
        confidence=0.7,
        session_id="s-corr",
    )

    data = _json(db_env["env_dir"])
    assert data["correction_rate_instrumented"] is True
    assert data["correction_rate_pct"] is not None
    assert "routed sessions drew correction language" in _run(db_env["env_dir"]).stdout


# --- route signal (scripts/route-signal-check.py) ----------------------------


def _write_events(db_dir: Path, events: list[dict]) -> None:
    (db_dir / "route-events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_route_health_reports_no_signal_without_events(db_env):
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 3)

    data = _json(db_env["env_dir"])
    assert data["route_signal"] == {"failures": 0, "scored": 0, "would_act": 0, "signal": False}
    assert "Route signal: NO-SIGNAL" in _run(db_env["env_dir"]).stdout


def test_route_health_reports_signal_from_route_events(db_env):
    """route-health runs the route-signal check, so the verdict is seen."""
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 3)
    _write_events(
        db_env["db_dir"],
        [
            {"type": "outcome", "outcome": "failure", "routing_relevant": True},
            {"type": "outcome", "outcome": "failure", "routing_relevant": False},
            {"type": "decision", "health_at_decision": 0.4, "action": "demote"},
            {"type": "decision", "health_at_decision": None, "action": "keep"},
        ],
    )

    data = _json(db_env["env_dir"])
    assert data["route_signal"] == {"failures": 1, "scored": 1, "would_act": 1, "signal": True}
    res = _run(db_env["env_dir"])
    assert res.returncode == 0  # the verdict is a line, not an exit code
    assert "Route signal: SIGNAL — 1 routing-relevant failures, 1 would-demote/would-tiebreak decisions" in res.stdout
    assert "re-propose the actuator" in res.stdout


def test_route_fit_negative_rate(db_env):
    ldb = db_env["ldb"]
    _seed_dispatches(ldb, "python-general-engineer", 20)
    _seed_basis(ldb, "python-general-engineer:quick", "route_fit:ok", 6)
    _seed_basis(ldb, "python-general-engineer:quick", "route_fit:wrong-agent", 3)
    _seed_basis(ldb, "python-general-engineer:quick", "route_fit:underspecified", 1)

    data = _json(db_env["env_dir"])
    assert data["route_fit_total"] == 10
    assert data["route_fit_negative"] == 4
    assert data["route_fit_negative_rate_pct"] == 40.0
    assert data["route_fit_counts"]["ok"] == 6
    assert "Route-fit negatives: 4/10" in _run(db_env["env_dir"]).stdout


def test_route_fit_absent_reports_no_data_and_no_divide_by_zero(db_env):
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 3)

    data = _json(db_env["env_dir"])
    assert data["route_fit_total"] == 0
    assert data["route_fit_negative_rate_pct"] is None
    assert "no route-fit verdicts recorded" in _run(db_env["env_dir"]).stdout


def test_no_dispatch_rows_degrades_gracefully(db_env):
    """Routing learnings but no evidence rows: report the gap, never crash."""
    db_env["ldb"].record_learning(
        topic="routing",
        key="python-general-engineer:quick",
        value="routing-decision: x",
        category="effectiveness",
        source="test:route-health",
    )
    res = _run(db_env["env_dir"])
    assert res.returncode == 0, res.stderr
    assert "no dispatch rows yet" in res.stdout
    assert _json(db_env["env_dir"])["dispatch_total"] == 0


def test_existing_basis_report_is_unchanged(db_env):
    """The counters are additive: the pre-existing lines still render."""
    _seed_dispatches(db_env["ldb"], "python-general-engineer", 4)
    _seed_basis(db_env["ldb"], "python-general-engineer:quick", "default_no_complaint", 3)

    out = _run(db_env["env_dir"]).stdout
    for line in ("Route Health:", "Confidence:", "Feedback loop:", "Outcome basis:", "Governed-path coverage:"):
        assert line in out
