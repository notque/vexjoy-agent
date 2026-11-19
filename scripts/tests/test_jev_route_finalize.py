"""prepare and finalize in jev-route.py: the deterministic parts of /d.

prepare runs the force-route guard and one Jev attachment call before the
session model picks. finalize validates the pick against the manifest, applies
the safety force route, computes `attach`, and sets the worker
(general-purpose, or a named private overlay agent; retired agents never). No test calls Jev or a model.
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

ENTRIES = [
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
] + [{"name": n, "type": "pipeline"} for n in ("pr-pipeline", "writing")]


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
    prepared = _prepare({"matched": False}, _jev_answers(domain__programming=0.95, tests_requested=0.9))
    route = jev_route.finalize(prepared, {"skill": "workflow", "confidence": "high"}, ENTRIES)
    assert (route["agent"], route["skill"], route["source"]) == ("general-purpose", "workflow", "session")
    assert route["attach"] == ["programming", "testing"]
    assert route["problems"] == []
    assert route["confidence"] == "high"
    assert "agent_source" not in route and "agents" not in route and "fallback_reason" not in route


def test_general_purpose_needs_no_fallback_reason() -> None:
    for agent in (None, "general-purpose"):
        route = jev_route.finalize({}, {"agent": agent, "skill": "workflow"}, ENTRIES)
        assert route["agent"] == "general-purpose"
        assert route["problems"] == []


@pytest.mark.parametrize("name", sorted(jev_route.routing_index_merge.RETIRED_AGENTS))
def test_finalize_never_emits_a_retired_agent(name: str) -> None:
    """Even when a stale agents index still lists the retired name."""
    route = jev_route.finalize({}, {"agent": name, "skill": "testing"}, ENTRIES, known_agents={name})
    assert route["agent"] == "general-purpose"
    assert any("not dispatchable" in p for p in route["problems"])
    assert route["skill"] == "testing"


@pytest.mark.parametrize("name", ["not-an-agent", "pr-workflow"])
def test_finalize_drops_an_unknown_agent(name: str) -> None:
    route = jev_route.finalize({}, {"agent": name, "skill": "testing"}, ENTRIES)
    assert any("not dispatchable" in p for p in route["problems"])
    assert route["agent"] == "general-purpose"


def test_finalize_keeps_a_named_overlay_agent() -> None:
    route = jev_route.finalize(
        {}, {"agent": "acme-overlay-engineer", "skill": "testing"}, ENTRIES, known_agents={"acme-overlay-engineer"}
    )
    assert route["agent"] == "acme-overlay-engineer"
    assert route["problems"] == []


def test_overlay_agents_come_from_the_index_minus_retired(tmp_path: Path, monkeypatch) -> None:
    index = tmp_path / "index"
    index.mkdir()
    agents = {"acme-overlay-engineer": {"file": "agents/a.md"}, "golang-general-engineer": {"file": "agents/g.md"}}
    (index / "agents.json").write_text(json.dumps({"agents": agents}), encoding="utf-8")
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index))
    known = jev_route._load_overlay_agents()
    assert "acme-overlay-engineer" in known
    assert "golang-general-engineer" not in known
    assert known >= jev_route.BUILTIN_AGENTS


def test_finalize_moves_a_skill_named_in_the_agent_slot() -> None:
    route = jev_route.finalize({}, {"agent": "workflow", "skill": None}, ENTRIES)
    assert route["skill"] == "workflow"
    assert route["skill_source"] == "session"
    assert route["agent"] == "general-purpose"


def test_finalize_validates_fanout_workers() -> None:
    decision = {
        "skill": "ghost",
        "pipeline": "ghost-pipeline",
        "workers": [
            {"skill": "review", "scope": "pkg/a"},
            "testing",
            {"skill": "ghost-skill", "scope": "pkg/b"},
            {"skill": "do"},
        ],
    }
    route = jev_route.finalize({}, decision, ENTRIES)
    assert route["pipeline"] is None
    assert route["workers"] == [{"skill": "review", "scope": "pkg/a"}, {"skill": "testing", "scope": ""}]
    assert len(route["problems"]) == 4
    assert (route["skill"], route["skill_source"]) == ("workflow", "fallback")


def test_legacy_agents_fanout_is_a_problem() -> None:
    route = jev_route.finalize({}, {"skill": "review", "agents": ["reviewer-system"]}, ENTRIES)
    assert route["workers"] == []
    assert any("'agents' is retired" in p for p in route["problems"])


@pytest.mark.parametrize("name", ["d", "do"])
def test_finalize_rejects_the_router_entry_points_as_skills(name: str) -> None:
    route = jev_route.finalize({}, {"skill": name}, ENTRIES)
    assert route["skill"] == "workflow"
    assert any(f"skill {name!r}" in p for p in route["problems"])


def test_domain_floor_comes_from_the_session_stack() -> None:
    """The domain skill the session names beside a methodology skill rides along without Jev evidence."""
    route = jev_route.finalize({}, {"skill": "workflow", "stack": ["programming", "ghost"]}, ENTRIES)
    assert route["attach"] == ["programming"]
    prepared = {"stack": ["kubernetes"], "domain_scores": {"testing": 0.9}}
    route = jev_route.finalize(prepared, {"skill": "workflow", "stack": ["programming"]}, ENTRIES)
    assert route["attach"] == ["kubernetes", "programming", "testing"]


def test_safety_force_route_overrides_the_picked_skill_and_pipeline() -> None:
    prepared = _prepare(_force("pr-workflow", pipeline="pr-pipeline", stack=["programming"]))
    route = jev_route.finalize(prepared, {"skill": "review"}, ENTRIES)
    assert (route["skill"], route["pipeline"], route["source"]) == ("pr-workflow", "pr-pipeline", "pre-route-force")
    assert route["skill_source"] == "pre-route"
    assert route["agent"] == "general-purpose"
    assert route["attach"] == ["programming"]


def test_safety_force_route_never_sets_the_agent() -> None:
    # A force route fixes the skill and pipeline only (/d Step 2, /do Phase 2 Step 1(a)).
    prepared = _prepare(_force("security", agent="reviewer-system"))
    route = jev_route.finalize(prepared, {"skill": "review"}, ENTRIES)
    assert route["agent"] == "general-purpose"
    assert (route["skill"], route["source"]) == ("security", "pre-route-force")


def test_safety_force_route_survives_a_failed_pick() -> None:
    prepared = _prepare(_force("security"))
    route = jev_route.finalize(prepared, {}, ENTRIES)
    assert route["skill"] == "security"
    assert route["agent"] == "general-purpose"
    assert route["source"] == "pre-route-force"


def test_complexity_comes_from_the_decision_or_is_derived() -> None:
    base = {"skill": "workflow"}
    assert jev_route.finalize({}, {**base, "complexity": "medium"}, ENTRIES)["complexity"] == "medium"
    assert jev_route.finalize({}, {**base, "complexity": "trivial"}, ENTRIES)["complexity"] == "simple"
    assert jev_route.finalize({}, {**base, "pipeline": "writing"}, ENTRIES)["complexity"] == "complex"
    assert jev_route.finalize({}, {**base, "workers": ["review"]}, ENTRIES)["complexity"] == "complex"
    prepared = {"signals": {"tests_requested": True}}
    assert jev_route.finalize(prepared, base, ENTRIES)["complexity"] == "medium"
    assert jev_route.finalize({}, base, ENTRIES)["complexity"] == "simple"


def test_finalize_output_is_usable_as_the_intent_validator_route_file() -> None:
    route = jev_route.finalize({}, {"skill": "workflow", "reasoning": "r"}, ENTRIES)
    for key in ("agent", "skill", "pipeline", "complexity", "source", "reasoning", "attach", "workers"):
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
    assert route["agent"] == "general-purpose"  # the retired agent never comes back out


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
