from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_transport


def test_import_loads_only_the_jev_keys_from_home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A synthetic ~/.env under a temp HOME: only the keys the transport reads reach the process."""
    import importlib.util
    import os

    pytest.importorskip("dotenv")
    gateway, unrelated = "gw-" + "a" * 12, "un-" + "b" * 12
    (tmp_path / ".env").write_text(
        f"AI_GATEWAY_API_KEY={gateway}\nUNRELATED_SERVICE_TOKEN={unrelated}\nJEV_TRANSPORT=vercel\n",
        encoding="utf-8",
    )
    # A private copy of the environment, so the import under test cannot leak into other tests.
    environ = {k: v for k, v in os.environ.items() if k not in ("JEV_TRANSPORT", "UNRELATED_SERVICE_TOKEN")}
    environ["HOME"] = str(tmp_path)
    monkeypatch.setattr(os, "environ", environ)
    spec = importlib.util.spec_from_file_location("jev_transport_import_probe", SCRIPTS / "jev_transport.py")
    assert spec and spec.loader
    spec.loader.exec_module(importlib.util.module_from_spec(spec))  # runs the import-time load
    seen = {k: environ.get(k) for k in ("AI_GATEWAY_API_KEY", "UNRELATED_SERVICE_TOKEN", "JEV_TRANSPORT")}
    seen["TYPESAFE_API_KEY"] = environ.get("TYPESAFE_API_KEY")
    assert seen == {
        "AI_GATEWAY_API_KEY": gateway,
        "UNRELATED_SERVICE_TOKEN": None,
        "JEV_TRANSPORT": "vercel",
        "TYPESAFE_API_KEY": None,
    }


def test_exported_value_wins_over_home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("dotenv")
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TYPESAFE_API_KEY", "exported")
    jev_transport._load_env_file_keys()
    assert jev_transport.os.environ["TYPESAFE_API_KEY"] == "exported"


def test_key_only_switch_still_loads_from_home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """JEV_KEY_ONLY=1 in ~/.env keeps working for cron and standalone runs."""
    pytest.importorskip("dotenv")
    (tmp_path / ".env").write_text("JEV_KEY_ONLY=1\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("JEV_KEY_ONLY", raising=False)
    jev_transport._load_env_file_keys()
    assert jev_transport.os.environ.get("JEV_KEY_ONLY") == "1"


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
    assert seen["payload"] == {"state": state, "model": "jev-1.14.0", "questions": questions}
    assert result["_meta"]["transport"] == jev_transport.DIRECT
