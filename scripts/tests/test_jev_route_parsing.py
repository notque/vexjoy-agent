"""Strict parsing of Jev's attachment answers in jev-route.py.

A malformed Noul (NaN, out of range, string, bool) must fail the call so the
evidence stays empty. It must not be coerced into a score that attaches skills.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("jev_route_parsing", SCRIPTS / "jev-route.py")
jev_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_route)

BAD = [float("nan"), float("inf"), -1, 9, "0.5", True, None]
DOMAIN_KEYS = [
    f"{jev_route.DOMAIN_NOUL_PREFIX}{jev_route._sanitize_key(n)}" for n in jev_route.DOMAIN_NOUL_INSTRUCTIONS
]


def _answers(score: float = 0.1) -> dict:
    keys = list(jev_route.NOUL_SIGNAL_KEYS) + DOMAIN_KEYS
    return {"answers": {key: {"noul": score} for key in keys}}


def test_well_formed_answers_parse() -> None:
    data = _answers(0.1)
    data["answers"]["tests_requested"] = {"noul": 0.9}
    data["answers"][f"{jev_route.DOMAIN_NOUL_PREFIX}programming"] = {"noul": 0.8}
    parsed = jev_route._parse_attach(data)
    assert parsed["signals"]["tests_requested"] is True
    assert parsed["signals"]["local_only"] is False
    assert parsed["domain_scores"]["programming"] == 0.8
    assert set(parsed["domain_scores"]) == set(jev_route.DOMAIN_NOUL_INSTRUCTIONS)


@pytest.mark.parametrize("bad", BAD)
@pytest.mark.parametrize("key", ["tests_requested", "local_only", f"{jev_route.DOMAIN_NOUL_PREFIX}programming"])
def test_answer_must_be_a_probability(key: str, bad: object) -> None:
    data = _answers()
    data["answers"][key] = {"noul": bad}
    with pytest.raises(ValueError, match="not a probability"):
        jev_route._parse_attach(data)


@pytest.mark.parametrize("key", ["research_needed", f"{jev_route.DOMAIN_NOUL_PREFIX}testing"])
def test_a_missing_answer_fails_the_call(key: str) -> None:
    data = _answers()
    del data["answers"][key]
    with pytest.raises(KeyError):
        jev_route._parse_attach(data)


def test_a_malformed_answer_leaves_the_evidence_empty_but_routing_continues() -> None:
    data = _answers()
    data["answers"]["tests_requested"] = {"noul": float("nan")}
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value={"matched": False}),
        mock.patch.object(jev_route.jev_transport, "available", return_value=(True, "")),
        mock.patch.object(jev_route, "_call_jev", return_value=(data, 5.0)),
    ):
        result = jev_route.prepare("add a test", 5)
    assert result["available"] is True
    assert result["signals"] is None
    assert result["domain_scores"] is None
    assert "not a probability" in result["error"]
    entries = [{"name": "python-general-engineer", "type": "agent"}, {"name": "testing", "type": "skill"}]
    route = jev_route.finalize(result, {"agent": "python-general-engineer", "skill": "testing"}, entries)
    assert (route["agent"], route["skill"], route["attach"], route["problems"]) == (
        "python-general-engineer",
        "testing",
        [],
        [],
    )
