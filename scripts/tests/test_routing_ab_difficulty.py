"""Tests for the A/B difficulty checks in scripts/routing-ab-test.py.

Covers the CEILING/FLOOR gate verdict (exit 3) and the pre-run --pilot-check
(baseline band, discriminating share, degraded control, A/A noise). Pure
functions on synthetic inputs, plus the CLI paths. No model calls.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "scripts" / "routing-ab-test.py"
HIT, MISS = "right", "wrong"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("routing_ab_difficulty", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_of(pairs: list[tuple[str, str]], bucket: str = "plain-english") -> dict:
    """Manifest-arm raw.json; each pair is the (base, chal) skill picked for expected skill 'right'."""
    records = [
        {
            "id": f"q{i:03d}",
            "bucket": bucket,
            "expected_agent": None,
            "expected_skill": HIT,
            "arms": {"base": {"route": {"skill": b}}, "chal": {"route": {"skill": c}}},
        }
        for i, (b, c) in enumerate(pairs)
    ]
    return {"arms": ["base", "chal"], "records": records}


def flags(text: str) -> list[bool]:
    return [ch == "1" for ch in text]


class TestGateBound:
    def test_both_arms_perfect_is_ceiling_not_underpowered(self, mod):
        v = mod.gate_verdict(raw_of([(HIT, HIT)] * 20), "base", "chal")
        assert (v["verdict"], v["exit_code"]) == ("CEILING", 3), "two perfect arms must read CEILING, exit 3"

    def test_fix_strategy_v1_replay_is_ceiling(self, mod):
        # fix-strategy-v1: 8/8 fixed in both arms, reported by hand as a null.
        v = mod.gate_verdict(raw_of([(HIT, HIT)] * 8), "base", "chal")
        assert v["verdict"] == "CEILING", "the 8/8 vs 8/8 run must never read as no difference"

    def test_powered_run_at_ceiling_is_not_promoted(self, mod):
        pairs = [(HIT, HIT)] * 190 + [(MISS, HIT)] * 4 + [(HIT, MISS)] * 3 + [(MISS, MISS)] * 3
        v = mod.gate_verdict(raw_of(pairs), "base", "chal")
        assert v["discordant_pairs"] == 7 and v["failing_gates"] == [], "setup: powered and passing"
        assert v["verdict"] == "CEILING", "96.5% vs 97.0% must read CEILING, not PROMOTE"

    def test_both_arms_at_zero_is_floor(self, mod):
        v = mod.gate_verdict(raw_of([(MISS, MISS)] * 20), "base", "chal")
        assert (v["verdict"], v["exit_code"]) == ("FLOOR", 3), "two arms at 0% must read FLOOR, exit 3"

    def test_reject_still_wins_at_ceiling(self, mod):
        raw = raw_of([(HIT, HIT)] * 100)
        raw["records"] += raw_of([(HIT, MISS)], bucket="paraphrase-git")["records"]
        v = mod.gate_verdict(raw, "base", "chal")
        assert v["verdict"] == "REJECT", "a new safety-bucket miss must reject even at ceiling"

    @pytest.mark.parametrize(
        ("base", "chal", "want"),
        [(95.0, 95.0, "CEILING"), (94.9, 100.0, None), (5.0, 5.0, "FLOOR"), (5.1, 0.0, None), (100.0, 0.0, None)],
    )
    def test_bound_edges(self, mod, base, chal, want):
        assert mod.non_discriminating(base, chal) == want, f"{base}/{chal} should map to {want}"

    def test_runbook_quotes_the_gate_text_verbatim(self, mod):
        runbook = (HARNESS.parents[1] / "docs" / "router-ab-runbook.md").read_text(encoding="utf-8")
        assert mod.GATES_TEXT in runbook, "docs/router-ab-runbook.md must quote GATES_TEXT verbatim"

    def test_gate_cli_exits_3_and_prints_gates_first(self, mod, tmp_path, capsys):
        (tmp_path / "raw.json").write_text(json.dumps(raw_of([(HIT, HIT)] * 10)), encoding="utf-8")
        assert mod.gate(out_dir=tmp_path) == 3, "--gate must exit 3 on a ceiling run"
        out = capsys.readouterr().out
        assert out.index("CEILING / FLOOR (exit 3)") < out.index("VERDICT: CEILING (exit 3)")


# base 50%, control 0%, A/A 50% with case 0 and case 5 swapped: 6/10 cases split.
PASSING = {"base": flags("1111100000"), "ctrl": flags("0000000000"), "aa": flags("0111110000")}


class TestPilotVerdict:
    def test_discriminating_pilot_passes_at_the_share_bar(self, mod):
        v = mod.pilot_verdict(PASSING, "base", "ctrl", "aa")
        assert v["discriminating_pct"] == 60.0, "cases 0-5 split, 6-9 agree"
        assert (v["verdict"], v["exit_code"]) == ("PASS", 0), "60% split meets the 60% bar"

    def test_easy_baseline_is_ceiling(self, mod):
        v = mod.pilot_verdict({"base": flags("1111111100"), "ctrl": flags("0000000000")}, "base", "ctrl")
        assert v["verdict"] == "CEILING", "baseline 80% is above the 70% band"

    def test_hard_baseline_is_floor(self, mod):
        v = mod.pilot_verdict({"base": flags("1100000000"), "ctrl": flags("0000000000")}, "base", "ctrl")
        assert v["verdict"] == "FLOOR", "baseline 20% is below the 30% band"

    def test_band_edges_are_inside(self, mod):
        hi = mod.pilot_verdict({"base": flags("1111111000"), "ctrl": flags("0000000000")}, "base", "ctrl")
        lo = mod.pilot_verdict({"base": flags("1110000000"), "ctrl": flags("0000000000")}, "base", "ctrl")
        assert "CEILING" not in hi["failing_checks"], "70% is inside the band"
        assert "FLOOR" not in lo["failing_checks"], "30% is inside the band"

    def test_too_few_split_cases_is_non_discriminating(self, mod):
        v = mod.pilot_verdict({"base": flags("1111100000"), "ctrl": flags("0000000000")}, "base", "ctrl")
        assert v["failing_checks"] == ["NON-DISCRIMINATING"], "5/10 split is under the 60% bar"

    def test_control_19_points_down_did_not_lose(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 19 + [True] * 41 + [False] * 40
        v = mod.pilot_verdict({"base": base, "ctrl": ctrl}, "base", "ctrl")
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 19-point gap is under the 20-point bar"

    def test_control_20_points_down_lost(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 20 + [True] * 40 + [False] * 40
        v = mod.pilot_verdict({"base": base, "ctrl": ctrl}, "base", "ctrl")
        assert "CONTROL-DID-NOT-LOSE" not in v["failing_checks"], "a 20-point gap meets the bar"

    def test_control_must_beat_twice_the_aa_noise(self, mod):
        arms = {"base": [True] * 50 + [False] * 50, "ctrl": [True] * 25 + [False] * 75}
        arms["aa"] = [True] * 65 + [False] * 35
        v = mod.pilot_verdict(arms, "base", "ctrl", "aa")
        assert (v["aa_gap_pts"], v["control_gap_pts"]) == (15.0, 25.0), "setup: noise 15, gap 25"
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 25-point gap is inside 2 x 15 noise"

    @pytest.mark.parametrize(
        ("arms", "control"),
        [({"base": [True], "ctrl": [True]}, "nope"), ({"base": [True], "ctrl": [True, False]}, "ctrl")],
    )
    def test_bad_input_raises(self, mod, arms, control):
        with pytest.raises(ValueError):
            mod.pilot_verdict(arms, "base", control)

    def test_same_arm_for_baseline_and_control_raises(self, mod):
        with pytest.raises(ValueError, match="must all differ"):
            mod.pilot_verdict(PASSING, "base", "base")


class TestPilotCli:
    def test_per_case_file_prints_checks_first_and_writes_verdict(self, mod, tmp_path, capsys):
        src = tmp_path / "pilot.json"
        src.write_text(json.dumps({"arms": {"base": [True] * 10, "ctrl": [False] * 10}}), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", per_case_path=src) == 1, "100% baseline fails"
        out = capsys.readouterr().out
        assert out.index("PRE-REGISTERED PILOT CHECKS") < out.index("VERDICT: CEILING")
        assert json.loads((tmp_path / "pilot-verdict.json").read_text())["verdict"] == "CEILING"

    def test_raw_json_input_scores_routes(self, mod, tmp_path):
        pairs = [(HIT, MISS)] * 5 + [(MISS, HIT)] * 2 + [(MISS, MISS)] * 3
        (tmp_path / "raw.json").write_text(json.dumps(raw_of(pairs)), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="chal") == 0, "50% vs 20%, 7/10 split passes"

    def test_missing_control_arm_fails(self, mod, tmp_path):
        assert mod.pilot_check(out_dir=tmp_path) == 1, "a pilot without a degraded control cannot pass"

    def test_missing_raw_json_fails(self, mod, tmp_path):
        assert mod.pilot_check(out_dir=tmp_path, control="chal") == 1, "no pilot data must not pass"
        assert not (tmp_path / "pilot-verdict.json").exists(), "no verdict file without pilot data"

    def test_unknown_arm_on_cli_fails(self, mod, tmp_path):
        (tmp_path / "raw.json").write_text(json.dumps(raw_of([(HIT, MISS)] * 4)), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="nope") == 1, "an unknown control arm is an error"

    def test_main_dispatches_pilot_check(self, mod, tmp_path, monkeypatch):
        src = tmp_path / "pilot.json"
        src.write_text(json.dumps({"arms": {"b": flags("1111100000"), "c": flags("0000000000")}}), encoding="utf-8")
        argv = ["x", "--pilot-check", "--control-arm", "c", "--per-case", str(src), "--out-dir", str(tmp_path)]
        monkeypatch.setattr("sys.argv", argv)
        assert mod.main() == 1, "5/10 split fails NON-DISCRIMINATING through the CLI"

    def test_pilot_flags_rejected_outside_pilot_mode(self, mod, monkeypatch):
        monkeypatch.setattr("sys.argv", ["routing-ab-test.py", "--gate", "--control-arm", "x"])
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 2, "--control-arm without --pilot-check is a usage error"
