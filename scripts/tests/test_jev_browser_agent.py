"""Focused security and replay tests for scripts/jev-browser-agent.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


agent = _load("jev-browser-agent")


class _StubDriver:
    def __init__(self, snap: dict):
        self.snap = snap
        self.calls: list[dict] = []

    def call(self, cmd: str, **kw) -> dict:
        self.calls.append({"cmd": cmd, **kw})
        if cmd == "open":
            return {"ok": True}
        if cmd == "observe":
            return {"ok": True, "result": dict(self.snap)}
        if cmd == "act":
            return {"ok": True}
        return {"ok": True}

    def close(self) -> None:
        pass


class TestHostAllowedSecurity:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "file://localhost/etc/passwd",
            "javascript:alert(1)",
            "data:text/html,<h1>x</h1>",
            "ftp://127.0.0.1/file",
        ],
    )
    def test_blocks_non_http_schemes_even_with_allow_remote(self, url):
        assert agent._host_allowed(url, {"example.com"}, allow_remote=True) is False
        assert agent._host_allowed(url, {"example.com"}, allow_remote=False) is False

    def test_strips_empty_and_dot_allow_hosts(self):
        assert agent._host_allowed("https://evil.example/", {"", ".", "   "}, allow_remote=False) is False
        assert agent._host_allowed("https://sub.example.com/", {".example.com", ""}, allow_remote=False) is True
        assert agent._host_allowed("http://127.0.0.1:8000/", set(), allow_remote=False) is True


class TestSubprocessHardening:
    def test_driver_closes_stderr_on_popen_error(self):
        closed = {"flag": False}

        class _FakeTmp:
            def close(self):
                closed["flag"] = True

        with (
            mock.patch.object(agent.tempfile, "TemporaryFile", return_value=_FakeTmp()),
            mock.patch.object(agent.subprocess, "Popen", side_effect=OSError("node missing")),
            pytest.raises(OSError, match="node missing"),
        ):
            agent.Driver()
        assert closed["flag"] is True

    def test_generate_text_cli_passes_utf8_encoding(self):
        captured: dict = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout='{"text": "hello"}\n', stderr="")

        with (
            mock.patch.object(agent.shutil, "which", return_value="/usr/bin/claude"),
            mock.patch.object(agent.subprocess, "run", side_effect=fake_run),
        ):
            text, src = agent.generate_text_cli(
                "goal", {"label": "Name"}, {"url": "http://127.0.0.1/", "title": "T", "text": ""}, []
            )
        assert src == "claude-cli"
        assert text == "hello"
        assert captured.get("encoding") == "utf-8"
        assert captured.get("errors") == "replace"


class TestRunnerUpAndReplay:
    def _base_snap(self) -> dict:
        return {
            "url": "http://127.0.0.1:8000/",
            "title": "App",
            "text": "hello",
            "page_key": "pk1",
            "marker": "m1",
            "guards": {"1": "g1", "2": "g2"},
            "elements": [
                {"index": "1", "role": "button", "label": "Primary", "operations": ["CLICK"]},
                {"index": "2", "role": "button", "label": "Secondary", "operations": ["CLICK"]},
            ],
            "actions": [
                {"id": "e1:click", "kind": "click", "index": "1", "label": "Primary"},
                {"id": "e2:click", "kind": "click", "index": "2", "label": "Secondary"},
            ],
        }

    def test_runner_up_replay_triggers_between_low_and_uncertain_confidence(self, monkeypatch):
        import jev_router_common

        monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (False, "offline"))
        drv = _StubDriver(self._base_snap())
        steps = iter(
            [
                {
                    "operation": "CLICK",
                    "target": "1",
                    "confidence": 0.55,
                    "target_probabilities": {"1": 0.55, "2": 0.40},
                    "source": "test",
                },
                {"operation": "DONE", "target": None, "confidence": 0.9, "source": "test"},
            ]
        )
        res = agent.run(
            "http://127.0.0.1:8000/",
            "click secondary",
            decide_fn=lambda _req: next(steps),
            verify_fn=lambda _req: {"goal_met": True, "source": "test"},
            driver=drv,
        )
        assert res["status"] == "done"
        acts = [c["action"]["id"] for c in drv.calls if c["cmd"] == "act"]
        assert acts == ["e1:click", "e2:click"]

    def test_runner_up_enforces_blocked_link(self, monkeypatch):
        import jev_router_common

        monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (False, "offline"))
        snap = self._base_snap()
        snap["elements"][1] = {
            "index": "2",
            "role": "link",
            "label": "External",
            "external": True,
            "host": "evil.example",
            "operations": ["CLICK"],
        }
        drv = _StubDriver(snap)
        steps = iter(
            [
                {
                    "operation": "CLICK",
                    "target": "1",
                    "confidence": 0.55,
                    "target_probabilities": {"1": 0.55, "2": 0.40},
                    "source": "test",
                },
                {"operation": "DONE", "target": None, "confidence": 0.9, "source": "test"},
            ]
        )
        agent.run(
            "http://127.0.0.1:8000/",
            "stay local",
            decide_fn=lambda _req: next(steps),
            verify_fn=lambda _req: {"goal_met": True, "source": "test"},
            driver=drv,
        )
        acts = [c["action"]["id"] for c in drv.calls if c["cmd"] == "act"]
        assert acts == ["e1:click"]

    def test_runner_up_never_replays_secret_onto_different_field(self, monkeypatch):
        import jev_router_common

        monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (False, "offline"))
        snap = {
            "url": "http://127.0.0.1:8000/",
            "title": "Login",
            "text": "login",
            "page_key": "pk1",
            "marker": "m1",
            "guards": {"1": "g1", "2": "g2"},
            "elements": [
                {"index": "1", "role": "textbox", "label": "Password", "operations": ["TYPE_TEXT"]},
                {"index": "2", "role": "textbox", "label": "Public Comment", "operations": ["TYPE_TEXT"]},
            ],
            "actions": [
                {"id": "e1:fill", "kind": "fill", "index": "1", "label": "Password"},
                {"id": "e2:fill", "kind": "fill", "index": "2", "label": "Public Comment"},
            ],
        }
        drv = _StubDriver(snap)
        steps = iter(
            [
                {
                    "operation": "TYPE_TEXT",
                    "target": "1",
                    "confidence": 0.55,
                    "needs_text": True,
                    "target_probabilities": {"1": 0.55, "2": 0.40},
                    "source": "test",
                },
                {"operation": "DONE", "target": None, "confidence": 0.9, "source": "test"},
            ]
        )
        agent.run(
            "http://127.0.0.1:8000/",
            "log in",
            secrets={"pw": "top-secret-value"},
            secret_pick_fn=lambda _g, _f, _p, _k: ("pw", "test"),
            decide_fn=lambda _req: next(steps),
            verify_fn=lambda _req: {"goal_met": True, "source": "test"},
            driver=drv,
        )
        acts = [c["action"]["id"] for c in drv.calls if c["cmd"] == "act"]
        assert acts == ["e1:fill"]

    def test_pure_replay_skips_step0_classify_and_reuses_init_obs(self, monkeypatch):
        import jev_router_common

        called = {"classify": 0}
        monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (True, "online"))
        monkeypatch.setattr(
            jev_router_common,
            "validated_call_jev",
            lambda *_a, **_k: called.__setitem__("classify", called["classify"] + 1),
        )

        trace_steps = [
            {
                "step": 1,
                "decision": {"operation": "DONE", "target": None, "confidence": 0.95, "source": "test"},
                "verify": {"goal_met": True, "source": "test"},
            }
        ]
        drv = _StubDriver(self._base_snap())
        res = agent.run(
            "http://127.0.0.1:8000/",
            "replay goal",
            decide_fn=agent.ReplayFn(trace_steps, "decision", fork_at=None),
            verify_fn=agent.ReplayFn(trace_steps, "verify", fork_at=None),
            driver=drv,
        )
        assert res["status"] == "done"
        assert called["classify"] == 0
        # Only 1 observe total (init_obs reused for step 1).
        assert sum(1 for c in drv.calls if c["cmd"] == "observe") == 1

    def test_check_replay_ignores_step0_classify_entries(self):
        trace = {
            "final": {"status": "done"},
            "steps": [{"step": 1, "decision": {"operation": "DONE", "target": None}}],
        }
        result = {
            "status": "done",
            "log": [
                {"step": 0, "phase": "classify", "goal_feasibility": 0.9},
                {"step": 1, "operation": "DONE", "target": None},
            ],
        }
        assert agent.check_replay(trace, result) == []
