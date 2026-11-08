"""Tests for the pre-run --pilot-check in scripts/routing-ab-test.py.

Covers the baseline band (p1), per-case discrimination with A/A flips as
noise and guard cases outside the analysis set (p2), the degraded control and
A/A noise (p3), input validation, and the CLI paths. Pure functions on synthetic inputs. No model calls.
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


# Stable base 50% (A/A identical), control 0%, a stronger reference arm passing every case:
# the control splits cases 0-4, the reference splits cases 5-9, so every case discriminates.
PASSING = {**arms("1111100000"), "ref": flags("1111111111")}


class TestDiscriminating:
    def test_every_case_split_by_control_or_reference_passes(self, mod):
        v = mod.pilot_verdict(PASSING, "base", "ctrl", "aa", ("ref",))
        assert (v["discriminating_cases"], v["discriminating_pct"]) == (10, 100.0), "all 10 cases split"
        assert (v["verdict"], v["exit_code"]) == ("PASS", 0), "a stable, fully discriminating pilot passes"

    def test_aa_flips_are_noise_not_discrimination(self, mod):
        # Regression: base 1111100000 vs A/A 0001111100 read 60% discriminating and PASSED on noise.
        v = mod.pilot_verdict(arms("1111100000", "0001111100"), "base", "ctrl", "aa")
        assert v["noise_cases"] == ["0", "1", "2", "5", "6", "7"], "baseline/A/A flips are noise"
        assert "NON-DISCRIMINATING" in v["failing_checks"], "a noisy pilot must fail p2"

    def test_stable_baseline_with_control_only_lists_floor_cases(self, mod):
        v = mod.pilot_verdict(arms("1111110000"), "base", "ctrl", "aa")
        assert v["discriminating_cases"] == 6, "the control splits every case the stable baseline passes"
        assert v["floor_cases"] == ["6", "7", "8", "9"], "cases every arm fails are floor"
        assert v["verdict"] == "NON-DISCRIMINATING", "floor cases fail p2 unless guarded"

    def test_guarded_floor_cases_leave_the_analysis_set(self, mod):
        v = mod.pilot_verdict(arms("1111110000"), "base", "ctrl", "aa", guards=("6", "7", "8", "9"))
        assert (v["analysis_cases"], v["guard_cases"]) == (6, ["6", "7", "8", "9"]), "guards are reported"
        assert v["discriminating_cases"] == 6, "every case left in the analysis set discriminates"
        assert v["accuracy_pct"]["base"] == 100.0, "p1 scores the analysis set, not the guards"
        assert v["verdict"] == "CEILING", "guarding every baseline failure leaves a ceiling analysis set"

    def test_guarded_floors_cannot_pad_p1_into_the_band(self, mod):
        # Regression: base/A/A pass 10 of 20, control fails all 20, the 10 failures are guarded.
        # p1 read 50% over all 20 cases and PASSED with a 100% baseline on the analysis set.
        half = [True] * 10 + [False] * 10
        data = {"base": half, "aa": list(half), "ctrl": [False] * 20}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", guards=tuple(str(i) for i in range(10, 20)))
        assert v["accuracy_all_cases_pct"]["base"] == 50.0, "setup: 50% over every case"
        assert (v["accuracy_pct"]["base"], v["control_gap_pts"]) == (100.0, 100.0), "p1/p3 on the analysis set"
        assert v["verdict"] == "CEILING", "guards must not rescue p1"

    def test_guard_padding_with_ref_arm_keeps_the_band(self, mod):
        data = {**arms("1111100000"), "ref": flags("1111111111")}
        data = {arm: [*vals, False, False] for arm, vals in data.items()}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", ("ref",), guards=("10", "11"))
        assert v["accuracy_pct"]["base"] == 50.0, "guards leave the analysis-set accuracy unchanged"
        assert v["verdict"] == "PASS", "a reference arm splits the baseline failures"

    def test_ceiling_case_fails_p2(self, mod):
        data = {**arms("1111100000", ctrl="1000000000"), "ref": flags("1111111111")}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", ("ref",))
        assert v["ceiling_cases"] == ["0"], "a case every arm passes is ceiling"
        assert "NON-DISCRIMINATING" in v["failing_checks"], "one ceiling case fails p2"

    def test_guarding_most_of_the_corpus_fails(self, mod):
        # Regression: 100 cases, 98 guarded, the 2 left would otherwise pass.
        base = [i % 2 == 0 for i in range(100)]
        data = {"base": base, "aa": list(base), "ctrl": [False] * 100, "ref": [True] * 100}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", ("ref",), guards=tuple(str(i) for i in range(2, 100)))
        assert v["verdict"] == "TOO-MANY-GUARDS", "guards cannot shrink the analysis set to a handful of cases"

    def test_guards_within_the_cap_still_pass(self, mod):
        base = [i % 2 == 0 for i in range(20)]
        data = {"base": base, "aa": list(base), "ctrl": [False] * 20, "ref": [True] * 20}
        v = mod.pilot_verdict(data, "base", "ctrl", "aa", ("ref",), guards=("0", "1", "2", "3"))
        assert v["verdict"] == "PASS", "20% guards with 16 analysis cases is within the cap"

    def test_unknown_guard_case_raises(self, mod):
        with pytest.raises(ValueError, match="not case ids"):
            mod.pilot_verdict(PASSING, "base", "ctrl", "aa", ("ref",), guards=("q999",))

    def test_all_guarded_is_non_discriminating(self, mod):
        guards = tuple(str(i) for i in range(10))
        v = mod.pilot_verdict(PASSING, "base", "ctrl", "aa", ("ref",), guards=guards)
        assert v["verdict"] == "NON-DISCRIMINATING", "an empty analysis set cannot pass"

    def test_unnamed_arm_is_rejected(self, mod):
        data = {**PASSING, "chal": flags("1111111111")}
        with pytest.raises(ValueError, match="not named"):
            mod.pilot_verdict(data, "base", "ctrl", "aa")

    def test_aa_arm_is_required(self, mod):
        data = {"base": flags("1111100000"), "ctrl": flags("0000000000")}
        with pytest.raises(ValueError, match="--aa-arm"):
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

    def test_control_29_points_down_did_not_lose(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 29 + [True] * 31 + [False] * 40
        v = mod.pilot_verdict({"base": base, "aa": base, "ctrl": ctrl}, "base", "ctrl", "aa")
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 29-point gap is under the 30-point bar"

    def test_control_30_points_down_lost(self, mod):
        base, ctrl = [True] * 60 + [False] * 40, [False] * 30 + [True] * 30 + [False] * 40
        v = mod.pilot_verdict({"base": base, "aa": base, "ctrl": ctrl}, "base", "ctrl", "aa")
        assert "CONTROL-DID-NOT-LOSE" not in v["failing_checks"], "a 30-point gap meets the bar"

    def test_control_must_beat_twice_the_aa_noise(self, mod):
        data = {"base": [True] * 50 + [False] * 50, "ctrl": [True] * 15 + [False] * 85}
        data["aa"] = [True] * 70 + [False] * 30
        v = mod.pilot_verdict(data, "base", "ctrl", "aa")
        assert (v["aa_gap_pts"], v["control_gap_pts"]) == (20.0, 35.0), "setup: noise 20, gap 35"
        assert "CONTROL-DID-NOT-LOSE" in v["failing_checks"], "a 35-point gap is inside 2 x 20 noise"


class TestInputValidation:
    @pytest.mark.parametrize("bad", [["true"] * 10, [1] * 10, "1111100000", None])
    def test_non_bool_per_case_values_raise(self, mod, bad):
        with pytest.raises(ValueError, match="true/false"):
            mod.pilot_verdict({**PASSING, "base": bad}, "base", "ctrl", "aa", ("ref",))

    @pytest.mark.parametrize(
        ("data", "control"),
        [(PASSING, "nope"), ({**PASSING, "ctrl": [True]}, "ctrl"), (["base"], "ctrl")],
    )
    def test_bad_shape_raises(self, mod, data, control):
        with pytest.raises(ValueError):
            mod.pilot_verdict(data, "base", control, "aa", ("ref",))

    def test_same_arm_for_baseline_and_control_raises(self, mod):
        with pytest.raises(ValueError, match="must all differ"):
            mod.pilot_verdict(PASSING, "base", "base", "aa", ("ref",))

    def test_per_case_case_ids_must_match_the_case_count(self, mod):
        with pytest.raises(ValueError, match="distinct"):
            mod.pilot_verdict(PASSING, "base", "ctrl", "aa", ("ref",), case_ids=["a", "a"] + list("cdefghij"))


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

    def test_raw_json_input_scores_routes_and_guards_by_record_id(self, mod, tmp_path):
        rows = [(HIT, HIT, MISS)] * 5 + [(MISS, MISS, MISS)] * 5
        (tmp_path / "raw.json").write_text(json.dumps(raw3(rows)), encoding="utf-8")
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa") == 1, "q005-q009 are floor cases"
        guards = [f"q{i:03d}" for i in range(5, 10)]
        assert mod.pilot_check(out_dir=tmp_path, control="ctrl", aa="aa", guards=guards) == 1, "ceiling"
        verdict = json.loads((tmp_path / "pilot-verdict.json").read_text())
        assert verdict["guard_cases"] == guards, "the verdict reports each guard"
        assert verdict["verdict"] == "CEILING", "guarding every baseline failure leaves baseline at 100%"

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
        ids = [f"c{i}" for i in range(10)]
        src.write_text(json.dumps({"arms": arms("1111100000"), "case_ids": ids}), encoding="utf-8")
        argv = ["x", "--pilot-check", "--control-arm", "ctrl", "--aa-arm", "aa"]
        guards = [arg for cid in ids[5:] for arg in ("--guard-case", cid)]
        monkeypatch.setattr("sys.argv", [*argv, *guards, "--per-case", str(src), "--out-dir", str(tmp_path)])
        assert mod.main() == 1, "guarding every baseline failure leaves a ceiling analysis set"
        assert json.loads((tmp_path / "pilot-verdict.json").read_text())["verdict"] == "CEILING"

    def test_main_passes_with_a_reference_arm(self, mod, tmp_path, monkeypatch):
        src = tmp_path / "pilot.json"
        src.write_text(json.dumps({"arms": PASSING}), encoding="utf-8")
        argv = ["x", "--pilot-check", "--control-arm", "ctrl", "--aa-arm", "aa", "--extra-arm", "ref"]
        monkeypatch.setattr("sys.argv", [*argv, "--per-case", str(src), "--out-dir", str(tmp_path)])
        assert mod.main() == 0, "a reference arm splits the cases the baseline fails"

    @pytest.mark.parametrize("flag", ["--control-arm", "--extra-arm", "--guard-case"])
    def test_pilot_flags_rejected_outside_pilot_mode(self, mod, monkeypatch, flag):
        monkeypatch.setattr("sys.argv", ["routing-ab-test.py", "--gate", flag, "x"])
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 2, f"{flag} without --pilot-check is a usage error"
