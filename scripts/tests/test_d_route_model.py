"""The eval stand-in for the /d session (scripts/d_route_model.py). No model or Jev calls."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import d_route_model as drm

ENTRIES = [
    {"name": "python-general-engineer", "type": "agent"},
    {"name": "workflow", "type": "skill"},
    {"name": "testing", "type": "skill"},
]


def test_system_text_holds_the_skill_the_rules_and_the_manifest() -> None:
    with mock.patch.object(drm, "manifest_for", return_value="AGENTS: a\nSKILLS: b\nPIPELINES: c"):
        text = drm.system_text("fix it")
    assert "# /d — Jev Router" in text
    assert "SECTION-INTEGRITY RULE" in text
    assert "AGENTS: a" in text
    assert text.index("SECTION-INTEGRITY RULE") < text.index("AGENTS: a")


def test_prompt_carries_the_request_and_the_prepared_result() -> None:
    prompt = drm.D_PROMPT % ("fix it", json.dumps({"forced": None}))
    assert "fix it" in prompt and '"forced": null' in prompt


def _pick(decision: dict | None, tmp_path: Path) -> dict:
    spec = importlib.util.spec_from_file_location("jev_route_for_d_model_test", SCRIPTS / "jev-route.py")
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    prepared = {"forced": None, "stack": [], "domain_scores": {"testing": 0.9}, "signals": {}}
    with (
        mock.patch.object(drm, "system_file", return_value=tmp_path / "sys.md"),
        mock.patch.object(drm, "call_model", return_value=(decision, 0.05, "raw text", {"output_tokens": 9})),
        mock.patch.object(drm, "_load_jev_route", return_value=real),
        mock.patch.object(real, "_load_manifest_entries", return_value=ENTRIES),
    ):
        return drm.pick_route("fix it", model="sonnet", scratch=tmp_path, prepared=prepared)


def test_pick_route_finalizes_the_model_decision(tmp_path: Path) -> None:
    route = _pick({"agent": "python-general-engineer", "skill": "workflow", "reasoning": "r"}, tmp_path)
    assert (route["agent"], route["skill"], route["attach"]) == ("python-general-engineer", "workflow", ["testing"])
    assert route["cost_usd"] == 0.05
    assert route["decision"]["skill"] == "workflow"


def test_a_reply_that_is_not_json_still_yields_a_route(tmp_path: Path) -> None:
    route = _pick(None, tmp_path)
    assert route["skill"] == "workflow"  # the skill-greediness fallback
    assert route["decision"] is None
    assert route["decision_text"] == "raw text"
