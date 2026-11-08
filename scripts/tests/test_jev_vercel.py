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
    result = jev_vercel.evaluate(
        {"request": token},
        {"ok": {"type": "noul", "instructions": f"check {token}"}},
        timeout=1,
    )
    assert token not in json.dumps(seen["payload"])
    assert result["answers"]["ok"]["noul"] == 0.9


def test_gateway_subprocess_receives_allowlisted_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    seen: dict[str, object] = {}

    def run(*args, **kwargs):
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess([], 0, '{"answers":{}}', "")

    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway-test-key")
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "must-not-reach-node")
    monkeypatch.setenv("NODE_OPTIONS", "--require=/tmp/untrusted.js")

    jev_vercel.evaluate({}, {}, timeout=1)

    assert isinstance(seen["env"], dict)
    assert seen["env"]["AI_GATEWAY_API_KEY"] == "gateway-test-key"
    assert "UNRELATED_SECRET_TOKEN" not in seen["env"]
    assert "NODE_OPTIONS" not in seen["env"]


def test_gateway_retries_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    failure = subprocess.CompletedProcess([], 1, "", 'Jev Vercel gateway error: {"message":"busy","status":503}\n')
    run = Mock(side_effect=[failure, subprocess.CompletedProcess([], 0, '{"answers":{}}', "")])
    sleeps: list[float] = []
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    monkeypatch.setattr(jev_vercel, "_jitter", lambda: 1.0)
    result = jev_vercel.evaluate({}, {}, timeout=1, sleeper=sleeps.append)
    assert run.call_count == 2
    assert sleeps == [0.5]
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


class _Clock:
    """A virtual monotonic clock: a timed-out attempt and every back-off advance it."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_gateway_retries_stay_inside_the_caller_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    clock = _Clock()
    attempts: list[float] = []

    def run(*_args, **kwargs):
        attempts.append(kwargs["timeout"])
        clock.now += kwargs["timeout"]  # every attempt times out
        raise subprocess.TimeoutExpired(cmd="node", timeout=kwargs["timeout"])

    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    monkeypatch.setattr(jev_vercel.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(jev_vercel, "_jitter", lambda: 1.0)
    started = clock.now
    with pytest.raises(jev_vercel.JevGatewayError, match="timeout of 90s reached"):
        jev_vercel.evaluate({"s": 1}, {"q": {"type": "noul"}}, timeout=90, sleeper=clock.sleep)
    assert clock.now - started <= 90.0  # was 4 x 90 s plus back-off
    assert len(attempts) == 1


def test_gateway_retry_gets_only_the_time_left(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    clock = _Clock()
    attempts: list[float] = []
    busy = subprocess.CompletedProcess([], 1, "", 'Jev Vercel gateway error: {"message":"busy","status":503}\n')

    def run(*_args, **kwargs):
        attempts.append(kwargs["timeout"])
        clock.now += 3.0
        return busy if len(attempts) == 1 else subprocess.CompletedProcess([], 0, '{"answers":{}}', "")

    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    monkeypatch.setattr(jev_vercel.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(jev_vercel, "_jitter", lambda: 1.0)
    jev_vercel.evaluate({"s": 2}, {}, timeout=10, sleeper=clock.sleep)
    assert attempts == [10, pytest.approx(10 - 3.0 - 0.5)]


def test_gateway_shares_the_direct_path_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import jev_router_common

    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    monkeypatch.setenv("JEV_CACHE_TTL_S", "120")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, '{"answers":{"q":{"noul":0.8}}}', ""))
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    state, questions = {"s": "cache"}, {"q": {"type": "noul"}}
    first = jev_vercel.evaluate(state, questions, timeout=5)
    second = jev_vercel.evaluate(state, questions, timeout=5)
    assert run.call_count == 1
    assert first["answers"] == second["answers"] == {"q": {"noul": 0.8}}
    assert second["_meta"]["cached"] is True
    # The key is the direct path's: a direct call with the same request is served from it too.
    direct = {"state": state, "model": jev_router_common.JEV_MODEL, "questions": questions}
    monkeypatch.setattr(jev_router_common, "_open_url", Mock(side_effect=AssertionError("network")))
    data, _ = jev_router_common.call_jev(direct, "k", 5)
    assert data["answers"] == {"q": {"noul": 0.8}}


def test_gateway_does_not_cache_an_invalid_answer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = tmp_path / "gateway.mjs"
    bridge.write_text("// bridge")
    monkeypatch.setenv("JEV_CACHE_TTL_S", "120")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, '{"answers":{"q":{"noul":7}}}', ""))
    monkeypatch.setattr(jev_vercel, "_BRIDGE", bridge)
    monkeypatch.setattr(jev_vercel.subprocess, "run", run)
    for _ in range(2):
        jev_vercel.evaluate({"s": "bad"}, {"q": {"type": "noul"}}, timeout=5)
    assert run.call_count == 2
