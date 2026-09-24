"""Deterministic parts of the router-attachment eval (scripts/router_attachment/).

Replays recorded Jev answers through jev-route.py's attachment and agent-default
policy offline, scores them with the eval's own scorer, and checks the /d
contract names only skills that exist. No Jev or model calls.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
EVAL_DIR = REPO / "scripts" / "router_attachment"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jev_route = _load("jev_route_attach", SCRIPTS / "jev-route.py")
run_eval = _load("router_attachment_run_eval", EVAL_DIR / "run_eval.py")

SKILLS_INDEX = json.loads((REPO / "skills" / "INDEX.json").read_text(encoding="utf-8"))["skills"]
AGENTS_INDEX = json.loads((REPO / "agents" / "INDEX.json").read_text(encoding="utf-8"))["agents"]
PATTERNS = {p.stem for p in (REPO / "skills" / "shared-patterns").glob("*.md")}


@pytest.fixture
def catalog():
    # Function scope: conftest's autouse index pin applies only inside a test,
    # so a module-scoped load would read the installed index instead.
    return run_eval.load_catalog()


def _replay(record: dict, skill_names: set[str]) -> dict:
    result = dict(record)
    result["attach"] = jev_route._attachments(result, skill_names)
    if result.get("agent") in (None, "general-purpose"):
        result["agent"] = jev_route._default_agent(result) or result.get("agent")
    return result


def test_case_labels_name_real_components(catalog):
    for case in run_eval.load_cases():
        for agent in case["agents"] + case["forbid_agents"]:
            assert agent == "*" or agent in catalog["agents"], (case["id"], agent)
        names = [s for group in case["required"] for s in group] + case["acceptable"] + case["forbid_skills"]
        for name in names:
            assert name in catalog["skills"], (case["id"], name)


def test_eval_has_dev_and_held_out_splits():
    cases = run_eval.load_cases()
    assert len({c["id"] for c in cases}) == len(cases)
    assert sum(c["split"] == "dev" for c in cases) >= 40
    assert sum(c["split"] == "ood" for c in cases) >= 12


def test_scorer_counts_groups_precision_and_forbidden():
    case = {
        "id": "x",
        "split": "dev",
        "domain": "go",
        "agents": ["golang-general-engineer"],
        "required": [["programming"], ["testing"]],
        "acceptable": ["workflow"],
        "forbid_agents": [],
        "forbid_skills": ["security"],
    }
    decision = {
        "agent": "golang-general-engineer",
        "skill": "programming",
        "stack": ["anti-rationalization-core", "testing", "security"],
    }
    score = run_eval.score_case(case, decision, PATTERNS)
    assert score["attached"] == ["programming", "testing", "security"]
    assert score["groups_hit"] == 2
    assert score["attached_correct"] == 2
    assert score["forbidden_hit"] == ["security"]
    assert score["full"] is False
    assert run_eval.score_case(case, {"skill": "programming"}, PATTERNS)["agent"] == "general-purpose"


def test_recorded_answers_meet_attachment_floor(catalog):
    """Offline replay of run r2: the policy must keep its measured quality."""
    fixture = json.loads((EVAL_DIR / "fixtures" / "jev-answers-r2.json").read_text(encoding="utf-8"))["cases"]
    cases = run_eval.load_cases()
    rows = []
    for case in cases:
        record = fixture[case["id"]]
        decision = record if record.get("source") == "jev-trivial-bypass" else _replay(record, catalog["skills"])
        rows.append({"id": case["id"], "decision": run_eval.d_code_decision(decision)})
    report = run_eval.report(rows, cases, PATTERNS)
    assert report["dev"]["full_attach"] >= 0.9, report["misses"]
    assert report["ood"]["full_attach"] >= 0.85, report["misses"]
    assert report["dev"]["skill_precision"] >= 0.9
    assert report["all"]["forbidden_hits"] == 0


def test_attachments_policy_order_cap_and_validation():
    result = {
        "agent": "golang-general-engineer",
        "skill": "debugging",
        "stack": ["programming"],
        "domain_scores": {"testing": 0.9, "kubernetes": 0.7, "frontend": 0.2, "research": 0.8},
        "signals": {"tests_requested": True, "local_only": True, "comprehensive_review": True},
    }
    attach = jev_route._attachments(result, set(SKILLS_INDEX))
    assert attach[0] == "programming"  # pre-route stack first, floor deduped
    assert "local-only" in attach  # shared pattern rides without using the cap
    assert len([a for a in attach if a != "local-only"]) == jev_route.MAX_ATTACHMENTS
    assert "frontend" not in attach
    assert jev_route._attachments({"skill": "testing", "domain_scores": {"testing": 0.99}}, set(SKILLS_INDEX)) == []
    assert jev_route._attachments({"skill": "x", "stack": ["not-a-skill"]}, set(SKILLS_INDEX)) == []


def test_python_agent_never_gets_the_programming_floor():
    assert "python-general-engineer" not in jev_route.DOMAIN_SKILL_BY_AGENT
    result = {"agent": "python-general-engineer", "skill": "testing", "domain_scores": {"programming": 0.1}}
    assert "programming" not in jev_route._attachments(result, set(SKILLS_INDEX))


def test_policy_tables_name_real_components():
    for agent, skill in jev_route.DOMAIN_SKILL_BY_AGENT.items():
        assert agent in AGENTS_INDEX and skill in SKILLS_INDEX
    for skill, agent in jev_route.AGENT_BY_SKILL.items():
        assert skill in SKILLS_INDEX and agent in AGENTS_INDEX
    for skill in jev_route.DOMAIN_NOUL_INSTRUCTIONS:
        assert skill in SKILLS_INDEX
    for name in jev_route.SIGNAL_SKILLS.values():
        assert name in SKILLS_INDEX or name in PATTERNS


def test_d_skill_attach_table_names_only_real_skills():
    """The v1.1 Phase 4 table named four skills that no longer existed."""
    text = (REPO / "skills" / "meta" / "d" / "SKILL.md").read_text(encoding="utf-8")
    phase4 = text[text.index("### Phase 4") : text.index("### Phase 5")]
    for name in re.findall(r"`([a-z][a-z0-9-]+)`", phase4):
        if name in AGENTS_INDEX or name.endswith(".py") or name in {"stack", "attach", "skill"}:
            continue
        if name in {"domain_scores", "local_only"} or "_" in name:
            continue
        assert name in SKILLS_INDEX or name in PATTERNS, name


def _classified(**overrides) -> dict:
    base = {
        "fallback": False,
        "source": "jev",
        "jev_called": True,
        "agent": "golang-general-engineer",
        "skill": "programming",
        "pipeline": None,
        "stack": [],
        "agents": [],
        "signals": {"tests_requested": False},
        "domain_scores": {"programming": 0.95},
        "complexity": "simple",
        "reasoning": "jev pick",
    }
    base.update(overrides)
    return base


def _force(skill: str, pipeline: str | None = None, stack: list | None = None) -> dict:
    return {
        "matched": True,
        "confidence": "high",
        "match_type": "force_route",
        "agent": None,
        "skill": skill,
        "pipeline": pipeline,
        "reasoning": f"matched triggers for {skill}",
        "stack": stack or [],
    }


def test_safety_force_route_keeps_skill_and_takes_jev_agent():
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=_force("pr-workflow", stack=["programming"])),
        mock.patch.object(
            jev_route, "_classify", return_value=(_classified(skill="code-quality"), set(SKILLS_INDEX))
        ) as classify,
    ):
        result = jev_route.route("commit main.go and open a PR", 0.3, 0.3, 5)
    assert classify.call_args.kwargs["hint_skill"] is None
    assert result["source"] == "pre-route-force"
    assert result["skill"] == "pr-workflow"
    assert result["agent"] == "golang-general-engineer"
    assert result["attach"] == ["programming"]


def test_safety_force_route_survives_jev_failure():
    failed = {"fallback": True, "source": "error", "jev_called": True, "fallback_reason": "boom"}
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=_force("security")),
        mock.patch.object(jev_route, "_classify", return_value=(failed, set())),
    ):
        result = jev_route.route("security audit of auth", 0.3, 0.3, 5)
    assert result["skill"] == "security"
    assert result["fallback"] is False
    assert result["agent"] == "reviewer-system"  # skill-owned default agent


def test_other_force_route_is_a_hint_not_a_verdict():
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=_force(None, pipeline="writing")),
        mock.patch.object(
            jev_route,
            "_classify",
            return_value=(_classified(agent="hook-development-engineer", skill="workflow"), set(SKILLS_INDEX)),
        ),
    ):
        result = jev_route.route("Write a PostToolUse hook", 0.3, 0.3, 5)
    assert result["source"] == "jev"
    assert result["pipeline"] is None
    assert result["pre_route_hint"]["pipeline"] == "writing"


def test_other_force_route_stands_when_jev_calls_it_trivial():
    trivial = {"fallback": False, "source": "jev-trivial-bypass", "jev_called": True}
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=_force("building-with-jev")),
        mock.patch.object(jev_route, "_classify", return_value=(trivial, set(SKILLS_INDEX))),
    ):
        result = jev_route.route("jev", 0.3, 0.3, 5)
    assert result["skill"] == "building-with-jev"
    assert result["agent"] == "python-general-engineer"
