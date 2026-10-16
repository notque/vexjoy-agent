"""prepare and finalize in jev-route.py: the deterministic parts of /d.

prepare runs the force-route guard and one Jev attachment call before the
session model picks. finalize validates the pick against the manifest, applies
the safety force route, and computes `attach`. No test calls Jev or a model.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("jev_route_finalize", SCRIPTS / "jev-route.py")
jev_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_route)

ENTRIES = (
    [
        {"name": n, "type": "agent"}
        for n in (
            "golang-general-engineer",
            "python-general-engineer",
            "reviewer-system",
            "research-coordinator-engineer",
            "testing-automation-engineer",
        )
    ]
    + [
        {"name": n, "type": "skill"}
        for n in (
            "pr-workflow",
            "security",
            "workflow",
            "testing",
            "review",
            "programming",
            "frontend",
            "kubernetes",
            "research",
            "d",
            "do",
        )
    ]
    + [{"name": n, "type": "pipeline"} for n in ("pr-pipeline", "writing")]
)


def _force(skill: str | None, pipeline: str | None = None, stack: list | None = None, **extra) -> dict:
    return {
        "matched": True,
        "confidence": "high",
        "match_type": "force_route",
        "agent": None,
        "skill": skill,
        "pipeline": pipeline,
        "reasoning": f"matched triggers for {skill or pipeline}",
        "stack": stack or [],
        **extra,
    }


def _jev_answers(**scores: float) -> dict:
    keys = list(jev_route.NOUL_SIGNAL_KEYS) + [
        f"{jev_route.DOMAIN_NOUL_PREFIX}{jev_route._sanitize_key(n)}" for n in jev_route.DOMAIN_NOUL_INSTRUCTIONS
    ]
    return {
        "answers": {k: {"noul": scores.get(k, 0.05)} for k in keys},
        "usage": {"input_tokens": 800, "output_tokens": 210},
    }


def _prepare(pre_route: dict, answers: dict | None = None, available: bool = True) -> dict:
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=pre_route),
        mock.patch.object(jev_route.jev_transport, "available", return_value=(available, "no key")),
        mock.patch.object(jev_route, "_call_jev", return_value=(answers or _jev_answers(), 12.0)) as call,
    ):
        result = jev_route.prepare("request", 5)
    result["_calls"] = call.call_count
    return result


# ---------------------------------------------------------------- prepare


def test_prepare_makes_one_jev_call_and_carries_no_pick() -> None:
    result = _prepare({"matched": False})
    assert result["_calls"] == 1
    assert (result["source"], result["forced"], result["error"]) == ("session", None, None)
    assert set(result["signals"]) == set(jev_route.NOUL_SIGNAL_KEYS)
    assert set(result["domain_scores"]) == set(jev_route.DOMAIN_NOUL_INSTRUCTIONS)
    assert "agent" not in result and "skill" not in result and "pipeline" not in result


def test_attach_payload_asks_only_noul_questions_and_carries_project_facts() -> None:
    project = {"languages": ["python"]}
    payload = jev_route._build_attach_payload("fix it", project)
    assert payload["state"] == {"request": "fix it", "project": project}
    assert {q["type"] for q in payload["questions"].values()} == {"noul"}
    assert len(payload["questions"]) == len(jev_route.NOUL_SIGNAL_KEYS) + len(jev_route.DOMAIN_NOUL_INSTRUCTIONS)
    assert jev_route._build_attach_payload("fix it")["state"] == "fix it"


def test_safety_force_route_is_recorded_with_its_stack() -> None:
    result = _prepare(_force("pr-workflow", pipeline="pr-pipeline", stack=["programming"]))
    assert result["source"] == "pre-route-force"
    assert result["forced"]["skill"] == "pr-workflow"
    assert result["forced"]["pipeline"] == "pr-pipeline"
    assert result["stack"] == ["programming"]


def test_non_safety_force_route_and_suggestions_are_dropped() -> None:
    assert _prepare(_force("deploy"))["forced"] is None
    assert _prepare(_force(None, pipeline="writing"))["forced"] is None
    suggestion = {"matched": False, "skill": "pr-workflow", "match_type": "fallthrough", "confidence": "low"}
    assert _prepare(suggestion)["forced"] is None


def test_a_low_confidence_safety_match_is_not_forced() -> None:
    assert _prepare(_force("security", confidence="low"))["forced"] is None


def test_jev_failure_keeps_the_force_route_and_leaves_evidence_empty() -> None:
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=_force("security")),
        mock.patch.object(jev_route.jev_transport, "available", return_value=(True, "")),
        mock.patch.object(jev_route, "_call_jev", side_effect=RuntimeError("boom")),
    ):
        result = jev_route.prepare("security audit of auth", 5)
    assert result["forced"]["skill"] == "security"
    assert result["domain_scores"] is None
    assert "boom" in result["error"]


def test_unavailable_transport_skips_jev_and_keeps_the_force_route() -> None:
    result = _prepare(_force("security"), available=False)
    assert (result["available"], result["jev_called"], result["_calls"]) == (False, False, 0)
    assert result["forced"]["skill"] == "security"
    assert "unavailable" in result["error"]


# ---------------------------------------------------------------- finalize


def test_finalize_keeps_a_valid_pick_and_adds_the_attachments() -> None:
    prepared = _prepare({"matched": False}, _jev_answers(programming=0.95, tests_requested=0.9))
    route = jev_route.finalize(
        prepared, {"agent": "golang-general-engineer", "skill": "workflow", "confidence": "high"}, ENTRIES
    )
    assert (route["agent"], route["skill"], route["source"], route["agent_source"]) == (
        "golang-general-engineer",
        "workflow",
        "session",
        "session",
    )
    assert route["attach"] == ["programming", "testing"]
    assert route["problems"] == []
    assert route["confidence"] == "high"


@pytest.mark.parametrize("name", ["not-an-agent", "pr-workflow"])
def test_finalize_drops_an_agent_outside_agents(name: str) -> None:
    route = jev_route.finalize({}, {"agent": name, "skill": "testing"}, ENTRIES)
    assert any("not in AGENTS" in p for p in route["problems"])
    assert route["agent"] == "testing-automation-engineer"  # the skill's owning agent
    assert route["agent_source"] == "skill-default"


def test_finalize_moves_a_skill_named_in_the_agent_slot() -> None:
    route = jev_route.finalize({}, {"agent": "workflow", "skill": None}, ENTRIES)
    assert route["skill"] == "workflow"
    assert route["skill_source"] == "session"


def test_finalize_drops_unknown_skills_pipelines_and_fanout_agents() -> None:
    decision = {
        "agent": "python-general-engineer",
        "skill": "ghost",
        "pipeline": "ghost-pipeline",
        "agents": ["python-general-engineer", "ghost-agent", "reviewer-system", "reviewer-system"],
    }
    route = jev_route.finalize({}, decision, ENTRIES)
    assert route["pipeline"] is None
    assert route["agents"] == ["reviewer-system"]
    assert len(route["problems"]) == 3
    assert (route["skill"], route["skill_source"]) == ("workflow", "fallback")


@pytest.mark.parametrize("name", ["d", "do"])
def test_finalize_rejects_the_router_entry_points_as_skills(name: str) -> None:
    route = jev_route.finalize({}, {"agent": "python-general-engineer", "skill": name}, ENTRIES)
    assert route["skill"] == "workflow"
    assert any(f"skill {name!r}" in p for p in route["problems"])


def test_safety_force_route_overrides_the_picked_skill_and_pipeline() -> None:
    prepared = _prepare(_force("pr-workflow", pipeline="pr-pipeline", stack=["programming"]))
    route = jev_route.finalize(prepared, {"agent": "golang-general-engineer", "skill": "review"}, ENTRIES)
    assert (route["skill"], route["pipeline"], route["source"]) == ("pr-workflow", "pr-pipeline", "pre-route-force")
    assert route["skill_source"] == "pre-route"
    assert route["agent"] == "golang-general-engineer"
    assert route["attach"] == ["programming"]


def test_safety_force_route_survives_a_failed_pick() -> None:
    prepared = _prepare(_force("security"))
    route = jev_route.finalize(prepared, {}, ENTRIES)
    assert route["skill"] == "security"
    assert route["agent"] == "reviewer-system"  # skill-owned default agent
    assert route["source"] == "pre-route-force"


def test_general_purpose_without_a_reason_is_a_problem_and_with_one_is_not() -> None:
    bare = jev_route.finalize({}, {"agent": "general-purpose", "skill": "workflow"}, ENTRIES)
    assert bare["agent"] == "general-purpose"
    assert any("fallback_reason" in p for p in bare["problems"])
    reasoned = jev_route.finalize(
        {}, {"agent": None, "skill": "workflow", "fallback_reason": "general-purpose: no listed agent"}, ENTRIES
    )
    assert reasoned["problems"] == []
    assert reasoned["fallback_reason"] == "general-purpose: no listed agent"


def test_complexity_comes_from_the_decision_or_is_derived() -> None:
    base = {"agent": "python-general-engineer", "skill": "workflow", "fallback_reason": "x"}
    assert jev_route.finalize({}, {**base, "complexity": "medium"}, ENTRIES)["complexity"] == "medium"
    assert jev_route.finalize({}, {**base, "complexity": "trivial"}, ENTRIES)["complexity"] == "simple"
    assert jev_route.finalize({}, {**base, "pipeline": "writing"}, ENTRIES)["complexity"] == "complex"
    prepared = {"signals": {"tests_requested": True}}
    assert jev_route.finalize(prepared, base, ENTRIES)["complexity"] == "medium"


def test_finalize_output_is_usable_as_the_intent_validator_route_file() -> None:
    route = jev_route.finalize({}, {"agent": "python-general-engineer", "skill": "workflow", "reasoning": "r"}, ENTRIES)
    for key in ("agent", "skill", "pipeline", "complexity", "source", "reasoning", "attach", "agents"):
        assert key in route
    json.dumps(route)


# ---------------------------------------------------------------- CLI


def test_cli_finalize_reads_files_and_prints_the_route(tmp_path: Path, use_public_index: Path) -> None:
    result_file = tmp_path / "result.json"
    decision_file = tmp_path / "decision.json"
    result_file.write_text(json.dumps({"forced": None, "stack": []}), encoding="utf-8")
    decision_file.write_text(json.dumps({"agent": "python-general-engineer", "skill": "workflow"}), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "jev-route.py"),
            "--finalize",
            "--result-file",
            str(result_file),
            "--decision-file",
            str(decision_file),
            "--json-compact",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    route = json.loads(proc.stdout)
    assert route["skill"] == "workflow"


def test_cli_finalize_reports_an_unreadable_file_as_an_error_not_a_crash(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "jev-route.py"),
            "--finalize",
            "--result-file",
            str(tmp_path / "missing.json"),
            "--decision-file",
            str(tmp_path / "missing2.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["error"]
