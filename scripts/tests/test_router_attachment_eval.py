"""Deterministic parts of the router-attachment eval (scripts/router_attachment/).

Replays recorded picks and Jev attachment evidence through jev-route.py's
attachment policy offline, scores them with the eval's own
scorer, and checks the /d contract names only skills that exist. No Jev or
model calls.
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

PATTERNS = {p.stem for p in (REPO / "skills" / "shared-patterns").glob("*.md")}


@pytest.fixture
def catalog(use_public_index):
    # Function scope: conftest's autouse index pin applies only inside a test,
    # so a module-scoped load would read the installed index instead.
    return run_eval.load_catalog()


@pytest.fixture
def skills_index(public_index_dir) -> dict:
    """Public skills from a tmp build; the checkout's INDEX.json may be absent or stale."""
    return json.loads((public_index_dir / "skills.json").read_text(encoding="utf-8"))["skills"]


@pytest.fixture
def agents_index(public_index_dir) -> dict:
    return json.loads((public_index_dir / "agents.json").read_text(encoding="utf-8"))["agents"]


# Fixture run r2 predates the agent retirement (plans/009): a record's `agent`
# is the old specialist pick. Under the new contract the session names the
# domain skill in its own `stack` instead, so the replay moves the pick there
# through the retired agent-to-domain floor (jev-route's DOMAIN_SKILL_BY_AGENT).
LEGACY_DOMAIN_FLOOR = {
    "golang-general-engineer": "programming",
    "kotlin-general-engineer": "programming",
    "php-general-engineer": "programming",
    "swift-general-engineer": "programming",
    "kubernetes-helm-engineer": "kubernetes",
    "ui-design-engineer": "frontend",
}


def _replay(record: dict, skill_names: set[str]) -> dict:
    result = dict(record)
    legacy = LEGACY_DOMAIN_FLOOR.get(result.pop("agent", None) or "")
    result["session_stack"] = [legacy] if legacy else []
    result["attach"] = jev_route._attachments(result, skill_names)
    result["agent"] = jev_route.WORKER_AGENT
    return result


def test_case_labels_name_real_components(catalog):
    for case in run_eval.load_cases():
        assert "agents" not in case and "forbid_agents" not in case, case["id"]
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
        "required": [["programming"], ["testing"]],
        "acceptable": ["workflow"],
        "forbid_skills": ["security"],
    }
    decision = {
        "agent": "general-purpose",
        "skill": "programming",
        "stack": ["anti-rationalization-core", "testing", "security"],
    }
    score = run_eval.score_case(case, decision, PATTERNS)
    assert score["attached"] == ["programming", "testing", "security"]
    assert score["groups_hit"] == 2
    assert score["attached_correct"] == 2
    assert score["forbidden_hit"] == ["security"]
    assert score["full"] is False
    assert run_eval.score_case(case, {"skill": "programming"}, PATTERNS)["worker"] == "general-purpose"
    met = run_eval.score_case(case, {"skill": "programming", "stack": ["testing"]}, PATTERNS)
    assert met["full"] is True  # no agent label: skills alone decide a full attach


def test_recorded_answers_meet_attachment_floor(catalog):
    """Offline replay of run r2: the policy must keep its measured quality."""
    fixture = json.loads((EVAL_DIR / "fixtures" / "jev-answers-r2.json").read_text(encoding="utf-8"))["cases"]
    cases = run_eval.load_cases()
    rows = []
    for case in cases:
        record = fixture[case["id"]]
        decision = record if record.get("source") == "jev-trivial-bypass" else _replay(record, catalog["skills"])
        rows.append({"id": case["id"], "decision": run_eval.d_model_decision(decision)})
    report = run_eval.report(rows, cases, PATTERNS)
    assert report["dev"]["full_attach"] >= 0.9, report["misses"]
    assert report["ood"]["full_attach"] >= 0.85, report["misses"]
    assert report["dev"]["skill_precision"] >= 0.9
    assert report["all"]["forbidden_hits"] == 0
    assert report["all"]["worker_share"] == 1.0


