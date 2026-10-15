"""Strict parsing of Jev's stage answers in jev-route.py.

A malformed Noul (NaN, out of range, string, bool) must fail the stage so the
caller falls back to full /do routing. It must not be coerced into a score that
attaches skills or skips routing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("jev_route_parsing", SCRIPTS / "jev-route.py")
jev_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_route)

BAD = [float("nan"), float("inf"), -1, 9, "0.5", True, None]
AGENTS, SKILLS, PIPELINES = {"a1", "a2"}, {"s1", "s2"}, {"p1"}


def _stage1() -> dict:
    return {
        "answers": {
            "agent": {"choice": "a1", "probabilities": {"a1": 0.7, "a2": 0.3}},
            "skill": {"choice": "s1", "probabilities": {"s1": 0.6, "s2": 0.4}},
            "pipeline": {"choice": "p1", "probabilities": {"p1": 0.5, "none": 0.5}},
            "needs_skill": {"noul": 0.9},
            "needs_pipeline": {"noul": 0.1},
            "prose_suffices": {"noul": 0.1},
        }
    }


def _stage2() -> dict:
    answers = {
        "agent": {"choice": "a1"},
        "skill": {"choice": "s1"},
        "agent_fit__a1": {"noul": 0.8},
        "skill_fit__s1": {"noul": 0.8},
    }
    answers.update({key: {"noul": 0.1} for key in jev_route.NOUL_SIGNAL_KEYS})
    return {"answers": answers}


def _parse2(data: dict) -> dict:
    return jev_route._parse_stage2(data, ["a1"], ["s1"], None, [], AGENTS, SKILLS, PIPELINES, 0.3)


def test_well_formed_answers_parse() -> None:
    assert jev_route._parse_stage1(_stage1(), AGENTS, SKILLS, PIPELINES)["agent_shortlist"] == ["a1", "a2"]
    decision = _parse2(_stage2())
    assert (decision["agent"], decision["skill"], decision["fallback"]) == ("a1", "s1", False)


@pytest.mark.parametrize("bad", BAD)
@pytest.mark.parametrize("key", ["needs_skill", "needs_pipeline", "prose_suffices"])
def test_stage1_gate_answer_must_be_a_probability(key: str, bad: object) -> None:
    data = _stage1()
    data["answers"][key] = {"noul": bad}
    with pytest.raises(ValueError, match="not a probability"):
        jev_route._parse_stage1(data, AGENTS, SKILLS, PIPELINES)


@pytest.mark.parametrize("bad", BAD)
@pytest.mark.parametrize("key", ["tests_requested", "agent_fit__a1", "skill_fit__s1"])
def test_stage2_answer_must_be_a_probability(key: str, bad: object) -> None:
    data = _stage2()
    data["answers"][key] = {"noul": bad}
    with pytest.raises(ValueError, match="not a probability"):
        _parse2(data)
