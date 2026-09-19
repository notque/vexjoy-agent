"""jev-route.py must redact the request before it reaches the API (choke point)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("jev_route", SCRIPTS / "jev-route.py")
jev_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_route)

FAKE = "ghp_" + "x" * 36


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_call_jev_redacts_request_state(capsys):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["body"] = request.data.decode()
        return _Resp(json.dumps({"answers": {}}).encode())

    payload = {"state": f"deploy with token {FAKE} now", "model": "jev-latest", "questions": {}}
    with mock.patch.object(jev_route.urllib.request, "urlopen", fake_urlopen):
        jev_route._call_jev(payload, "k", 5)
    assert FAKE not in sent["body"]
    assert "<redacted:github:xxxx>" in sent["body"]
    assert "[jev-redact] 1 value(s)" in capsys.readouterr().err
    assert FAKE in payload["state"], "caller's payload must not be mutated"


class TestProjectContext:
    """Project facts come from marker files and reach state only when detected."""

    def test_detects_languages_frameworks_datastores(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("Flask==3.0\npeewee>=3\n", encoding="utf-8")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "18"}}', encoding="utf-8")
        context = jev_route.detect_project_context(tmp_path)
        assert context == {
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
        text = str(jev_route.detect_project_context(tmp_path))
        assert str(tmp_path) not in text
        assert "abc123" not in text

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
