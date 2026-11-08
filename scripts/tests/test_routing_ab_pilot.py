"""Tests for the pre-run --pilot-check in scripts/routing-ab-test.py.

Covers the baseline band (p1), the discriminating share over the non-control
arms only (p2), the degraded control and A/A noise (p3), input validation,
and the CLI paths. Pure functions on synthetic inputs. No model calls.
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
    spec = importlib.util.spec_from_file_location("routing_ab_pilot", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flags(text: str) -> list[bool]:
    return [ch == "1" for ch in text]


def arms(base: str, aa: str | None = None, ctrl: str = "0000000000") -> dict[str, list[bool]]:
    """base/aa/ctrl per-case flags; aa defaults to a copy of base (no split)."""
    return {"base": flags(base), "aa": flags(aa if aa is not None else base), "ctrl": flags(ctrl)}


def raw3(rows: list[tuple[str, ...]], names: tuple[str, ...] = ("base", "aa", "ctrl")) -> dict:
    """Manifest-arm raw.json; each row is the skill each arm picked for expected skill 'right'."""
    records = [
        {
            "id": f"q{i:03d}",
            "bucket": "plain-english",
            "expected_agent": None,
            "expected_skill": HIT,
            "arms": {name: {"route": {"skill": pick}} for name, pick in zip(names, row, strict=True)},
        }
        for i, row in enumerate(rows)
    ]
    return {"arms": list(names), "records": records}


# base 50%, A/A 50% splitting cases 0-2 and 5-7 (6/10), control 0%.
PASSING = arms("1111100000", "0001111100")


class TestDiscriminatingShare:
    def test_six_of_ten_split_between_baseline_and_aa_passes(self, mod):
        v = mod.pilot_verdict(PASSING, "base", "ctrl", "aa")
        assert v["discriminating_pct"] == 60.0, "cases 0-2 and 5-7 split between base and aa"
        assert (v["verdict"], v["exit_code"]) == ("PASS", 0), "60% split meets the 60% bar"

    def test_five_of_ten_split_is_non_discriminating(self, mod):
        v = mod.pilot_verdict(arms("1111100000", "0011111000"), "base", "ctrl", "aa")
        assert v["failing_checks"] == ["NON-DISCRIMINATING"], "5/10 split is under the 60% bar"

    def test_control_never_counts_toward_the_split(self, mod):
        # Regression: identical baseline and A/A with a 0% control read 60%, PASS.
        v = mod.pilot_verdict(arms("1111110000"), "base", "ctrl", "aa")
        assert v["discriminating_pct"] == 0.0, "every case is a fixed pass or fail for the real arms"
        assert v["verdict"] == "NON-DISCRIMINATING", "a control-only split must fail p2"

    def test_named_extra_arm_counts_toward_the_split(self, mod):
        data = {**arms("1111100000"), "c": flags("0001111100")}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", ("c",))
        assert (v["split_arms"], v["discriminating_pct"]) == (["base", "aa", "c"], 60.0), "extra arm splits 6"

    def test_unnamed_arm_is_rejected(self, mod):
        data = {**PASSING, "chal": flags("1111111111")}
        with pytest.raises(ValueError, match="not named"):
            mod.pilot_verdict(data, "base", "ctrl", "aa")

    def test_baseline_alone_cannot_measure_a_split(self, mod):
        data = {"base": flags("1111100000"), "ctrl": flags("0000000000")}
        with pytest.raises(ValueError, match="two non-control arms"):
            mod.pilot_verdict(data, "base", "ctrl")


class TestBandAndControl:
    def test_easy_baseline_is_ceiling(self, mod):
        v = mod.pilot_verdict(arms("1111111100"), "base", "ctrl", "aa")
        assert v["verdict"] == "CEILING", "baseline 80% is above the 70% band"

    def test_hard_baseline_is_floor(self, mod):
        v = mod.pilot_verdict(arms("1100000000"), "base", "ctrl", "aa")
        assert v["verdict"] == "FLOOR", "baseline 20% is below the 30% band"

    def test_band_edges_are_inside(self, mod):
        hi = mod.pilot_verdict(arms("1111111000"), "base", "ctrl", "aa")
        lo = mod.pilot_verdict(arms("1110000000"), "base", "ctrl", "aa")
        assert "CEILING" not in hi["failing_checks"], "70% is inside the band"
        assert "FLOOR" not in lo["failing_checks"], "30% is inside the band"

    def test_control_19_points_down_did_not_lose(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 19 + [True] * 41 + [False] * 40
        v = mod.pilot_verdict({"base": base, "aa": base, "ctrl": ctrl}, "base", "ctrl", "aa")
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 19-point gap is under the 20-point bar"

    def test_control_20_points_down_lost(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 20 + [True] * 40 + [False] * 40
        v = mod.pilot_verdict({"base": base, "aa": base, "ctrl": ctrl}, "base", "ctrl", "aa")
        assert "CONTROL-DID-NOT-LOSE" not in v["failing_checks"], "a 20-point gap meets the bar"

    def test_control_must_beat_twice_the_aa_noise(self, mod):
        data = {"base": [True] * 50 + [False] * 50, "ctrl": [True] * 25 + [False] * 75}
        data["aa"] = [True] * 65 + [False] * 35
        v = mod.pilot_verdict(data, "base", "ctrl", "aa")
        assert (v["aa_gap_pts"], v["control_gap_pts"]) == (15.0, 25.0), "setup: noise 15, gap 25"
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 25-point gap is inside 2 x 15 noise"


class TestInputValidation:
    @pytest.mark.parametrize("bad", [["true"] * 10, [1] * 10, "1111100000", None])
    def test_non_bool_per_case_values_raise(self, mod, bad):
        with pytest.raises(ValueError, match="true/false"):
            mod.pilot_verdict({**PASSING, "base": bad}, "base", "ctrl", "aa")

    @pytest.mark.parametrize(
        ("data", "control"),
        [(PASSING, "nope"), ({**PASSING, "ctrl": [True]}, "ctrl"), (["base"], "ctrl")],
    )
    def test_bad_shape_raises(self, mod, data, control):
        with pytest.raises(ValueError):
            mod.pilot_verdict(data, "base", control, "aa")

    def test_same_arm_for_baseline_and_control_raises(self, mod):
        with pytest.raises(ValueError, match="must all differ"):
            mod.pilot_verdict(PASSING, "base", "base", "aa")


class TestPilotCli:
    def test_per_case_file_prints_checks_first_and_writes_verdict(self, mod, tmp_path, capsys):
        src = tmp_path / "pilot.json"
        src.write_text(json.dumps({"arms": arms("1111111111")}), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa", per_case_path=src) == 1, "100% fails"
        out = capsys.readouterr().out
        assert out.index("PRE-REGISTERED PILOT CHECKS") < out.index("VERDICT: CEILING")
        assert json.loads((tmp_path / "pilot-verdict.json").read_text())["verdict"] == "CEILING"

    @pytest.mark.parametrize("body", ["{not json", json.dumps({"cases": {}}), json.dumps([1, 2])])
    def test_unreadable_per_case_file_prints_error(self, mod, tmp_path, capsys, body):
        src = tmp_path / "pilot.json"
        src.write_text(body, encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa", per_case_path=src) == 1
        assert "ERROR:" in capsys.readouterr().err, "bad pilot input must print an ERROR line, not a traceback"

    def test_raw_json_input_scores_routes(self, mod, tmp_path):
        rows = [(HIT, MISS, MISS)] * 3 + [(HIT, HIT, MISS)] * 2 + [(MISS, HIT, MISS)] * 3 + [(MISS, MISS, MISS)] * 2
        (tmp_path / "raw.json").write_text(json.dumps(raw3(rows)), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa") == 0, "50% base, 6/10 split, ctrl 0%"

    def test_candidate_arm_in_raw_json_fails(self, mod, tmp_path):
        rows = [(HIT, MISS, MISS, HIT)] * 6 + [(MISS, HIT, MISS, HIT)] * 4
        raw = raw3(rows, ("base", "aa", "ctrl", "chal"))
        (tmp_path / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa") == 1, "an unnamed arm is an error"

    def test_missing_control_arm_fails(self, mod, tmp_path):
        assert mod.pilot_check(out_dir=tmp_path) == 1, "a pilot without a degraded control cannot pass"

    def test_missing_raw_json_fails(self, mod, tmp_path):
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl") == 1, "no pilot data must not pass"
        assert not (tmp_path / "pilot-verdict.json").exists(), "no verdict file without pilot data"

    def test_main_dispatches_pilot_check(self, mod, tmp_path, monkeypatch):
        src = tmp_path / "pilot.json"
        src.write_text(json.dumps({"arms": {**arms("1111100000"), "c": flags("0001111100")}}), encoding="utf-8")
        argv = ["x", "--pilot-check", "--control-arm", "ctrl", "--aa-arm", "aa", "--extra-arm", "c"]
        monkeypatch.setattr("sys.argv", [*argv, "--per-case", str(src), "--out-dir", str(tmp_path)])
        assert mod.main() == 0, "the extra arm supplies the 6/10 split through the CLI"

    @pytest.mark.parametrize("flag", ["--control-arm", "--extra-arm"])
    def test_pilot_flags_rejected_outside_pilot_mode(self, mod, monkeypatch, flag):
        monkeypatch.setattr("sys.argv", ["routing-ab-test.py", "--gate", flag, "x"])
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 2, f"{flag} without --pilot-check is a usage error"
