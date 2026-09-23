"""Integration contracts for route transport, project context, and shortlists."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("jev_route", SCRIPTS / "jev-route.py")
jev_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_route)
FAKE = "ghp_" + "x" * 36


def test_call_jev_uses_vercel_gateway_and_never_passes_a_direct_api_key():
    payload = {"state": f"deploy with token {FAKE} now", "model": "typesafe-ai/jev", "questions": {}}
    sent: dict[str, object] = {}

    def evaluate(state, questions, *, timeout):
        sent.update({"state": state, "questions": questions, "timeout": timeout})
        return {"answers": {}}

    with mock.patch.object(jev_route.jev_transport, "evaluate_packed", side_effect=evaluate):
        result, _ = jev_route._call_jev(payload, 5)
    assert result == {"answers": {}}
    assert sent["state"] == payload["state"]
    assert sent["questions"] == {}
    assert "api_key" not in sent


def test_call_jev_redacts_before_the_vercel_bridge(monkeypatch, capsys):
    payload = {"state": f"deploy with token {FAKE} now", "model": "typesafe-ai/jev", "questions": {}}
    sent: dict[str, object] = {}

    def run(command, *, input, text, capture_output, timeout, check, env):
        sent.update(command=command, input=input, timeout=timeout, env=env)
        return subprocess.CompletedProcess(command, 0, json.dumps({"answers": {}}), "")

    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway-test-key")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with mock.patch.object(jev_route.jev_transport.jev_vercel.subprocess, "run", side_effect=run):
        result, _ = jev_route._call_jev(payload, 5)
    assert result["answers"] == {}
    assert FAKE not in str(sent["input"])
    assert "<redacted:github:xxxx>" in str(sent["input"])
    assert "gateway-test-key" not in str(sent["input"])
    assert FAKE in payload["state"]
    assert "[jev-redact] 1 value(s)" in capsys.readouterr().err


class TestProjectContext:
    def test_detects_languages_frameworks_datastores(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("Flask==3.0\npeewee>=3\n", encoding="utf-8")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "18"}}', encoding="utf-8")
        assert jev_route.detect_project_context(tmp_path) == {
            "languages": ["python", "javascript"],
            "frameworks": ["flask", "react"],
            "datastores": ["peewee"],
        }

    def test_returns_none_when_nothing_detected(self, tmp_path):
        assert jev_route.detect_project_context(tmp_path) is None
        assert jev_route.detect_project_context(None) is None
        assert jev_route.detect_project_context(tmp_path / "missing") is None

    def test_context_never_carries_paths_or_file_contents(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\nSECRET_TOKEN=abc123\n", encoding="utf-8")
        context = str(jev_route.detect_project_context(tmp_path))
        assert str(tmp_path) not in context
        assert "abc123" not in context

    def test_bare_request_state_is_unchanged_without_project(self):
        payload = jev_route._build_stage1_payload("fix it", {"a": "x"}, {"s": "y"}, {"none": "z"})
        assert payload["state"] == "fix it"
        assert jev_route.PROJECT_CONTEXT_INSTRUCTIONS not in payload["questions"]["agent"]["instructions"]

    def test_project_facts_go_in_state_and_agent_instructions(self):
        project = {"languages": ["python"]}
        payload = jev_route._build_stage1_payload("fix it", {"a": "x"}, {"s": "y"}, {"none": "z"}, project)
        assert payload["state"] == {"request": "fix it", "project": project}
        assert jev_route.PROJECT_CONTEXT_INSTRUCTIONS in payload["questions"]["agent"]["instructions"]

    def test_shortlist_size_is_a_parameter(self):
        probs = {f"a{i}": 1.0 - i / 10 for i in range(8)}
        data = {
            "answers": {
                "agent": {"probabilities": probs},
                "skill": {"probabilities": probs},
                "pipeline": {"probabilities": {}},
                "needs_skill": {"noul": 0.9},
                "needs_pipeline": {"noul": 0.1},
                "prose_suffices": {"noul": 0.1},
            }
        }
        names = set(probs)
        assert (
            len(jev_route._parse_stage1(data, names, names, set())["agent_shortlist"]) == jev_route.STAGE1_SHORTLIST_N
        )
        assert jev_route._parse_stage1(data, names, names, set(), 4)["skill_shortlist"] == [f"a{i}" for i in range(4)]
