"""Contracts for the /d router fixes: shortlist backfill, agent table, skill-fit guard, model pick.

Every Jev call is mocked; no network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("jev_route_dfix", SCRIPTS / "jev-route.py")
jr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jr)

AGENTS = {
    "alpha-agent",
    "beta-agent",
    "general-purpose",
    "golang-general-engineer",
    "swift-general-engineer",
    "project-coordinator-engineer",
    "python-general-engineer",
}
SKILLS = {"testing", "programming", "debugging", "pr-workflow", "workflow", "accounts"}


def _stage1_data(agent_probs: dict, skill_probs: dict) -> dict:
    return {
        "answers": {
            "agent": {"probabilities": agent_probs},
            "skill": {"probabilities": skill_probs},
            "pipeline": {"probabilities": {"none": 1.0}},
            "needs_skill": {"noul": 0.9},
            "needs_pipeline": {"noul": 0.1},
            "prose_suffices": {"noul": 0.1},
        }
    }


class TestDomainAgentTable:
    @pytest.mark.parametrize(
        ("request_text", "agent"),
        [
            ("write XCTest cases for this Swift view model", "swift-general-engineer"),
            ("debug the goroutine leak", "golang-general-engineer"),
            ("fix the typo in main.go", "golang-general-engineer"),
            ("do finance phases zero and one", "project-coordinator-engineer"),
            ("add a pytest fixture", "python-general-engineer"),
        ],
    )
    def test_domain_signal_names_agent(self, request_text: str, agent: str) -> None:
        assert agent in jr._domain_agent_hits(request_text)

    @pytest.mark.parametrize("request_text", ["go ahead and fix the bug", "Go ahead and merge it", "save my work"])
    def test_plain_go_is_not_a_language_signal(self, request_text: str) -> None:
        assert "golang-general-engineer" not in jr._domain_agent_hits(request_text)


class TestShortlistBackfill:
    def test_zero_probability_ties_are_not_alphabetical_filler(self) -> None:
        probs = {name: 0.0 for name in AGENTS} | {"python-general-engineer": 0.9}
        got = jr._backfilled_shortlist(probs, AGENTS, 6, [], "refactor this module", {})
        assert got == ["python-general-engineer"]

    def test_extras_follow_ranked_names_and_respect_the_cap(self) -> None:
        probs = {name: 0.0 for name in AGENTS} | {"python-general-engineer": 0.6, "general-purpose": 0.4}
        got = jr._backfilled_shortlist(
            probs, AGENTS, 3, ["swift-general-engineer", "golang-general-engineer"], "swift view model", {}
        )
        assert got == ["python-general-engineer", "general-purpose", "swift-general-engineer"]

    def test_lexical_overlap_of_two_words_backfills(self) -> None:
        probs = {name: 0.0 for name in AGENTS} | {"python-general-engineer": 1.0}
        criteria = {"alpha-agent": "dashboards alerting metrics", "beta-agent": "unrelated thing"}
        got = jr._backfilled_shortlist(probs, AGENTS, 6, [], "build metrics dashboards for alerting", criteria)
        assert got == ["python-general-engineer", "alpha-agent"]

    def test_all_zero_probabilities_still_return_candidates(self) -> None:
        got = jr._backfilled_shortlist({name: 0.0 for name in AGENTS}, AGENTS, 2, [], "x", {})
        assert len(got) == 2

    def test_stage1_agent_table_and_domain_skill_reach_stage2(self) -> None:
        agent_probs = {name: 0.0 for name in AGENTS} | {"general-purpose": 0.7, "python-general-engineer": 0.3}
        skill_probs = {name: 0.0 for name in SKILLS} | {"testing": 1.0}
        parsed = jr._parse_stage1(
            _stage1_data(agent_probs, skill_probs),
            AGENTS,
            SKILLS,
            {"none"},
            6,
            "write XCTest cases for this Swift view model",
        )
        assert parsed["agent_shortlist"][:2] == ["general-purpose", "python-general-engineer"]
        assert "swift-general-engineer" in parsed["agent_shortlist"]
        assert "alpha-agent" not in parsed["agent_shortlist"]
        assert parsed["skill_shortlist"] == ["testing", "programming"]


def _stage2_data(skill_fit: float, *, model: bool = True) -> dict:
    answers: dict = {
        "agent": {"choice": "python-general-engineer"},
        "agent_fit__python_general_engineer": {"noul": 0.8},
        "agent_fit__general_purpose": {"noul": 0.2},
        "skill": {"choice": "pr-workflow"},
        "skill_fit__pr_workflow": {"noul": skill_fit},
    }
    for key in jr.NOUL_SIGNAL_KEYS:
        answers[key] = {"noul": 0.0}
    if model:
        answers["model_task"] = {"choice": "locate", "probabilities": {"locate": 0.9, "unmatched": 0.1}}
        answers["high_risk"] = {"noul": 0.1}
    return {"answers": answers}


def _parse2(data: dict) -> dict:
    return jr._parse_stage2(
        data,
        ["python-general-engineer", "general-purpose"],
        ["pr-workflow"],
        None,
        [],
        AGENTS,
        SKILLS,
        {"none"},
        jr.DEFAULT_FITS_THRESHOLD,
    )


class TestSkillFitGuard:
    def test_skill_fit_under_floor_defers_to_do(self) -> None:
        decision = _parse2(_stage2_data(0.02))
        assert decision["fallback"] is True
        assert decision["source"] == "low-fit-skill"
        assert (decision["agent"], decision["skill"], decision["pipeline"]) == (None, None, None)
        assert decision["rejected_pick"]["skill"] == "pr-workflow"
        assert "0.02" in decision["fallback_reason"]

    def test_skill_fit_at_floor_is_kept(self) -> None:
        decision = _parse2(_stage2_data(jr.SKILL_FIT_FLOOR))
        assert decision["fallback"] is False
        assert decision["skill"] == "pr-workflow"

    def test_decision_carries_agent_fits_and_model_probabilities(self) -> None:
        decision = _parse2(_stage2_data(0.7))
        assert decision["agent_fits"] == {"python-general-engineer": 0.8, "general-purpose": 0.2}
        assert decision["model_probabilities"]["model_task"]["locate"] == 0.9
        assert decision["model_probabilities"]["high_risk"] == 0.1

    def test_missing_model_answers_leave_probabilities_empty(self) -> None:
        assert _parse2(_stage2_data(0.7, model=False))["model_probabilities"] is None


def _result(task_probs: dict | None, high_risk: float | None, skill: str = "debugging", pipeline: str | None = None):
    probs = {"model_task": task_probs, "high_risk": high_risk} if task_probs else None
    return {"skill": skill, "pipeline": pipeline, "model_probabilities": probs}


class TestModelPick:
    @pytest.mark.parametrize(
        ("task", "model", "policy"),
        [
            ("locate", "haiku", "low-risk"),
            ("mech_edit", "haiku", "low-risk"),
            ("review", "haiku", "low-risk"),
            ("deep_debug", "sonnet", "standard"),
            ("ts_feature", "sonnet", "standard"),
            ("long_lane", "sonnet", "standard"),
            ("unmatched", "sonnet", "standard"),
        ],
    )
    def test_confident_task_maps_to_its_tier(self, task: str, model: str, policy: str) -> None:
        pick = jr._model_pick(_result({task: 0.9, "unmatched": 0.1}, 0.1))
        assert (pick["model_task"], pick["model"], pick["model_policy"]) == (task, model, policy)

    def test_split_task_falls_to_sonnet(self) -> None:
        pick = jr._model_pick(_result({"locate": 0.55, "deep_debug": 0.45}, 0.1))
        assert (pick["model"], pick["model_policy"]) == ("sonnet", "standard")

    def test_high_risk_noul_forces_opus(self) -> None:
        pick = jr._model_pick(_result({"locate": 0.95, "unmatched": 0.05}, 0.6))
        assert (pick["model"], pick["model_policy"]) == ("opus", "high-risk")

    @pytest.mark.parametrize("skill", ["pr-workflow", "security", "deploy"])
    def test_safety_skill_forces_opus_even_when_task_is_cheap(self, skill: str) -> None:
        pick = jr._model_pick(_result({"locate": 0.95, "unmatched": 0.05}, 0.0, skill=skill))
        assert pick["model"] == "opus"

    def test_safety_pipeline_forces_opus(self) -> None:
        assert (
            jr._model_pick(_result({"review": 0.9, "unmatched": 0.1}, 0.0, pipeline="pr-pipeline"))["model"] == "opus"
        )

    def test_no_evidence_defaults_to_sonnet(self) -> None:
        pick = jr._model_pick(_result(None, None))
        assert (pick["model"], pick["model_task"]) == ("sonnet", None)


class TestAgentFallbacks:
    def test_general_purpose_yields_to_a_fitting_domain_agent(self) -> None:
        result = {"agent_fits": {"general-purpose": 0.36, "python-general-engineer": 0.62}}
        assert jr._demote_general_purpose(result) == "python-general-engineer"

    def test_general_purpose_stays_when_no_agent_clears_the_fit_floor(self) -> None:
        result = {"agent_fits": {"general-purpose": 0.43, "golang-general-engineer": 0.3}}
        assert jr._demote_general_purpose(result) is None

    def test_general_purpose_stays_when_it_fits_better(self) -> None:
        result = {"agent_fits": {"general-purpose": 0.9, "golang-general-engineer": 0.6}}
        assert jr._demote_general_purpose(result) is None

    def test_default_agent_prefers_request_domain_over_skill_owner(self) -> None:
        assert jr._default_agent({"skill": "testing"}, "write XCTest cases for Swift") == "swift-general-engineer"

    def test_default_agent_without_domain_uses_skill_owner(self) -> None:
        assert jr._default_agent({"skill": "testing"}, "check that it works") == "testing-automation-engineer"


def _entries() -> list[dict]:
    rows = [{"type": "agent", "name": n, "description": f"{n} agent"} for n in sorted(AGENTS - {"general-purpose"})]
    rows += [{"type": "skill", "name": n, "description": f"{n} skill"} for n in sorted(SKILLS)]
    rows.append({"type": "pipeline", "name": "none-pipe", "description": "pipe"})
    return rows


NO_ROUTE = {"matched": False, "agent": None, "skill": None, "pipeline": None, "confidence": "low", "stack": []}


class TestRouteEndToEnd:
    def _run(self, request: str, stage2: dict) -> tuple[dict, list[dict]]:
        sent: list[dict] = []
        stage1 = _stage1_data(
            {"general-purpose": 0.6, "python-general-engineer": 0.4} | {n: 0.0 for n in AGENTS},
            {"debugging": 0.9, "testing": 0.1} | {n: 0.0 for n in SKILLS},
        )
        stage1["answers"]["agent"]["probabilities"] = {"general-purpose": 0.6, "python-general-engineer": 0.4}
        stage1["answers"]["skill"]["probabilities"] = {"debugging": 0.9, "testing": 0.1}
        replies = iter([(stage1, 1.0), (stage2, 1.0)])

        def fake_call(payload: dict, timeout: float) -> tuple[dict, float]:
            sent.append(payload)
            return next(replies)

        with (
            mock.patch.object(jr.jev_transport, "available", return_value=(True, "")),
            mock.patch.object(jr, "_load_manifest_entries", return_value=_entries()),
            mock.patch.object(jr, "_run_pre_route", return_value=NO_ROUTE),
            mock.patch.object(jr, "_call_jev", side_effect=fake_call),
        ):
            result = jr.route(request, 0.3, 0.3, 5.0)
        return result, sent

    def test_stage2_request_carries_the_model_questions_in_one_round_trip(self) -> None:
        stage2 = {
            "answers": {
                "agent": {"choice": "general-purpose"},
                "agent_fit__general_purpose": {"noul": 0.3},
                "agent_fit__python_general_engineer": {"noul": 0.7},
                "skill": {"choice": "debugging"},
                "skill_fit__debugging": {"noul": 0.8},
                "model_task": {"choice": "deep_debug", "probabilities": {"deep_debug": 0.9, "locate": 0.1}},
                "high_risk": {"noul": 0.1},
            }
        }
        for key in jr.NOUL_SIGNAL_KEYS:
            stage2["answers"][key] = {"noul": 0.0}
        result, sent = self._run("fix the parser bugs", stage2)
        assert len(sent) == 2
        questions = sent[1]["questions"]
        assert questions["model_task"]["type"] == "choice"
        assert set(questions["model_task"]["criteria"]) == set(jr.MODEL_TASK_TIER)
        assert questions["high_risk"]["type"] == "noul"
        assert result["agent"] == "python-general-engineer"
        assert result["agent_source"] == "fit-demote"
        assert (result["model_task"], result["model"], result["model_policy"]) == ("deep_debug", "sonnet", "standard")
        assert result["model_probabilities"]["high_risk"] == 0.1

    def test_low_fit_skill_pick_returns_a_fallback_for_do(self) -> None:
        stage2 = {
            "answers": {
                "agent": {"choice": "general-purpose"},
                "agent_fit__general_purpose": {"noul": 0.5},
                "skill": {"choice": "debugging"},
                "skill_fit__debugging": {"noul": 0.03},
            }
        }
        for key in jr.NOUL_SIGNAL_KEYS:
            stage2["answers"][key] = {"noul": 0.0}
        result, _ = self._run("go ahead and fix the bug", stage2)
        assert result["fallback"] is True
        assert result["source"] == "low-fit-skill"
        assert (result["agent"], result["skill"], result["pipeline"]) == (None, None, None)
        assert result["model"] is None

    def test_request_domain_signal_beats_a_fitting_but_unrelated_agent(self) -> None:
        stage2 = {
            "answers": {
                "agent": {"choice": "general-purpose"},
                "agent_fit__general_purpose": {"noul": 0.2},
                "agent_fit__python_general_engineer": {"noul": 0.56},
                "skill": {"choice": "debugging"},
                "skill_fit__debugging": {"noul": 0.8},
            }
        }
        for key in jr.NOUL_SIGNAL_KEYS:
            stage2["answers"][key] = {"noul": 0.0}
        result, _ = self._run("do finance phases zero and one", stage2)
        assert (result["agent"], result["agent_source"]) == ("project-coordinator-engineer", "domain-table")
        assert "_agent_names" not in result
        assert result["model"] == "sonnet"
        assert result["model_task"] is None
