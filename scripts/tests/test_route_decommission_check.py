"""Tests for the routing-loop decommission check (scripts/route-decommission-check.py).

ADR routing-loop-value-eval, decommission trigger. The check answers one
question: should the outcome-routing shadow loop be removed today?

Contract under test:
  - Clock start = Stage-0 wiring-fix commit (d943ba74, 2026-06-06).
  - DELETE iff (elapsed >= 90 days OR post-fix decisions >= 3000) AND
    real_demote + real_tiebreak + shadow_demote + shadow_tiebreak == 0,
    AND the clock is valid.
  - Clock valid iff post-fix non-null health_at_decision rate >= 95% AND
    outcome unknown_rate <= 5%.
  - Verdicts: KEEP (interventions > 0), DELETE, ACCRUING (no threshold reached),
    CLOCK-INVALID. Exit codes: 0 KEEP/ACCRUING, 3 DELETE, 4 CLOCK-INVALID.

Deterministic, offline. Synthetic event files only; the live route-events.jsonl
is never read (every test passes an explicit tmp path).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "route_decommission_check", _REPO_ROOT / "scripts" / "route-decommission-check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, events: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return path


def _decision(ts: float, **kw) -> dict:
    # gate_inputs_present defaults True for a numeric-health decision (state a);
    # state (b)/(c) tests pass it explicitly. A null-health default still marks
    # the marker as carrying the gate input unless overridden.
    e = {
        "type": "decision",
        "ts": ts,
        "session": kw.pop("session", "s"),
        "agent": kw.pop("agent", "python-general-engineer"),
        "skill": kw.pop("skill", "test-driven-development"),
        "health_at_decision": kw.pop("health", 0.7),
        "n": kw.pop("n", 5),
        "failure": kw.pop("failure", 0),
        "action": kw.pop("action", "keep"),
        "alternates": kw.pop("alternates", None),
        "gate_inputs_present": kw.pop("gate_inputs_present", True),
    }
    e.update(kw)
    return e


# Clock start is the Stage-0 commit; events at FIX+1s are post-fix.
def _mod_consts(mod):
    return mod.STAGE0_FIX_EPOCH, mod.DELETE_DAYS, mod.DELETE_DECISIONS


# --------------------------------------------------------------------------- #
# Named constants tie the clock to the commit (no silent drift).
# --------------------------------------------------------------------------- #
def test_clock_start_is_stage0_commit():
    mod = _load()
    assert mod.STAGE0_FIX_EPOCH == 1780780867  # d943ba74 2026-06-06 21:21:07 UTC
    assert mod.STAGE0_FIX_COMMIT == "d943ba74"
    assert mod.DELETE_DAYS == 90
    assert mod.DELETE_DECISIONS == 3000
    assert mod.MIN_INSTRUMENTED_RATE == 0.95
    assert mod.MAX_UNKNOWN_RATE == 0.05


# --------------------------------------------------------------------------- #
# Post-fix filtering: pre-fix events are ignored entirely.
# --------------------------------------------------------------------------- #
def test_pre_fix_events_excluded(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    p = _write(
        tmp_path / "e.jsonl",
        [_decision(fix - 100), _decision(fix - 1), _decision(fix + 1), _decision(fix + 2)],
    )
    stats = mod.count_post_fix(p)
    assert stats["post_fix_decisions"] == 2


# --------------------------------------------------------------------------- #
# Real interventions counted from the recorded action field.
# --------------------------------------------------------------------------- #
def test_real_interventions_counted_from_action(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    p = _write(
        tmp_path / "e.jsonl",
        [
            _decision(fix + 1, action="demote"),
            _decision(fix + 2, action="tiebreak"),
            _decision(fix + 3, action="keep"),
        ],
    )
    stats = mod.count_post_fix(p)
    assert stats["real_demote"] == 1
    assert stats["real_tiebreak"] == 1
    assert stats["interventions"] == 2


# --------------------------------------------------------------------------- #
# Shadow counted by replaying health_adjust on the RECORDED gate inputs.
# Floor met on the picked pair + a recorded alternate that wins => shadow demote.
# --------------------------------------------------------------------------- #
def test_shadow_demote_reconstructed_from_recorded_fields(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # Picked pair in the demote floor (conf<0.30, fail>=3, n>=5). One recorded
    # alternate. Recorded action is "keep" (router did not fire), but the shadow
    # replay fires demote toward the healthier alternate.
    dec = _decision(
        fix + 1,
        action="keep",
        health=0.20,
        n=6,
        failure=4,
        alternates=[{"key": "alt:route", "confidence": 0.8, "n": 6, "success": 6, "failure": 0}],
    )
    p = _write(tmp_path / "e.jsonl", [dec])
    stats = mod.count_post_fix(p)
    assert stats["real_demote"] == 0
    assert stats["shadow_demote"] == 1
    assert stats["interventions"] == 1  # shadow counts as an intervention


def test_shadow_zero_when_no_alternate_weights(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # Floor met on the pick, but the recorded alternates are bare keys with no
    # weight rows => health_adjust cannot prefer them => no shadow fire. Honest 0.
    dec = _decision(fix + 1, action="keep", health=0.20, n=6, failure=4, alternates=["alt:route"])
    p = _write(tmp_path / "e.jsonl", [dec])
    stats = mod.count_post_fix(p)
    assert stats["shadow_demote"] == 0
    assert stats["interventions"] == 0


# --------------------------------------------------------------------------- #
# Clock validity gate.
# --------------------------------------------------------------------------- #
def test_clock_valid_when_health_rate_and_unknown_rate_ok(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # 20 decisions, all non-null health (100% >= 95%); each joins a same-session
    # outcome (unknown_rate 0). Clock valid.
    events: list[dict] = []
    for i in range(20):
        events.append(_decision(fix + i + 1, session=f"s{i}", health=0.7))
        events.append({"type": "outcome", "ts": fix + i + 1.5, "session": f"s{i}", "outcome": "success"})
    p = _write(tmp_path / "e.jsonl", events)
    stats = mod.count_post_fix(p)
    valid, _reason = mod.clock_valid(stats)
    assert valid is True


def test_clock_invalid_when_instrumented_rate_below_95(tmp_path):
    # Contract change (soundness fix): validity counts INSTRUMENTED decisions
    # (state a numeric + state b no-row), not non-null health. Only state (c)
    # (no gate input on the marker) counts against the 95% rate. 9 state-(c)
    # legacy decisions + 1 state-(a) => 10% instrumented => clock invalid.
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    decs = [_decision(fix + i + 1, session=f"s{i}", health=None, gate_inputs_present=False) for i in range(9)]
    decs.append(_decision(fix + 50, session="s9", health=0.7))
    p = _write(tmp_path / "e.jsonl", decs)
    stats = mod.count_post_fix(p)
    valid, reason = mod.clock_valid(stats)
    assert valid is False
    assert "instrumented" in reason.lower()
    assert "0.1" in reason or "10" in reason  # the failing number is reported


def test_state_b_majority_is_valid_clock(tmp_path):
    # CORE FIX: most live picks are state (b) — pick has no weight row, recorded
    # as null health BUT gate_inputs_present True. These are instrumented, valid,
    # expected data. The clock must be VALID when state (b) dominates, else the
    # decommission clock stays unreachable forever (the soundness gap).
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    events: list[dict] = []
    for i in range(20):
        events.append(_decision(fix + i + 1, session=f"s{i}", health=None, gate_inputs_present=True))
        events.append({"type": "outcome", "ts": fix + i + 1.5, "session": f"s{i}", "outcome": "success"})
    p = _write(tmp_path / "e.jsonl", events)
    stats = mod.count_post_fix(p)
    assert stats["state_b_norow"] == 20
    assert stats["state_a_numeric"] == 0
    assert stats["state_c_legacy"] == 0
    assert stats["instrumented_rate"] == 1.0
    valid, _reason = mod.clock_valid(stats)
    assert valid is True


def test_state_c_majority_is_clock_invalid(tmp_path):
    # State (c) majority (legacy / no gate input on the marker) => instrumented
    # rate below 95% => CLOCK-INVALID. Distinguishes missing instrumentation
    # (state c) from the valid no-row signal (state b).
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    decs = [_decision(fix + i + 1, session=f"s{i}", health=None, gate_inputs_present=False) for i in range(19)]
    decs.append(_decision(fix + 50, session="s19", health=None, gate_inputs_present=True))
    p = _write(tmp_path / "e.jsonl", decs)
    stats = mod.count_post_fix(p)
    assert stats["state_c_legacy"] == 19
    assert stats["state_b_norow"] == 1
    valid, reason = mod.clock_valid(stats)
    assert valid is False
    assert "instrumented" in reason.lower()


def test_three_state_breakdown_in_stats(tmp_path):
    # The stats expose the three-state counts so the CLOCK-INVALID message and
    # the live report can print the breakdown.
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    decs = [
        _decision(fix + 1, session="a", health=0.7),  # state a
        _decision(fix + 2, session="b", health=None, gate_inputs_present=True),  # state b
        _decision(fix + 3, session="c", health=None, gate_inputs_present=False),  # state c
    ]
    p = _write(tmp_path / "e.jsonl", decs)
    stats = mod.count_post_fix(p)
    assert stats["state_a_numeric"] == 1
    assert stats["state_b_norow"] == 1
    assert stats["state_c_legacy"] == 1
    # instrumented = a + b = 2 of 3 (rate rounded to 4 dp).
    assert stats["instrumented_rate"] == 0.6667


# --------------------------------------------------------------------------- #
# Verdict + exit-code contract.
# --------------------------------------------------------------------------- #
def test_keep_when_interventions_present(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # One real demote => KEEP regardless of clock validity (positive signal wins).
    decs = [_decision(fix + i + 1, session=f"s{i}", health=None) for i in range(5)]
    decs.append(_decision(fix + 50, session="x", action="demote", health=0.2, n=6, failure=4))
    p = _write(tmp_path / "e.jsonl", decs)
    res = mod.decide(events_path=p, now=fix + 100)
    assert res["verdict"] == "KEEP"
    assert res["exit_code"] == 0
    assert res["interventions"] == 1


def _valid_clock_events(fix: float, n: int) -> list[dict]:
    """n decisions, each non-null health + a same-session joining outcome.

    Yields a valid clock: 100% health rate, 0% unknown rate.
    """
    events: list[dict] = []
    for i in range(n):
        events.append(_decision(fix + i + 1, session=f"s{i}", health=0.7))
        events.append({"type": "outcome", "ts": fix + i + 1.5, "session": f"s{i}", "outcome": "success"})
    return events


def test_delete_when_time_threshold_met_and_zero_interventions(tmp_path):
    mod = _load()
    fix, days, _ = _mod_consts(mod)
    # 20 non-null health decisions, valid clock, 0 interventions, 91 days elapsed.
    p = _write(tmp_path / "e.jsonl", _valid_clock_events(fix, 20))
    now = fix + (days + 1) * 86400
    res = mod.decide(events_path=p, now=now)
    assert res["verdict"] == "DELETE"
    assert res["exit_code"] == 3


def test_delete_when_count_threshold_met(tmp_path):
    mod = _load()
    fix, _, count = _mod_consts(mod)
    p = _write(tmp_path / "e.jsonl", _valid_clock_events(fix, count))
    res = mod.decide(events_path=p, now=fix + 86400)  # 1 day elapsed; count carries it
    assert res["verdict"] == "DELETE"
    assert res["exit_code"] == 3


def test_accruing_when_neither_threshold_reached(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # Valid clock, 0 interventions, only 5 days + 20 decisions => below both gates.
    p = _write(tmp_path / "e.jsonl", _valid_clock_events(fix, 20))
    now = fix + 5 * 86400
    res = mod.decide(events_path=p, now=now)
    assert res["verdict"] == "ACCRUING"
    assert res["exit_code"] == 0
    # Exact remaining reported.
    assert res["remaining_days"] == 85
    assert res["remaining_decisions"] == 2980


def test_clock_invalid_blocks_delete(tmp_path):
    mod = _load()
    fix, days, _ = _mod_consts(mod)
    # Time threshold met AND zero interventions, but instrumented rate is 10%
    # (9 state-c legacy + 1 state-a) => the zero cannot be trusted =>
    # CLOCK-INVALID, not DELETE.
    decs = [_decision(fix + i + 1, session=f"s{i}", health=None, gate_inputs_present=False) for i in range(9)]
    decs.append(_decision(fix + 50, session="s9", health=0.7))
    p = _write(tmp_path / "e.jsonl", decs)
    now = fix + (days + 1) * 86400
    res = mod.decide(events_path=p, now=now)
    assert res["verdict"] == "CLOCK-INVALID"
    assert res["exit_code"] == 4


def test_unknown_rate_above_5_percent_invalidates_clock(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    # 20 non-null health decisions (health rate fine), but only 1 joinable
    # outcome out of 20 decisions => unknown_rate 95% > 5% => CLOCK-INVALID.
    decs = [_decision(fix + i + 1, session=f"s{i}", health=0.7) for i in range(20)]
    decs.append({"type": "outcome", "ts": fix + 100, "session": "s0", "outcome": "success"})
    # Force unknown_rate high by giving most decisions no matching outcome.
    p = _write(tmp_path / "e.jsonl", decs)
    stats = mod.count_post_fix(p)
    # 19 of 20 decisions unjoinable => 0.95 unknown rate.
    assert stats["unknown_rate"] > mod.MAX_UNKNOWN_RATE
    valid, reason = mod.clock_valid(stats)
    assert valid is False
    assert "unknown" in reason.lower()


# --------------------------------------------------------------------------- #
# Live files are never touched: default path is read-only; tests use temp paths.
# --------------------------------------------------------------------------- #
def test_missing_events_file_is_clock_invalid(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    missing = tmp_path / "nope.jsonl"
    res = mod.decide(events_path=missing, now=fix + 86400)
    # No post-fix data => health rate undefined => clock invalid (cannot trust 0).
    assert res["verdict"] == "CLOCK-INVALID"
    assert res["exit_code"] == 4


# --------------------------------------------------------------------------- #
# JSON output shape (machine consumers).
# --------------------------------------------------------------------------- #
def test_decide_emits_machine_fields(tmp_path):
    mod = _load()
    fix, _, _ = _mod_consts(mod)
    decs = [_decision(fix + i + 1, session=f"s{i}", health=0.7) for i in range(20)]
    p = _write(tmp_path / "e.jsonl", decs)
    res = mod.decide(events_path=p, now=fix + 5 * 86400)
    for field in (
        "verdict",
        "exit_code",
        "interventions",
        "real_demote",
        "real_tiebreak",
        "shadow_demote",
        "shadow_tiebreak",
        "post_fix_decisions",
        "elapsed_days",
        "remaining_days",
        "remaining_decisions",
        "clock_valid",
        "instrumented_rate",
        "state_a_numeric",
        "state_b_norow",
        "state_c_legacy",
        "unknown_rate",
    ):
        assert field in res, f"missing field {field}"
