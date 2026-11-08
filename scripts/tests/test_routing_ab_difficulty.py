"""Tests for the A/B difficulty checks in scripts/routing-ab-test.py.

Covers the CEILING/FLOOR gate verdict (exit 3). The pre-run --pilot-check
lives in test_routing_ab_pilot.py. Pure functions on synthetic inputs, plus
the CLI path. No model calls.
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


class TestGateBound:
    def test_both_arms_perfect_is_ceiling_not_underpowered(self, mod):
        v = mod.gate_verdict(raw_of([(HIT, HIT)] * 20), "base", "chal")
        assert (v["verdict"], v["exit_code"]) == ("CEILING", 3), "two perfect arms must read CEILING, exit 3"

    def test_fix_strategy_v1_replay_is_ceiling(self, mod):
        # fix-strategy-v1: 8/8 fixed in both arms, reported by hand as a null.
        v = mod.gate_verdict(raw_of([(HIT, HIT)] * 8), "base", "chal")
        assert v["verdict"] == "CEILING", "the 8/8 vs 8/8 run must never read as no difference"

    def test_powered_run_at_ceiling_gets_the_normal_verdict(self, mod):
        # 95% vs 100% with 10 help pairs did discriminate, so it must not read "judged nothing".
        pairs = [(HIT, HIT)] * 190 + [(MISS, HIT)] * 10
        v = mod.gate_verdict(raw_of(pairs), "base", "chal")
        assert v["discordant_pairs"] == 10 and v["failing_gates"] == [], "setup: powered and passing"
        assert (v["verdict"], v["non_discriminating"]) == ("PROMOTE", None), "a powered run at a bound is PROMOTE"

    def test_underpowered_run_at_ceiling_is_ceiling(self, mod):
        pairs = [(HIT, HIT)] * 190 + [(MISS, HIT)] * 3 + [(HIT, MISS)] * 2
        v = mod.gate_verdict(raw_of(pairs), "base", "chal")
        assert v["discordant_pairs"] == 5, "setup: under the 6-pair bar"
        assert v["verdict"] == "CEILING", "an underpowered run at a bound reads CEILING, not UNDERPOWERED"

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
