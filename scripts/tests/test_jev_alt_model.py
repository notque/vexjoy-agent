"""Tests for the single named alt model behind the two scoped Jev fallback/second-opinion modes.

Covers: backend selection (api/claude-cli/auto), reply parsing, the CLI and API
answer paths, and the end-to-end `answer()` contract (complete answers only,
always tagged `is_jev: False`, never a fabricated or partial answer).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_alt_model

NOUL_Q = {"ok": {"type": "noul", "instructions": "Is this a test?"}}


def _ok_reply(text: str = '{"answers": {"ok": {"type": "noul", "noul": 0.6}}}') -> str:
    return text


# ---------------------------------------------------------------------------
# available()
# ---------------------------------------------------------------------------


def test_available_api_backend_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "api")
    monkeypatch.delenv("JEV_ALT_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert jev_alt_model.available() == (False, "no alt-model API key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    ok, reason = jev_alt_model.available()
    assert ok and "set" in reason


def test_available_claude_cli_backend_checks_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _name: None)
    assert jev_alt_model.available() == (False, "claude CLI not on PATH")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _name: "/usr/bin/claude")
    assert jev_alt_model.available() == (True, "claude CLI on PATH")


def test_available_auto_prefers_api_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    ok, reason = jev_alt_model.available()
    assert ok and "set" in reason


def test_available_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "carrier-pigeon")
    ok, reason = jev_alt_model.available()
    assert ok is False
    assert "invalid" in reason


# ---------------------------------------------------------------------------
# _parse_reply
# ---------------------------------------------------------------------------


def test_parse_reply_plain_json() -> None:
    assert jev_alt_model._parse_reply('{"answers": {"ok": {"noul": 0.6}}}') == {"answers": {"ok": {"noul": 0.6}}}


def test_parse_reply_fenced_json() -> None:
    text = '```json\n{"answers": {"ok": {"noul": 0.6}}}\n```'
    assert jev_alt_model._parse_reply(text) == {"answers": {"ok": {"noul": 0.6}}}


def test_parse_reply_prose_wrapped_json() -> None:
    text = 'Sure, here you go: {"answers": {"ok": {"noul": 0.6}}} hope that helps'
    assert jev_alt_model._parse_reply(text) == {"answers": {"ok": {"noul": 0.6}}}


def test_parse_reply_unparseable() -> None:
    assert jev_alt_model._parse_reply("no JSON here") is None
    assert jev_alt_model._parse_reply("{not valid json}") is None


# ---------------------------------------------------------------------------
# answer() via the claude-cli backend
# ---------------------------------------------------------------------------


def test_answer_cli_backend_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))

        class R:
            returncode = 0
            stdout = _ok_reply()

        return R()

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    result = jev_alt_model.answer({"x": 1}, NOUL_Q, timeout=5)
    assert result["answers"] == {"ok": {"type": "noul", "noul": 0.6}}
    assert result["_meta"] == {"is_jev": False, "source": "alt-model", "backend": "claude-cli"}
    cmd, kw = calls[0]
    assert cmd[:2] == ["claude", "-p"]
    assert "--no-session-persistence" in cmd
    assert kw["cwd"] == jev_alt_model.tempfile.gettempdir()


def test_answer_cli_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: None)
    with pytest.raises(jev_alt_model.AltModelError) as exc_info:
        jev_alt_model.answer({}, NOUL_Q, timeout=5)
    assert exc_info.value.reason == "claude-cli-missing"


def test_answer_cli_nonzero_exit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")

    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""

        return R()

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    with pytest.raises(jev_alt_model.AltModelError, match="claude-cli-exit-1"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


def test_answer_cli_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")

    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=5)

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    with pytest.raises(jev_alt_model.AltModelError, match="claude-cli-error"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


# ---------------------------------------------------------------------------
# answer() via the api backend
# ---------------------------------------------------------------------------


def test_answer_api_backend_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "api")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            import json

            return json.dumps({"content": [{"type": "text", "text": _ok_reply()}]}).encode()

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(jev_alt_model._NO_REDIRECT_OPENER, "open", fake_open)
    result = jev_alt_model.answer({"x": 1}, NOUL_Q, timeout=7)
    assert result["answers"] == {"ok": {"type": "noul", "noul": 0.6}}
    assert result["_meta"]["backend"] == "api"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["timeout"] == 7
    assert any(k.lower() == "x-api-key" for k in seen["headers"])


def test_answer_api_backend_no_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "api")
    monkeypatch.delenv("JEV_ALT_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(jev_alt_model.AltModelError, match="no-alt-model-key"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


def test_answer_api_backend_insecure_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "api")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BASE_URL", "http://evil.example.com")
    with pytest.raises(jev_alt_model.AltModelError, match="alt-model-insecure-url"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


def test_answer_auto_prefers_cli_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "auto")
    monkeypatch.delenv("JEV_ALT_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: None)
    with pytest.raises(jev_alt_model.AltModelError, match="claude-cli-missing"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


# ---------------------------------------------------------------------------
# answer() contract: complete, valid, never fabricated
# ---------------------------------------------------------------------------


def test_answer_rejects_incomplete_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")
    two_questions = {**NOUL_Q, "other": {"type": "noul", "instructions": "Another?"}}

    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            # Only answers "ok", not "other": the alt model dropped a question.
            stdout = '{"answers": {"ok": {"type": "noul", "noul": 0.5}}}'

        return R()

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    with pytest.raises(jev_alt_model.AltModelError, match="alt-model-incomplete-answers"):
        jev_alt_model.answer({}, two_questions, timeout=5)


def test_answer_rejects_invalid_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")

    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            # noul out of [0, 1]: validate_jev_response must catch this.
            stdout = '{"answers": {"ok": {"type": "noul", "noul": 7.0}}}'

        return R()

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    with pytest.raises(jev_alt_model.AltModelError, match="alt-model-invalid-shape"):
        jev_alt_model.answer({}, NOUL_Q, timeout=5)


def test_answer_always_tags_not_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jev_alt_model, "ALT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(jev_alt_model.shutil, "which", lambda _n: "/usr/bin/claude")

    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            stdout = _ok_reply()

        return R()

    monkeypatch.setattr(jev_alt_model.subprocess, "run", fake_run)
    result = jev_alt_model.answer({}, NOUL_Q, timeout=5)
    assert result["_meta"]["is_jev"] is False
    assert result["_meta"]["source"] == "alt-model"
