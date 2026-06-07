"""Tests for the route value eval orchestrator (scripts/route-value-eval.py).

Two verdicts, never one gate (ADR: routing-loop-value-eval):
  - Stage 1 MECHANISM: REAL changed==0; SYNTHETIC/TIEBREAK help>0, harm==0,
    force-route held.
  - Stage 2: skip-with-reason on current data (non_null_health=0, failures=0).
  - Stage 3 VALUE: value PASS needs D>0 + CI lower bound>0 + McNemar p<0.05 +
    harm==0; value_measured=false yields exit 2, not exit 0.

Deterministic, offline. Stage 1 runs on a tiny fixture corpus + temp DB; the
live DB and live route-events.jsonl are never touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_eval():
    spec = importlib.util.spec_from_file_location("route_value_eval", _REPO_ROOT / "scripts" / "route-value-eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tiny_corpora(tmp_path: Path) -> tuple[Path, Path]:
    """Two tiny corpus files: force-route + normal cases (mirrors health_replay)."""
    ab = {
        "version": "test",
        "test_cases": [
            {"request": "send commits", "expected_agent": None, "expected_skill": "pr-workflow", "bucket": "git"},
            {
                "request": "write a function",
                "expected_agent": "python-general-engineer",
                "expected_skill": "test-driven-development",
                "bucket": "code",
            },
        ],
    }
    bm = {
        "version": "test",
        "test_cases": [
            {"request": "scan for vulns", "expected_agent": None, "expected_skill": "security-review", "bucket": "sec"},
            {
                "request": "explore the repo",
                "expected_agent": "explore",
                "expected_skill": "codebase-overview",
                "bucket": "explore",
            },
            {"request": "no skill case", "expected_agent": None, "expected_skill": None, "bucket": "none"},
        ],
    }
    ab_path = tmp_path / "ab.json"
    bm_path = tmp_path / "bm.json"
    ab_path.write_text(json.dumps(ab), encoding="utf-8")
    bm_path.write_text(json.dumps(bm), encoding="utf-8")
    return ab_path, bm_path


_HEALTHY = {
    "direct:pr-workflow": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
    "python-general-engineer:test-driven-development": {
        "confidence": 0.7,
        "n": 5,
        "success": 5,
        "failure": 0,
        "last_seen": "x",
    },
    "direct:security-review": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
    "explore:codebase-overview": {"confidence": 0.7, "n": 5, "success": 5, "failure": 0, "last_seen": "x"},
}


# --------------------------------------------------------------------------- #
# Stage 1 — MECHANISM
# --------------------------------------------------------------------------- #
def test_stage1_real_changed_zero(tiny_corpora, tmp_path):
    ev = _load_eval()
    ab, bm = tiny_corpora
    res = ev.run_stage1(ab_path=ab, benchmark_path=bm, db_dir=tmp_path / "db", real_weights=_HEALTHY)
    assert res["real"]["changed"] == 0
    assert res["mechanism"]["clauses"]["real_changed_zero"] is True


def test_stage1_synthetic_help_harm_force(tiny_corpora, tmp_path):
    ev = _load_eval()
    ab, bm = tiny_corpora
    res = ev.run_stage1(ab_path=ab, benchmark_path=bm, db_dir=tmp_path / "db", real_weights=_HEALTHY)
    syn = res["synthetic"]
    assert syn["help"] > 0
    assert syn["harm"] == 0
    assert syn["force_route_held"] == 2  # pr-workflow + security-review held
    cl = res["mechanism"]["clauses"]
    assert cl["synthetic_help_positive"] and cl["synthetic_harm_zero"] and cl["synthetic_force_route_held"]


def test_stage1_tiebreak_help_harm_force(tiny_corpora, tmp_path):
    ev = _load_eval()
    ab, bm = tiny_corpora
    res = ev.run_stage1(ab_path=ab, benchmark_path=bm, db_dir=tmp_path / "db", real_weights=_HEALTHY)
    tb = res["tiebreak"]
    assert tb["help"] > 0
    assert tb["harm"] == 0
    assert tb["force_route_held"] == 2
    assert res["mechanism"]["mechanism_pass"] is True


# --------------------------------------------------------------------------- #
# Stage 2 — recorded-events availability (skip with reason today)
# --------------------------------------------------------------------------- #
def test_stage2_skip_with_reason_on_empty(tmp_path):
    ev = _load_eval()
    empty = tmp_path / "route-events.jsonl"  # does not exist
    res = ev.run_stage2(events_path=empty)
    assert res["non_null_health"] == 0
    assert res["recorded_failures"] == 0
    assert res["faithful_replay_ran"] is False
    assert res["value_measured"] is False
    assert "non_null_health=0" in res["skip_reason"]


def test_stage2_counts_and_censors_neutral(tmp_path):
    ev = _load_eval()
    p = tmp_path / "route-events.jsonl"
    lines = [
        {"type": "decision", "health_at_decision": None, "action": "keep"},
        # A demote decision with historical failure_count=4. Under finding [51]
        # this must NOT count toward recorded_failures: it is a snapshot of the
        # weight row's history, not this dispatch's outcome.
        {"type": "decision", "health_at_decision": 0.2, "action": "demote", "n": 6, "failure": 4},
        {"type": "outcome", "outcome": "neutral"},
        {"type": "outcome", "outcome": "failure"},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    res = ev.run_stage2(events_path=p)
    assert res["decisions"] == 2
    assert res["outcomes"] == 2
    assert res["non_null_health"] == 1
    assert res["neutral_censored"] == 1
    # Only the one failure OUTCOME counts; the demote decision does not (finding [51]).
    assert res["recorded_failures"] == 1
    # Still below the gate (non_null_health < 20).
    assert res["faithful_replay_ran"] is False


def test_stage2_recorded_failures_counts_only_routing_relevant_outcomes(tmp_path):
    """Finding [51]: recorded_failures = routing-relevant outcome=="failure" only.

    Legacy failure events (no routing_relevant field) count; explicit
    routing_relevant: false events do not; decision-event failure_count never
    counts regardless of action.
    """
    ev = _load_eval()
    p = tmp_path / "route-events.jsonl"
    lines = [
        # Historical failure_count on decisions: must contribute 0 failures.
        {"type": "decision", "health_at_decision": 0.1, "action": "demote", "n": 9, "failure": 7},
        {"type": "decision", "health_at_decision": 0.4, "action": "keep", "n": 9, "failure": 3},
        # Legacy failure outcome (no field) -> counts.
        {"type": "outcome", "outcome": "failure"},
        # Explicitly routing-relevant failure -> counts.
        {"type": "outcome", "outcome": "failure", "routing_relevant": True},
        # Explicitly NOT routing-relevant failure -> excluded.
        {"type": "outcome", "outcome": "failure", "routing_relevant": False},
        # Non-failure outcomes never count as failures.
        {"type": "outcome", "outcome": "success", "routing_relevant": True},
        {"type": "outcome", "outcome": "neutral"},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    res = ev.run_stage2(events_path=p)
    assert res["recorded_failures"] == 2  # two relevant failure outcomes only
    assert res["neutral_censored"] == 1


# --------------------------------------------------------------------------- #
# Stage 3 — VALUE stats
# --------------------------------------------------------------------------- #
def _per_case(a_correct, b_correct):
    return [{"a_correct": a, "b_correct": b} for a, b in zip(a_correct, b_correct, strict=True)]


def test_stage3_value_pass_requires_all_gates():
    ev = _load_eval()
    # Strong positive signal: B fixes 12 of 14, never harms. D>0, CI>0, p<0.05.
    a = [False] * 14
    b = [True] * 12 + [False] * 2
    stats = ev.compute_value_stats(_per_case(a, b))
    assert stats["D"] > 0
    assert stats["D_ci_low"] > 0
    assert stats["mcnemar_p"] < 0.05
    assert stats["harm"] == 0
    assert stats["value_pass"] is True


def test_stage3_harm_blocks_value_pass():
    ev = _load_eval()
    # B helps a lot but harms one correct route => hard gate fails.
    a = [False] * 13 + [True]
    b = [True] * 12 + [False, False]  # last: A right, B wrong = harm
    stats = ev.compute_value_stats(_per_case(a, b))
    assert stats["harm"] == 1
    assert stats["value_pass"] is False


def test_stage3_noop_does_not_pass():
    ev = _load_eval()
    # D == 0 (B no better than A) must not pass.
    a = [True, False, True, False]
    b = [True, False, True, False]
    stats = ev.compute_value_stats(_per_case(a, b))
    assert stats["D"] == 0
    assert stats["value_pass"] is False


def test_stage3_unmeasured_when_no_per_case():
    ev = _load_eval()
    s3 = ev.run_stage3(scoreboard_per_case=None, stage2_can_measure=False)
    assert s3["value_measured"] is False
    assert s3["value_verdict"] == "unmeasured"


def test_stage3_unmeasured_when_telemetry_absent_even_with_data():
    ev = _load_eval()
    a = [False] * 14
    b = [True] * 12 + [False] * 2
    s3 = ev.run_stage3(scoreboard_per_case=_per_case(a, b), stage2_can_measure=False)
    # Stats computed, but live telemetry preconditions unmet => unmeasured.
    assert s3["value_measured"] is False
    assert s3["value_verdict"] == "unmeasured"


# --------------------------------------------------------------------------- #
# Alternate builder — mixes a plausibly-wrong route so harm is catchable
# --------------------------------------------------------------------------- #
def test_alternate_builder_includes_wrong_route(tiny_corpora):
    ev = _load_eval()
    ab, bm = tiny_corpora
    rr = importlib.util.spec_from_file_location("route_replay", _REPO_ROOT / "scripts" / "route-replay.py")
    mod = importlib.util.module_from_spec(rr)
    rr.loader.exec_module(mod)
    cases = mod.load_corpus(ab) + mod.load_corpus(bm)
    alts = ev.build_alternates(cases)
    # Each gold-bearing case gets a non-empty alternate pool, and at least one
    # case's pool contains a route that is NOT its own gold (a wrong route).
    assert any(len(v) > 0 for v in alts.values())
    for i, case in enumerate(cases):
        gold = ev._gold_key(case)
        if gold is None:
            continue
        assert gold not in alts.get(i, []), "gold must not be its own alternate"


# --------------------------------------------------------------------------- #
# Stage 3 — live arm computation + judge blinding
# --------------------------------------------------------------------------- #
def test_compute_health_arms_identifies_k_affected():
    ev = _load_eval()
    cases = [
        {"request": "r0", "expected_agent": "python-general-engineer", "expected_skill": "tdd", "bucket": "code"},
        {"request": "r1", "expected_agent": "explore", "expected_skill": "overview", "bucket": "explore"},
    ]
    # Case 0: low-confidence pick on a wrong route + an evidenced healthy gold
    # alternate => tie-break moves it (B != A). Case 1: confident, no alternate move.
    weights = {
        "wrong:route": {"confidence": 0.6, "n": 6, "success": 4, "failure": 0},
        "python-general-engineer:tdd": {"confidence": 0.9, "n": 8, "success": 8, "failure": 0},
    }
    picks = {
        0: {"key": "wrong:route", "confidence": 0.1},  # low conf => tie-break candidate
        1: {"key": "explore:overview", "confidence": 0.9},
    }
    alternates = {0: ["python-general-engineer:tdd"], 1: []}
    arms = ev.compute_health_arms(picks, cases, weights, set(), alternates=alternates)
    assert arms["k_health_affected"] == 1
    affected = next(c for c in arms["per_case"] if c["case_index"] == 0)
    assert affected["a_pick"] == "wrong:route"
    assert affected["b_pick"] == "python-general-engineer:tdd"
    assert affected["action"] == "tiebreak"


def test_judge_rows_strip_forbidden_fields_and_score_only_k():
    ev = _load_eval()
    cases = [
        {"request": "r0", "expected_agent": "python-general-engineer", "expected_skill": "tdd", "bucket": "code"},
        {"request": "r1", "expected_agent": "explore", "expected_skill": "overview", "bucket": "explore"},
    ]
    weights = {
        "wrong:route": {"confidence": 0.6, "n": 6, "success": 4, "failure": 0},
        "python-general-engineer:tdd": {"confidence": 0.9, "n": 8, "success": 8, "failure": 0},
    }
    picks = {0: {"key": "wrong:route", "confidence": 0.1}, 1: {"key": "explore:overview", "confidence": 0.9}}
    alternates = {0: ["python-general-engineer:tdd"], 1: []}
    arms = ev.compute_health_arms(picks, cases, weights, set(), alternates=alternates)
    rows, uid_map = ev.build_judge_rows(arms, cases)
    # Only the 1 health-affected case => 2 rows (Arm A + Arm B), arm-stripped.
    assert len(rows) == 2
    assert len(uid_map) == 2
    for row in rows:
        assert ev._JUDGE_FORBIDDEN_FIELDS.isdisjoint(row.keys())
        assert set(row.keys()) == {"uid", "query", "predicted_agent", "predicted_skill"}
    # The private map records the arm (judge never sees it).
    assert {m["arm"] for m in uid_map.values()} == {"A", "B"}


# --------------------------------------------------------------------------- #
# Orchestrator — exit-code contract
#
# orchestrate() calls run_stage1(), which (unstubbed) shells out to the live DB
# via `learning-db.py route-weights --json`. Every orchestrate test stubs
# run_stage1 so no test reads or spawns against the live learning dir (finding
# [19]). _stub_stage1 lets a test force the mechanism verdict pass/fail.
# --------------------------------------------------------------------------- #
def _stub_stage1(mechanism_pass: bool = True) -> dict:
    """A minimal Stage-1 result with a controllable mechanism verdict.

    Mirrors the shape orchestrate() reads: real/synthetic/tiebreak arm blocks and
    a `mechanism` block. No DB, no subprocess.
    """
    arm = {"evaluated": 0, "changed": 0, "help": 0, "harm": 0, "unchanged": 0, "force_route_held": 0}
    clauses = {"real_changed_zero": mechanism_pass}
    return {
        "real": dict(arm),
        "synthetic": dict(arm),
        "tiebreak": dict(arm),
        "force_case_count": 0,
        "mechanism": {
            "clauses": clauses,
            "mechanism_pass": mechanism_pass,
            "failing_clauses": [] if mechanism_pass else ["real_changed_zero"],
        },
    }


def _patch_stage1(monkeypatch, ev, *, mechanism_pass: bool) -> None:
    """Replace run_stage1 with a DB-free stub so no test touches the live DB."""
    result = _stub_stage1(mechanism_pass=mechanism_pass)

    def _fake_run_stage1(*_args, **_kwargs):
        return result

    monkeypatch.setattr(ev, "run_stage1", _fake_run_stage1)


def test_value_unmeasured_yields_exit_2_not_0(tmp_path, monkeypatch):
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=True)
    empty = tmp_path / "route-events.jsonl"
    res = ev.orchestrate(events_path=empty, stage3_per_case=None)
    assert res["mechanism_verdict"] == "pass"
    assert res["value_measured"] is False
    assert res["exit_code"] == 2  # NOT 0


def test_exit_0_only_when_value_measured_and_pass(tmp_path, monkeypatch):
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=True)
    # Simulate live telemetry that clears the Stage-2 gate (>=20 non-null health
    # AND >0 routing-relevant failure outcomes) AND a strongly-positive A/B set.
    p = tmp_path / "route-events.jsonl"
    decs = [{"type": "decision", "health_at_decision": 0.2, "action": "keep", "n": 6} for _ in range(25)]
    fails = [{"type": "outcome", "outcome": "failure"} for _ in range(3)]
    p.write_text("\n".join(json.dumps(x) for x in decs + fails), encoding="utf-8")
    a = [False] * 14
    b = [True] * 12 + [False] * 2
    res = ev.orchestrate(events_path=p, stage3_per_case=_per_case(a, b))
    assert res["value_measured"] is True
    assert res["value_verdict"] == "pass"
    assert res["exit_code"] == 0


def test_value_fail_when_measured_yields_exit_1(tmp_path, monkeypatch):
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=True)
    p = tmp_path / "route-events.jsonl"
    decs = [{"type": "decision", "health_at_decision": 0.2, "action": "keep", "n": 6} for _ in range(25)]
    fails = [{"type": "outcome", "outcome": "failure"} for _ in range(3)]
    p.write_text("\n".join(json.dumps(x) for x in decs + fails), encoding="utf-8")
    # Harm present => value FAIL when measured.
    a = [False] * 13 + [True]
    b = [True] * 12 + [False, False]
    res = ev.orchestrate(events_path=p, stage3_per_case=_per_case(a, b))
    assert res["value_measured"] is True
    assert res["value_verdict"] == "fail"
    assert res["exit_code"] == 1


def test_mechanism_fail_yields_exit_1(tmp_path, monkeypatch):
    """Finding [20]: the mechanism-fail exit_code=1 path had zero coverage.

    Force mechanism_pass=False via a stubbed Stage 1 and assert orchestrate()
    reports mechanism_verdict==fail with exit_code==1 (the same exit code as a
    value fail, which is why finding [81] added a distinguishing stderr line).
    """
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=False)
    empty = tmp_path / "route-events.jsonl"
    res = ev.orchestrate(events_path=empty, stage3_per_case=None)
    assert res["mechanism_verdict"] == "fail"
    assert res["exit_code"] == 1
    assert res["stage1"]["mechanism"]["failing_clauses"] == ["real_changed_zero"]


def test_main_value_fail_prints_value_fail_diagnostic(tmp_path, monkeypatch, capsys):
    """Finding [81]: a value fail must print a VALUE FAIL stderr line distinct
    from the MECHANISM FAIL line, since both exit 1."""
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=True)
    p = tmp_path / "route-events.jsonl"
    decs = [{"type": "decision", "health_at_decision": 0.2, "action": "keep", "n": 6} for _ in range(25)]
    fails = [{"type": "outcome", "outcome": "failure"} for _ in range(3)]
    p.write_text("\n".join(json.dumps(x) for x in decs + fails), encoding="utf-8")
    stub = tmp_path / "stub.json"
    a = [False] * 13 + [True]
    b = [True] * 12 + [False, False]
    stub.write_text(json.dumps({"per_case": _per_case(a, b)}), encoding="utf-8")
    code = ev.main(["--events", str(p), "--out-dir", str(tmp_path / "out"), "--stage3-stub", str(stub)])
    captured = capsys.readouterr()
    assert code == 1
    assert "VALUE FAIL:" in captured.err
    assert "MECHANISM FAIL:" not in captured.err


def test_main_mechanism_fail_prints_mechanism_diagnostic(tmp_path, monkeypatch, capsys):
    """Finding [81]/[20]: a mechanism fail prints MECHANISM FAIL, not VALUE FAIL."""
    ev = _load_eval()
    _patch_stage1(monkeypatch, ev, mechanism_pass=False)
    empty = tmp_path / "route-events.jsonl"
    code = ev.main(["--events", str(empty), "--out-dir", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == 1
    assert "MECHANISM FAIL:" in captured.err
    assert "VALUE FAIL:" not in captured.err
