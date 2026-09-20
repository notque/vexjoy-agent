from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import jev_vercel


def test_gateway_availability_uses_only_gateway_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    assert jev_vercel.available()[0] is False
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test")
    assert jev_vercel.available()[0] is True


def test_gateway_redacts_before_node_receives_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    seen: dict[str, object] = {}

    def run(*args, **kwargs):
        seen["payload"] = json.loads(kwargs["input"])
        return subprocess.CompletedProcess([], 0, '{"answers":{"ok":{"noul":0.9}}}', "")

    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    token = "ghp_" + "x" * 36
    result = jev_vercel.evaluate({"request": token}, {"ok": {"type": "noul"}}, timeout=1)
    assert token not in json.dumps(seen["payload"])
    assert result["answers"]["ok"]["noul"] == 0.9


def test_gateway_retries_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    failure = subprocess.CompletedProcess([], 1, "", 'Jev Vercel gateway error: {"message":"busy","status":503}\n')
    run = Mock(side_effect=[failure, subprocess.CompletedProcess([], 0, '{"answers":{}}', "")])
    sleeps: list[float] = []
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    result = jev_vercel.evaluate({}, {}, timeout=1, sleeper=sleeps.append)
    assert run.call_count == 2
    assert sleeps == [0.25]
    assert result["_meta"]["retry"]["retries"] == 1


def test_gateway_retries_provider_timeout_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    failure = subprocess.CompletedProcess(
        [], 1, "", 'Jev Vercel gateway error: {"message":"timed out","kind":"timeout"}\n'
    )
    run = Mock(side_effect=[failure, subprocess.CompletedProcess([], 0, '{"answers":{}}', "")])
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    result = jev_vercel.evaluate({}, {}, timeout=1, sleeper=lambda _: None)
    assert run.call_count == 2
    assert result["_meta"]["retry"]["retries"] == 1


@pytest.mark.parametrize("status", [429, 503, 529])
def test_gateway_retries_each_documented_transient_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status: int
) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    failure = subprocess.CompletedProcess(
        [], 1, "", f'Jev Vercel gateway error: {{"message":"failed","status":{status}}}\n'
    )
    run = Mock(side_effect=[failure, subprocess.CompletedProcess([], 0, '{"answers":{}}', "")])
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    result = jev_vercel.evaluate({}, {}, timeout=1, sleeper=lambda _: None)
    assert run.call_count == 2
    assert result["_meta"]["retry"]["attempts"] == 2
