from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_transport


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("JEV_TRANSPORT", "AI_GATEWAY_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_auto_prefers_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway")
    monkeypatch.setenv("TYPESAFE_API_KEY", "direct")
    assert jev_transport.select()[0] == jev_transport.VERCEL


def test_auto_uses_direct_when_gateway_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("TYPESAFE_API_KEY", "direct")
    assert jev_transport.select()[0] == jev_transport.DIRECT


@pytest.mark.parametrize(
    ("choice", "key", "expected"),
    [("vercel", "AI_GATEWAY_API_KEY", jev_transport.VERCEL), ("direct", "TYPESAFE_API_KEY", jev_transport.DIRECT)],
)
def test_explicit_transport_selection(monkeypatch: pytest.MonkeyPatch, choice: str, key: str, expected: str) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("JEV_TRANSPORT", choice)
    monkeypatch.setenv(key, "configured")
    assert jev_transport.select()[0] == expected


def test_explicit_transport_never_silently_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")
    monkeypatch.setenv("TYPESAFE_API_KEY", "direct")
    selected, reason = jev_transport.select()
    assert selected is None
    assert "AI_GATEWAY_API_KEY is unset" in reason


def test_direct_transport_sends_same_state_and_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("JEV_TRANSPORT", "direct")
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret")
    seen: dict[str, object] = {}

    def call(payload, api_key, timeout, *, script_name):
        seen.update(payload=payload, api_key=api_key, timeout=timeout, script_name=script_name)
        return {"answers": {"ok": {"type": "noul", "noul": 0.9}}}, 12.0

    monkeypatch.setattr(jev_transport.jev_router_common, "call_jev", call)
    state = {"request": "test"}
    questions = {"ok": {"type": "noul", "instructions": "Is this a test?"}}
    result = jev_transport.evaluate(state, questions, timeout=3)
    assert seen["payload"] == {"state": state, "model": "jev-latest", "questions": questions}
    assert result["_meta"]["transport"] == jev_transport.DIRECT