def test_attachments_policy_order_cap_and_validation(skills_index):
    result = {
        "skill": "debugging",
        "stack": ["programming"],
        "session_stack": ["programming"],
        "domain_scores": {"testing": 0.9, "kubernetes": 0.7, "frontend": 0.2, "research": 0.8},
        "signals": {"tests_requested": True, "local_only": True, "comprehensive_review": True},
    }
    attach = jev_route._attachments(result, set(skills_index))
    assert attach[0] == "programming"  # pre-route stack first, session floor deduped
    assert "local-only" in attach  # shared pattern rides without using the cap
    assert len([a for a in attach if a != "local-only"]) == jev_route.MAX_ATTACHMENTS
    assert "frontend" not in attach
    assert jev_route._attachments({"skill": "testing", "domain_scores": {"testing": 0.99}}, set(skills_index)) == []
    assert jev_route._attachments({"skill": "x", "stack": ["not-a-skill"]}, set(skills_index)) == []


def test_session_stack_is_the_domain_floor(skills_index):
    """The session's named domain skill attaches even when Jev evidence is empty."""
    result = {"skill": "debugging", "session_stack": ["kubernetes"], "domain_scores": None, "signals": None}
    assert jev_route._attachments(result, set(skills_index)) == ["kubernetes"]
    no_floor = {"skill": "testing", "domain_scores": {"programming": 0.1}}
    assert "programming" not in jev_route._attachments(no_floor, set(skills_index))


def test_policy_tables_name_real_components(skills_index):
    assert not hasattr(jev_route, "DOMAIN_SKILL_BY_AGENT")
    assert not hasattr(jev_route, "AGENT_BY_SKILL")
    for skill in LEGACY_DOMAIN_FLOOR.values():
        assert skill in skills_index
    for skill in jev_route.DOMAIN_NOUL_INSTRUCTIONS:
        assert skill in skills_index
    for name in jev_route.SIGNAL_SKILLS.values():
        assert name in skills_index or name in PATTERNS


def test_d_skill_attach_table_names_only_real_skills(skills_index, agents_index):  # agents_index: overlays only
    """The v1.1 Phase 4 table named four skills that no longer existed."""
    text = (REPO / "skills" / "meta" / "d" / "SKILL.md").read_text(encoding="utf-8")
    phase4 = text[text.index("### Phase 4") : text.index("### Phase 5")]
    for name in re.findall(r"`([a-z][a-z0-9-]+)`", phase4):
        if name in agents_index or name in jev_route.BUILTIN_AGENTS or name.endswith(".py"):
            continue
        if name in {"stack", "attach", "skill", "agent", "workers", "scope", "files"}:  # route and task_spec fields
            continue
        if name in {"domain_scores", "local_only"} or "_" in name:
            continue
        assert name in skills_index or name in PATTERNS, name


def test_d_skill_names_the_scripts_it_runs():
    text = (REPO / "skills" / "meta" / "d" / "SKILL.md").read_text(encoding="utf-8")
    for script in re.findall(r'"\$SDIR/([a-z0-9_.-]+\.(?:py|sh))"', text):
        assert (SCRIPTS / script).is_file(), script
    for needed in ("jev-route.py", "print-route-rules.py", "get-routing-manifest.sh", "--finalize"):
        assert needed in text


def test_d_model_decision_uses_attach_as_the_stack():
    route = {"agent": "general-purpose", "skill": "debugging", "attach": ["programming"], "stack": ["x"]}
    assert run_eval.d_model_decision(route)["stack"] == ["programming"]
    assert run_eval.d_model_decision({**route, "workers": [{"skill": "review", "scope": "a"}]})["workers"] == [
        {"skill": "review", "scope": "a"}
    ]
    assert run_eval.d_model_decision({"skill": "debugging", "stack": ["x"]})["stack"] == ["x"]
