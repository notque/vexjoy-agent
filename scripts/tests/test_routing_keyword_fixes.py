"""Router keyword fixes found by the router attachment eval (2026-09-23).

- Trigger matching: the last word of a multi-word trigger takes a plain
  inflection only, so "write post" no longer matches PostToolUse or Postgres.
- "review my changes" routes to `review`; security phrasings stay on `security`.
- "ship it" force-routes alone but only suggests inside "before I ship it".
- Private (overlay) entries are candidates only when the request names their
  domain. Synthetic `acmebrand-*` names stand in for real private skills.
- A renamed agent's old name still resolves to the current agent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import routing_index_merge as rim


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pre_route = _load("pre_route_keyword_fixes", SCRIPTS / "pre-route.py")
jev_route = _load("jev_route_keyword_fixes", SCRIPTS / "jev-route.py")
routing_manifest = _load("routing_manifest_keyword_fixes", SCRIPTS / "routing-manifest.py")
build_dispatch = _load("build_dispatch_keyword_fixes", SCRIPTS / "build-dispatch.py")


@pytest.fixture
def entries(use_public_index) -> list[dict]:
    """Public index entries from a tmp build.

    The checkout's INDEX.json is generated and gitignored, and ``load_entries``
    regenerates it in place when missing.
    """
    return pre_route.load_entries()


# ---------------------------------------------------------------- word boundary


@pytest.mark.parametrize(
    "request_text",
    [
        "Write a PostToolUse hook that warns when an edit adds a TODO without an issue link",
        "Write a zero-downtime Postgres migration that splits users.name into first and last name columns",
        "write the postmortem for last night's outage",
    ],
)
def test_last_trigger_word_does_not_prefix_match(request_text: str) -> None:
    assert not pre_route._build_pattern("write post").search(request_text.lower())


@pytest.mark.parametrize(
    ("trigger", "request_text"),
    [
        ("write post", "write two posts about webhooks"),
        ("go test", "run the go tests"),
        ("diff review", "review this diff with separate reviewers"),
        ("write post", "write a post"),
    ],
)
def test_last_trigger_word_keeps_inflections(trigger: str, request_text: str) -> None:
    assert pre_route._build_pattern(trigger).search(request_text.lower())


def test_posttooluse_request_is_not_a_writing_route(entries) -> None:
    result = pre_route.route("Write a PostToolUse hook that warns on TODOs", entries=entries)
    assert result["pipeline"] != "writing"
    assert result["skill"] != "writing"


# ---------------------------------------------------------------- review / security


@pytest.mark.parametrize("request_text", ["review my changes", "please review my changes to the parser"])
def test_plain_review_my_changes_routes_to_review(entries, request_text: str) -> None:
    result = pre_route.route(request_text, entries=entries)
    assert result["matched"] is True
    assert result["skill"] == "review"


@pytest.mark.parametrize(
    "request_text", ["review my changes for security", "review my changes for vulnerabilities", "security review"]
)
def test_security_review_phrasings_stay_on_security(entries, request_text: str) -> None:
    result = pre_route.route(request_text, entries=entries)
    assert result["matched"] is True
    assert result["skill"] == "security"


# ---------------------------------------------------------------- ship it


def test_bare_ship_it_still_force_routes(entries) -> None:
    result = pre_route.route("ship it", entries=entries)
    assert (result["skill"], result["confidence"], result["match_type"]) == ("pr-workflow", "high", "force_route")


@pytest.mark.parametrize(
    "request_text",
    [
        "can u look over what I changed in the .go files before I ship it",
        "tidy the error messages so we can ship it",
    ],
)
def test_ship_it_in_a_later_clause_only_suggests(entries, request_text: str) -> None:
    result = pre_route.route(request_text, entries=entries)
    assert result["matched"] is False
    assert result["confidence"] == "low"
    assert result["skill"] in ("pr-workflow", "code-quality", None)
    if result["skill"] == "pr-workflow":
        assert result["reasoning"].startswith("suggest-only")


def test_other_pr_trigger_keeps_force_route_with_ship_it(entries) -> None:
    result = pre_route.route("before I ship it, open a PR", entries=entries)
    assert (result["skill"], result["confidence"]) == ("pr-workflow", "high")


def test_suggestion_ranks_below_a_force_match() -> None:
    table = pre_route.build_match_table(
        [
            {"name": "pr-workflow", "type": "skill", "triggers": ["ship it"], "agent": None, "force_route": True},
            {"name": "review", "type": "skill", "triggers": ["look over"], "agent": None, "force_route": True},
        ]
    )
    request = "look over this before I ship it, it is ready for the last pass"
    candidates = pre_route.score_matches(table, request)
    candidates["skill:pr-workflow"].score += 10  # a suggestion must lose even with the higher score
    assert pre_route.determine_confidence(candidates["skill:pr-workflow"], request) == "low"
    assert pre_route.determine_confidence(candidates["skill:review"], request) == "high"


def test_jev_route_passes_a_suggestion_as_a_hint() -> None:
    suggestion = {
        "matched": False,
        "agent": None,
        "skill": "pr-workflow",
        "pipeline": None,
        "confidence": "low",
        "match_type": "fallthrough",
        "reasoning": "suggest-only match",
        "stack": [],
    }
    failed = {"fallback": True, "source": "error", "jev_called": True, "fallback_reason": "boom"}
    with (
        mock.patch.object(jev_route, "_run_pre_route", return_value=suggestion),
        mock.patch.object(jev_route, "_classify", return_value=(failed, set())) as classify,
    ):
        result = jev_route.route("look over my diff before I ship it", 0.3, 0.3, 5)
    assert classify.call_args.kwargs["hint_skill"] == "pr-workflow"
    assert result.get("skill") != "pr-workflow"  # a suggestion never stands alone


# ---------------------------------------------------------------- private gate


def _synthetic_catalog() -> list[dict]:
    return [
        {
            "name": "research",
            "type": "skill",
            "description": "Research: gather sources, compare findings, write a cited summary.",
            "triggers": ["research", "fact-check"],
        },
        {
            "name": "writing",
            "type": "skill",
            "description": "Writing: articles, explainers, voice profiles.",
            "triggers": ["write article", "voice"],
        },
        {
            "name": "acmebrand-research",
            "type": "skill",
            "description": "Research for the Acmebrand site.",
            "triggers": ["acmebrand-research", "acmebrand", "research", "comparison"],
            "private": True,
        },
        {
            "name": "voice-zorblax",
            "type": "skill",
            "description": "Write in Zorblax's voice.",
            "triggers": ["voice-zorblax", "voice", "zorblax"],
            "private": True,
        },
    ]


@pytest.mark.parametrize(
    "request_text",
    [
        "Research how other CLI agents route requests and summarize the tradeoffs with sources",
        "write an article in a friendly voice",
        "a comparison of bun and node",
    ],
)
def test_private_entries_need_a_domain_match(request_text: str) -> None:
    kept = {e["name"] for e in rim.gate_private_entries(_synthetic_catalog(), request_text)}
    assert kept == {"research", "writing"}


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("research this week's Acmebrand results", "acmebrand-research"),
        ("use acmebrand-research on the new roster", "acmebrand-research"),
        ("write this in zorblax's voice", "voice-zorblax"),
    ],
)
def test_private_entry_offered_when_request_names_its_domain(request_text: str, expected: str) -> None:
    kept = {e["name"] for e in rim.gate_private_entries(_synthetic_catalog(), request_text)}
    assert expected in kept
    assert {"research", "writing"} <= kept


def test_domain_terms_skip_public_and_generic_words() -> None:
    catalog = _synthetic_catalog()
    vocab = rim.public_vocabulary(catalog)
    assert rim.domain_terms(catalog[2], vocab) == {"acmebrand"}
    assert rim.domain_terms(catalog[3], vocab) == {"zorblax"}


def test_pre_route_gates_private_force_entries() -> None:
    catalog = [
        {"name": "research", "type": "skill", "triggers": ["research"], "agent": None, "force_route": False},
        {
            "name": "acmebrand-research",
            "type": "skill",
            "triggers": ["acmebrand", "research"],
            "agent": None,
            "force_route": True,
            "private": True,
        },
    ]
    assert pre_route.route("research the fastest json parser", entries=catalog)["matched"] is False
    hit = pre_route.route("research acmebrand ratings", entries=catalog)
    assert (hit["matched"], hit["skill"]) == (True, "acmebrand-research")


def test_jev_route_drops_private_candidates_without_domain_match() -> None:
    seen: dict = {}

    def capture(request_text, agent_criteria, skill_criteria, pipeline_criteria, project):
        seen["skills"] = set(skill_criteria)
        raise RuntimeError("stop after candidate building")

    manifest = [dict(e, agent=None) for e in _synthetic_catalog()]
    with (
        mock.patch.object(jev_route.jev_transport, "available", return_value=(True, "")),
        mock.patch.object(jev_route, "_load_manifest_entries", return_value=manifest),
        mock.patch.object(jev_route, "_build_stage1_payload", side_effect=capture),
    ):
        jev_route._classify("research the history of RSS", 0.3, 0.3, 5, None, 3)
        assert seen["skills"] == {"research", "writing"}
        jev_route._classify("research the acmebrand archive", 0.3, 0.3, 5, None, 3)
        assert "acmebrand-research" in seen["skills"]


def _write_index(path: Path, kind: str, items: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({kind: items}), encoding="utf-8")


def test_private_names_from_legacy_local_overlay(tmp_path: Path) -> None:
    tracked = tmp_path / "skills" / "INDEX.json"
    _write_index(tracked, "skills", {"research": {"triggers": ["research"]}})
    _write_index(
        tmp_path / "skills" / "INDEX.local.json",
        "skills",
        {"research": {"triggers": ["research"]}, "acmebrand-research": {"triggers": ["acmebrand"]}},
    )
    assert rim.private_names_for("skills", tracked, "INDEX.local.json", repo_root=tmp_path) == {"acmebrand-research"}


def test_private_names_from_installed_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installed = tmp_path / "installed"
    _write_index(
        installed / "skills.json",
        "skills",
        {"research": {"owner": "public"}, "acmebrand-research": {"owner": "overlay:private"}},
    )
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(installed))
    tracked = tmp_path / "skills" / "INDEX.json"
    assert rim.private_names_for("skills", tracked, "INDEX.local.json", repo_root=tmp_path) == {"acmebrand-research"}


# ---------------------------------------------------------------- agent rename


def test_old_agent_name_maps_to_current_name() -> None:
    assert rim.canonical_agent_name("ui-frontend-engineer") == "ui-design-engineer"
    assert rim.canonical_agent_name("golang-general-engineer") == "golang-general-engineer"
    for new in rim.AGENT_ALIASES.values():
        assert (REPO / "agents" / f"{new}.md").is_file(), new


def test_routing_history_attributes_old_agent_name_to_renamed_agent() -> None:
    names: set[str] = set()
    routing_manifest._names_from_key("ui-frontend-engineer:frontend", names)
    assert names == {"ui-design-engineer", "frontend"}


def test_build_dispatch_resolves_old_agent_name() -> None:
    known = frozenset({"ui-design-engineer", "general-purpose"})
    with mock.patch.object(build_dispatch, "load_known_agents", return_value=known):
        agent, reason = build_dispatch.resolve_agent({"agent": "ui-frontend-engineer"})
    assert (agent, reason) == ("ui-design-engineer", "")
