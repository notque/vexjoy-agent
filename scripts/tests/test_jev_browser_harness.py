"""Offline tests for the Jev browser harness: decide payload/parse, verify parse,
agent loop with a fake driver, and the driver/snapshot contract."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import ClassVar

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


decide = _load("jev-browser-decide")
verify = _load("jev-browser-verify")
agent = _load("jev-browser-agent")


@pytest.fixture(autouse=True)
def _jev_offline(monkeypatch):
    """These are offline tests. With a real TYPESAFE_API_KEY in the environment
    the agent's step-0 page classification would call the live API, add a
    `classify` log entry and a request, and change every step count. Tests
    that need Jev "available" override this locally."""
    import jev_router_common

    monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (False, "offline test"))


ELEMENTS = [
    {"index": "1", "node": 1, "role": "heading", "label": "Sign in", "value": "", "operations": []},
    {
        "index": "2",
        "node": 2,
        "role": "textbox",
        "label": "Username",
        "value": "",
        "operations": ["CLICK", "TYPE_TEXT"],
    },
    {
        "index": "3",
        "node": 3,
        "role": "combobox",
        "label": "Country",
        "value": "USA",
        "operations": ["SELECT"],
        "options": [
            {"index": "3:1", "label": "USA", "value": "us"},
            {"index": "3:2", "label": "Canada", "value": "ca"},
        ],
    },
    {"index": "4", "node": 4, "role": "button", "label": "Sign in", "value": "", "operations": ["CLICK"]},
]
ACTIONS = [
    {"id": "e2:click", "kind": "click", "node": 2, "index": "2", "label": "Username"},
    {"id": "e2:fill", "kind": "fill", "node": 2, "index": "2", "label": "Username", "role": "textbox"},
    {"id": "e3:sel:us", "kind": "select", "node": 3, "index": "3:1", "label": "Country → USA", "value": "us"},
    {"id": "e3:sel:ca", "kind": "select", "node": 3, "index": "3:2", "label": "Country → Canada", "value": "ca"},
    {"id": "e4:click", "kind": "click", "node": 4, "index": "4", "label": "Sign in"},
    {"id": "scroll_down", "kind": "scroll", "delta": 640, "label": "Scroll down"},
    {"id": "wait", "kind": "wait", "label": "Wait"},
]
PAGE = {"url": "http://127.0.0.1:1/", "title": "Login", "text": "Sign in Username Country"}


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------


def test_decide_payload_speculative_fanout():
    payload = decide.build_payload({"goal": "sign in", "elements": ELEMENTS, "page": PAGE, "history": []})
    q = payload["questions"]
    assert set(q) == {
        "operation",
        "still_loading",
        "content_assessment",
        "click_target",
        "type_text_target",
        "select_target",
    }
    assert set(q["operation"]["criteria"]) == {
        "CLICK",
        "TYPE_TEXT",
        "SELECT",
        "SCROLL_DOWN",
        "SCROLL_UP",
        "WAIT",
        "DONE",
        "BLOCKED",
    }
    assert set(q["select_target"]["criteria"]) == {"3:1", "3:2"}
    assert set(q["type_text_target"]["criteria"]) == {"2"}


def test_decide_parse_consumes_only_matching_target():
    req = {"goal": "g", "elements": ELEMENTS}
    data = {
        "answers": {
            "operation": {"choice": "SELECT", "probabilities": {"SELECT": 0.9}, "confidence": 0.9},
            "select_target": {"choice": "3:2", "probabilities": {"3:2": 0.8}, "confidence": 0.8},
            "click_target": {"choice": "4", "probabilities": {}, "confidence": 0.5},
        }
    }
    r = decide.parse_response(data, req)
    assert (r["operation"], r["target"], r["needs_text"]) == ("SELECT", "3:2", False)
    assert r["target_probabilities"] == {"3:2": 0.8}


def test_decide_invalid_target_asks_for_retry_not_blocked():
    data = {
        "answers": {
            "operation": {"choice": "CLICK", "confidence": 0.9},
            "click_target": {"choice": "99", "probabilities": {}, "confidence": 0.9},
        }
    }
    r = decide.parse_response(data, {"elements": ELEMENTS})
    # A target that was never offered is a bad answer, not a dead end.
    assert r["operation"] == "RETRY" and r["target"] is None
    assert r["invalid_answer"] is True and r["reason"] == "Jev answer failed validation"
    assert r["confidence"] == 0.0 and r["needs_text"] is False
    valid = decide.parse_response(
        {
            "answers": {
                "operation": {"choice": "CLICK", "confidence": 0.9},
                "click_target": {"choice": "4", "probabilities": {}, "confidence": 0.9},
            }
        },
        {"elements": ELEMENTS},
    )
    assert "invalid_answer" not in valid and valid["operation"] == "CLICK"


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def test_verify_parse_and_deterministic_veto(monkeypatch):
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (True, "ok"))
    data = {
        "answers": {
            "goal_met": {"noul": 0.9},
            "confidence": {"score": 4},
            "has_error": {"noul": 0.1},
            "page_loaded": {"noul": 0.99},
            "evidence_element": {"choice": "1"},
        },
        "usage": {"input_tokens": 1},
    }
    monkeypatch.setattr(verify.jev_router_common, "validated_call_jev", lambda *_: (data, 12.0))
    ok = verify.verify({"goal": "g", "page": PAGE, "elements": ELEMENTS, "checks": {"text_contains": "username"}})
    assert ok["goal_met"] is True and ok["confidence"] == 1.0 and ok["evidence_element"] == "1"
    vetoed = verify.verify({"goal": "g", "page": PAGE, "elements": ELEMENTS, "checks": {"url_contains": "/done"}})
    assert vetoed["goal_met"] is False and vetoed["deterministic"] == {"url_contains": False}


def test_verify_passed_follows_deterministic_override(monkeypatch):
    """`passed` must be computed from the FINAL goal_met. A weak Jev Noul that
    passing deterministic checks lift over the threshold used to leave
    `passed` False because it was computed before the override."""
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (True, "ok"))
    data = {
        "answers": {
            "goal_met": {"noul": 0.35},
            "confidence": {"score": 4},
            "has_error": {"noul": 0.0},
            "page_loaded": {"noul": 1.0},
        }
    }
    monkeypatch.setattr(verify.jev_router_common, "validated_call_jev", lambda *_: (data, 1.0))
    r = verify.verify({"goal": "g", "page": PAGE, "elements": [], "checks": {"text_contains": "username"}})
    assert r["goal_met"] is True and r["passed"] is True
    # Strong Jev but a failing check: neither goal_met nor passed.
    data["answers"]["goal_met"] = {"noul": 0.95}
    r = verify.verify({"goal": "g", "page": PAGE, "elements": [], "checks": {"url_contains": "/nope"}})
    assert r["goal_met"] is False and r["passed"] is False


def test_split_goal_only_on_sequencing_tokens():
    # A bare comma is a list separator, not a step boundary.
    assert verify.split_goal("select red, green and blue") == ["select red, green and blue"]
    assert verify.split_goal("pick a date, then press Search") == ["pick a date", "press Search"]
    assert verify.split_goal("open the menu; choose Settings") == ["open the menu", "choose Settings"]
    assert verify.split_goal("type alice and then submit") == ["type alice", "submit"]
    assert verify.split_goal("fill name then email, phone and zip then save") == [
        "fill name",
        "email, phone and zip",
        "save",
    ]


def test_verify_unavailable_uses_deterministic_only(monkeypatch):
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (False, "no key"))
    r = verify.verify({"goal": "g", "page": PAGE, "checks": {"text_contains": "username"}})
    assert r["goal_met"] is True and r["source"] == "unavailable"
    assert verify.verify({"goal": "g", "page": PAGE})["goal_met"] is False


# ---------------------------------------------------------------------------
# agent loop with fake driver
# ---------------------------------------------------------------------------


class FakeDriver:
    def __init__(self, stale_once: bool = False, wait_fails: bool = False):
        self.calls: list[dict] = []
        self.marker = 0
        self.stale_once = stale_once
        self.wait_fails = wait_fails
        self.closed = False

    def call(self, cmd, **kw):
        self.calls.append({"cmd": cmd, **kw})
        if cmd == "open":
            return {"ok": True, "result": {"url": kw["url"]}}
        if cmd == "observe":
            return {
                "ok": True,
                "result": {
                    **PAGE,
                    "page_key": "k",
                    "marker": f"m{self.marker}",
                    "guards": {"2": "g"},
                    "elements": ELEMENTS,
                    "actions": ACTIONS,
                },
            }
        if cmd == "act":
            if self.stale_once:
                self.stale_once = False
                return {"ok": False, "error": "stale", "stale": True}
            if self.wait_fails and kw["action"]["kind"] == "wait":
                return {"ok": False, "error": "WebSocket closed (1006)"}
            self.marker += 1
            return {"ok": True, "result": {"executed": kw["action"]["id"]}}
        if cmd == "close":
            self.closed = True
            return {"ok": True, "result": {}}
        raise AssertionError(cmd)

    def close(self):
        self.call("close")


def _scripted(plan):
    it = iter(plan)

    def decide_fn(req):
        op, target = next(it)
        return {
            "operation": op,
            "target": target,
            "confidence": 0.9,
            "operation_probabilities": {op: 0.9},
            "target_probabilities": {},
            "needs_text": op == "TYPE_TEXT",
            "source": "test",
            "latency_ms": 1,
            "usage": {"input_tokens": 10},
        }

    return decide_fn


def test_agent_refuses_remote_by_default():
    r = agent.run("https://example.com/", "g", driver=FakeDriver())
    assert r["status"] == "error" and "remote" in r["error"]


def test_agent_loop_done_with_jev_text_and_verify():
    drv = FakeDriver()
    r = agent.run(
        "http://127.0.0.1:1/",
        'log in with username "alice"',
        decide_fn=_scripted([("TYPE_TEXT", "2"), ("SELECT", "3:2"), ("CLICK", "4"), ("DONE", None)]),
        verify_fn=lambda _req: {"goal_met": True, "source": "test", "usage": {}},
        pick_fn=lambda _g, _f, _p, cands: ("alice", "jev") if "alice" in cands else (None, "jev-none"),
        text_fn=lambda *_: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
        driver=drv,
    )
    # requests: 4 decisions + 1 Jev text pick + 1 verify. steps: 4 decisions.
    assert r["status"] == "done" and r["steps"] == 4 and r["requests"] == 6
    acts = [c for c in drv.calls if c["cmd"] == "act"]
    assert [a["action"]["id"] for a in acts] == ["e2:fill", "e3:sel:ca", "e4:click"]
    assert acts[0]["text"] == "alice"
    assert acts[0]["page"]["guards"] == {"2": "g"}
    assert r["log"][0]["text_source"] == "jev"
    assert r["usage"] == {"input_tokens": 40}
    assert not drv.closed  # injected driver is not owned
    # The post-action observe is the next step's snapshot: one initial observe,
    # one for step 1, then one per executed action (3). Never two per step.
    assert sum(1 for c in drv.calls if c["cmd"] == "observe") == 5
    opened = next(c for c in drv.calls if c["cmd"] == "open")
    assert opened["headers"] == {} and opened["header_hosts"] == []


def test_agent_counts_jev_none_and_text_model_as_requests():
    drv = FakeDriver()
    r = agent.run(
        "http://127.0.0.1:1/",
        "type something",
        decide_fn=_scripted([("TYPE_TEXT", "2"), ("BLOCKED", None)]),
        pick_fn=lambda *_: (None, "jev-none"),  # a Jev call that answered NONE
        text_fn=lambda *_: ("composed", "text-model"),
        driver=drv,
    )
    assert r["status"] == "blocked"
    # step 1: decide + jev-none pick + text model; step 2: decide.
    assert r["requests"] == 4
    assert r["log"][0]["text_source"] == "text-model" and r["log"][0]["text"] == "composed"


def test_agent_records_failed_wait_on_entry():
    drv = FakeDriver(wait_fails=True)
    err = {
        "operation": "BLOCKED",
        "target": None,
        "confidence": 0,
        "needs_text": False,
        "source": "error",
        "error": "t",
    }
    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=lambda _req: dict(err), driver=drv)
    assert r["status"] == "blocked"
    waits = [e for e in r["log"] if e.get("retry") == "wait"]
    assert waits and all(e["wait_error"] == "WebSocket closed (1006)" for e in waits)


def test_agent_invalid_answer_retries_then_blocks():
    drv = FakeDriver()
    bad = {
        "operation": "RETRY",
        "target": None,
        "confidence": 0.0,
        "needs_text": False,
        "source": "jev",
        "invalid_answer": True,
        "reason": "Jev answer failed validation",
    }
    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=lambda _req: dict(bad), driver=drv)
    assert r["status"] == "blocked" and "failed validation" in r["reason"]
    assert r["steps"] == agent.STALL_LIMIT
    assert all(e.get("retry") == "invalid-answer" for e in r["log"])
    waits = [c for c in drv.calls if c["cmd"] == "act" and c["action"]["id"] == "wait"]
    assert len(waits) == agent.STALL_LIMIT - 1  # the last step blocks before waiting
    assert not [c for c in drv.calls if c["cmd"] == "act" and c["action"]["kind"] != "wait"]


def test_agent_secret_never_logged():
    drv = FakeDriver()
    r = agent.run(
        "http://127.0.0.1:1/",
        "log in",
        decide_fn=_scripted([("TYPE_TEXT", "2"), ("BLOCKED", None)]),
        secrets={"username": "hunter2"},
        secret_pick_fn=lambda _g, field, _p, _labels: (
            ("username", "test") if "user" in field["label"].lower() else (None, "test-none")
        ),
        driver=drv,
    )
    assert r["status"] == "blocked"
    assert "hunter2" not in json.dumps(r)
    assert next(c for c in drv.calls if c["cmd"] == "act")["text"] == "hunter2"


def test_agent_stale_act_reobserves_without_stall_penalty():
    drv = FakeDriver(stale_once=True)
    r = agent.run(
        "http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4"), ("CLICK", "4"), ("BLOCKED", None)]), driver=drv
    )
    assert r["log"][0]["stale"] is True
    assert r["log"][1].get("action_id") == "e4:click"
    assert r["status"] == "blocked"


def test_agent_stall_guard():
    class Frozen(FakeDriver):
        def call(self, cmd, **kw):
            out = super().call(cmd, **kw)
            self.marker = 0  # page never changes
            return out

    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4")] * 10), driver=Frozen())
    # First observe always counts as "changed"; then STALL_LIMIT unchanged steps.
    assert r["status"] == "blocked" and r["steps"] == agent.STALL_LIMIT + 1


def test_agent_done_rejected_then_verified():
    verdicts = iter([False, True])
    r = agent.run(
        "http://127.0.0.1:1/",
        "g",
        decide_fn=_scripted([("DONE", None), ("CLICK", "4"), ("DONE", None)]),
        verify_fn=lambda _req: {"goal_met": next(verdicts), "source": "test"},
        driver=FakeDriver(),
    )
    assert r["status"] == "done" and r["steps"] == 3
    assert r["log"][0]["verify"]["goal_met"] is False


def test_agent_budget():
    r = agent.run(
        "http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4")] * 5), max_requests=2, driver=FakeDriver()
    )
    assert r["status"] == "budget" and r["requests"] == 2


def test_goal_candidates():
    c = agent.goal_candidates('Sign in with username alice and email bob@x.io, search for "red shoes" then enter 90210')
    assert {"alice", "bob@x.io", "red shoes", "90210"} <= set(c)


# ---------------------------------------------------------------------------
# driver / snapshot contract (static)
# ---------------------------------------------------------------------------


def test_driver_has_no_imports_outside_node_builtins():
    src = (SCRIPTS / "lib" / "jev_browser" / "cdp_driver.mjs").read_text()
    for m in re.finditer(r'from\s+"([^"]+)"', src):
        assert m.group(1).startswith("node:"), m.group(1)


def test_driver_scopes_headers_and_handles_transport_events():
    src = (SCRIPTS / "lib" / "jev_browser" / "cdp_driver.mjs").read_text()
    # Caller headers go through Fetch interception scoped to the home host,
    # never Network.setExtraHTTPHeaders (which sends them to every origin).
    assert "Network.setExtraHTTPHeaders" not in src
    assert "Fetch.enable" in src and "Fetch.requestPaused" in src and "Fetch.continueRequest" in src
    assert "this.headerHosts.has(host)" in src
    # Navigation errors and load timeouts surface as rejected commands.
    assert "r.errorText" in src and "page did not finish loading" in src
    # A closed socket rejects every pending command; dialogs are auto-dismissed.
    assert 'addEventListener("close"' in src and "rejectAll(" in src
    assert "Page.javascriptDialogOpening" in src and "Page.handleJavaScriptDialog" in src
    # Listeners are removable and removed when a tab is replaced.
    assert "off(listener)" in src and "tab.close();" in src
    # WAIT is never rejected as stale.
    assert 'action.kind === "wait") return true' in src
    # DevTools launch timeout kills the orphan and its profile.
    assert 'proc.kill("SIGKILL")' in src


def test_driver_read_times_out_and_detects_exit():
    import queue

    d = agent.Driver.__new__(agent.Driver)
    d._lines = queue.Queue()
    d.stderr = agent.tempfile.TemporaryFile(mode="w+")
    with pytest.raises(RuntimeError, match="did not reply within"):
        d._read(timeout=0.01)
    d._lines.put(None)  # reader thread saw EOF
    with pytest.raises(RuntimeError, match="driver exited"):
        d._read(timeout=0.01)
    d._lines.put('{"ok": true}\n')
    assert d._read(timeout=0.01) == {"ok": True}
    assert agent.READ_TIMEOUT_S >= 30 and agent.CLOSE_TIMEOUT_S <= 10


def test_snapshot_never_exposes_password_values():
    src = (SCRIPTS / "lib" / "jev_browser" / "snapshot.js").read_text()
    assert '"(filled)"' in src and "p=${el.value ? 1 : 0}" in src


@pytest.mark.parametrize(
    "op,target,expect",
    [
        ("CLICK", "4", "e4:click"),
        ("TYPE_TEXT", "2", "e2:fill"),
        ("SELECT", "3:2", "e3:sel:ca"),
        ("SCROLL_DOWN", None, "scroll_down"),
        ("WAIT", None, "wait"),
        ("CLICK", "77", None),
    ],
)
def test_find_action(op, target, expect):
    a = agent._find_action({"actions": ACTIONS}, op, target)
    assert (a or {}).get("id") == expect


# ---------------------------------------------------------------------------
# reviewer-driven additions: preflight, scrub, Jev-error retry, stale cap
# ---------------------------------------------------------------------------


def test_preflight_errors(monkeypatch):
    import jev_router_common

    monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (False, "TYPESAFE_API_KEY unset"))
    assert agent.preflight("http://127.0.0.1/", False, [])[1].startswith("Jev unavailable")
    monkeypatch.setattr(jev_router_common, "typesafe_available", lambda: (True, "ok"))
    monkeypatch.delenv("JEV_TEST_SECRET", raising=False)
    assert "is unset" in agent.preflight("http://127.0.0.1/", False, ["password=JEV_TEST_SECRET"])[1]
    assert "expected LABEL=ENV_VAR" in agent.preflight("http://127.0.0.1/", False, ["nonsense"])[1]
    monkeypatch.setenv("JEV_TEST_SECRET", "pw")
    secrets, err, headers = agent.preflight("http://127.0.0.1/", False, ["password=JEV_TEST_SECRET"])
    assert err is None and secrets == {"password": "pw"} and headers == {}
    assert agent.preflight("https://example.com/", False, [])[1].startswith("remote URL refused")
    assert agent.preflight("https://app.example.com/", False, [], {"example.com"})[1] is None
    monkeypatch.setenv("JEV_TEST_TOKEN", "tok")
    _, err, headers = agent.preflight("http://127.0.0.1/", False, [], None, ["X-Smoke-Token=JEV_TEST_TOKEN"])
    assert err is None and headers == {"X-Smoke-Token": "tok"}
    assert "is unset" in agent.preflight("http://127.0.0.1/", False, [], None, ["X-T=NOPE_UNSET_VAR"])[1]


def test_scrub_masks_text_and_values():
    snap = {
        "text": "hello hunter2 world",
        "elements": [{"index": "1", "value": "hunter2"}, {"index": "2", "value": "x"}],
    }
    out = agent._scrub(snap, {"hunter2"})
    assert out["text"] == "hello (secret) world"
    assert [e["value"] for e in out["elements"]] == ["(secret)", "x"]
    assert agent._scrub(snap, set()) is snap


def test_jev_error_retries_as_wait_then_blocks():
    drv = FakeDriver()
    err = {
        "operation": "BLOCKED",
        "target": None,
        "confidence": 0,
        "needs_text": False,
        "source": "error",
        "error": "timeout",
    }
    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=lambda _req: dict(err), driver=drv)
    assert r["status"] == "blocked" and "Jev error" in r["reason"]
    waits = [c for c in drv.calls if c["cmd"] == "act" and c["action"]["id"] == "wait"]
    assert len(waits) == agent.STALL_LIMIT - 1
    assert r["log"][0]["retry"] == "wait"


def test_unavailable_blocks_immediately():
    err = {
        "operation": "BLOCKED",
        "target": None,
        "confidence": 0,
        "needs_text": False,
        "source": "unavailable",
        "error": "no key",
    }
    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=lambda _req: dict(err), driver=FakeDriver())
    assert r["status"] == "blocked" and r["steps"] == 1 and "unavailable" in r["reason"]


def test_perpetual_stale_page_is_capped():
    class AlwaysStale(FakeDriver):
        def call(self, cmd, **kw):
            if cmd == "act":
                self.calls.append({"cmd": cmd, **kw})
                return {"ok": False, "error": "stale", "stale": True}
            return super().call(cmd, **kw)

    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4")] * 20), driver=AlwaysStale())
    assert r["status"] == "blocked" and "kept changing" in r["reason"]
    # `stale_count` is fed by two signals: the element fingerprint unchanged at
    # observe time (+1 from step 2 on) and the act rejected as stale (+1 every
    # step). So step k ends at 2k-1 and the cap trips at ceil(STALE_LIMIT/2).
    assert r["steps"] == (agent.STALE_LIMIT + 1) // 2 == 3
    assert all(e["stale"] is True for e in r["log"])


def test_reason_present_on_every_exit():
    r = agent.run(
        "http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4")] * 5), max_steps=2, driver=FakeDriver()
    )
    assert r["status"] == "budget" and "step budget" in r["reason"]


def test_parse_text_reply_variants():
    assert agent._parse_text_reply('{"text": "bob"}') == ("bob", "ok")
    assert agent._parse_text_reply('```json\n{"text": "bob"}\n```') == ("bob", "ok")
    assert agent._parse_text_reply('Sure: {"text": "bob"} done') == ("bob", "ok")
    assert agent._parse_text_reply("nope")[0] is None
    assert agent._parse_text_reply('{"text": ""}') == (None, "text-model-empty")


def test_generate_text_cli_backend(monkeypatch):
    monkeypatch.setattr(agent, "TEXT_MODEL_BACKEND", "claude-cli")
    monkeypatch.setattr(agent.shutil, "which", lambda _n: "/usr/bin/claude")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))

        class R:
            returncode = 0
            stdout = '{"text": "hello"}'

        return R()

    monkeypatch.setattr(agent.subprocess, "run", fake_run)
    assert agent.generate_text("g", {"index": "2", "label": "Username"}, PAGE, []) == ("hello", "claude-cli")
    cmd, kw = calls[0]
    assert cmd[:2] == ["claude", "-p"] and "--no-session-persistence" in cmd and "" in cmd
    assert kw["cwd"] == agent.tempfile.gettempdir() and "GOAL: g" in kw["input"]


def test_generate_text_auto_prefers_cli_without_key(monkeypatch):
    monkeypatch.setattr(agent, "TEXT_MODEL_BACKEND", "auto")
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(agent.shutil, "which", lambda _n: None)
    assert agent.generate_text("g", {}, PAGE, []) == (None, "claude-cli-missing")


def test_origin_guard_returns_home_and_counts_stall():
    class Wanderer(FakeDriver):
        def __init__(self):
            super().__init__()
            self.away = False

        def call(self, cmd, **kw):
            if cmd == "navigate":
                self.calls.append({"cmd": cmd, **kw})
                self.away = False
                return {"ok": True, "result": {}}
            out = super().call(cmd, **kw)
            if cmd == "observe" and self.away:
                out["result"]["url"] = "https://accounts.example.com/oauth"
            if cmd == "act":
                self.away = True
            return out

    drv = Wanderer()
    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=_scripted([("CLICK", "4")] * 10), driver=drv)
    assert r["status"] == "blocked" and "leaving the site" in r["reason"]
    navs = [c for c in drv.calls if c["cmd"] == "navigate"]
    assert navs and all(c["url"] == "http://127.0.0.1:1/" for c in navs)
    assert any(e.get("phase") == "origin-guard" for e in r["log"])


def test_low_confidence_pick_is_held_then_blocks():
    drv = FakeDriver()

    def guess(_req):
        return {"operation": "CLICK", "target": "4", "confidence": 0.1, "needs_text": False, "source": "test"}

    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=guess, driver=drv)
    assert r["status"] == "blocked" and "unsure" in r["reason"]
    assert all(e.get("retry") == "low-confidence" for e in r["log"])
    assert not [c for c in drv.calls if c["cmd"] == "act" and c["action"]["kind"] == "click"]


def test_decide_table_marks_offscreen_external_and_nav():
    table = decide._build_element_table(
        [
            {"index": "1", "role": "button", "label": "Start", "operations": ["CLICK"], "offscreen": True},
            {"index": "2", "role": "link", "label": "Help", "operations": ["CLICK"], "external": True},
            {"index": "3", "role": "link", "label": "Analytics", "operations": ["CLICK"], "nav": "/analytics"},
        ]
    )
    assert "offscreen, scrolled into view on use" in table
    assert "leaves this site" in table
    assert "navigates away to /analytics" in table
    targets = decide._group_targets(
        [{"index": "3", "role": "link", "label": "A", "operations": ["CLICK"], "nav": "/x"}]
    )
    assert targets["CLICK"]["3"]["nav"] == "/x"


def test_verify_check_url_and_audit_with_fake_driver(monkeypatch):
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (True, "ok"))
    answers = {
        "goal_met": {"noul": 0.9},
        "confidence": {"score": 4},
        "has_error": {"noul": 0.0},
        "page_loaded": {"noul": 1.0},
    }
    monkeypatch.setattr(
        verify.jev_router_common, "validated_call_jev", lambda *_: ({"answers": answers, "usage": {}}, 5.0)
    )
    drv = FakeDriver()
    out = verify.check_url(
        "http://127.0.0.1:1/", ["shows a form", "has a country picker"], driver=drv, headers={"X-T": "v"}
    )
    assert out["passed"] is True and len(out["results"]) == 2 and out["element_count"] == len(ELEMENTS)
    assert next(c for c in drv.calls if c["cmd"] == "open")["headers"] == {"X-T": "v"}
    assert not drv.closed  # injected driver stays open

    class Factory:
        made: ClassVar[list] = []

        def __init__(self):
            self.d = FakeDriver()
            Factory.made.append(self.d)

        def call(self, *a, **k):
            return self.d.call(*a, **k)

        def close(self):
            self.d.close()

    monkeypatch.setattr(verify, "_load_agent", lambda: type("M", (), {"Driver": Factory}))
    audit = verify.run_audit("http://127.0.0.1:1", {"/a": ["g1"], "/b": ["g2", "g3"]})
    assert (audit["total"], audit["passed"], audit["failed"]) == (2, 2, 0)
    assert len(Factory.made) == 1 and Factory.made[0].closed  # one browser for the whole audit
    assert [c["url"] for c in Factory.made[0].calls if c["cmd"] == "open"] == [
        "http://127.0.0.1:1/a",
        "http://127.0.0.1:1/b",
    ]


def test_verify_passed_requires_evidence(monkeypatch):
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (True, "ok"))
    weak = {
        "goal_met": {"noul": 0.8},
        "confidence": {"score": 1},
        "has_error": {"noul": 0.0},
        "page_loaded": {"noul": 1.0},
    }
    monkeypatch.setattr(
        verify.jev_router_common, "validated_call_jev", lambda *_: ({"answers": weak, "usage": {}}, 5.0)
    )
    r = verify.verify({"goal": "g", "page": PAGE, "elements": []})
    assert r["goal_met"] is True and r["passed"] is False and r["confidence"] == 0.25


def test_still_loading_holds_action_and_waits():
    drv = FakeDriver()
    seq = iter([0.9, 0.9, 0.1])

    def decide_fn(_req):
        return {
            "operation": "CLICK",
            "target": "4",
            "confidence": 0.9,
            "needs_text": False,
            "source": "test",
            "still_loading": next(seq),
        }

    r = agent.run("http://127.0.0.1:1/", "g", decide_fn=decide_fn, driver=drv, max_steps=3)
    acts = [c["action"]["id"] for c in drv.calls if c["cmd"] == "act"]
    assert acts == ["wait", "wait", "e4:click"]
    assert [e.get("retry") for e in r["log"]] == ["still-loading", "still-loading", None]


def test_verify_contradiction_and_loading_block_goal_met(monkeypatch):
    monkeypatch.setattr(verify.jev_router_common, "typesafe_available", lambda: (True, "ok"))
    base = {
        "goal_met": {"noul": 0.9},
        "confidence": {"score": 4},
        "has_error": {"noul": 0.0},
        "page_loaded": {"noul": 1.0},
    }
    for extra, expect in [
        ({}, True),
        ({"contradiction": {"noul": 0.8}}, False),
        ({"still_loading": {"noul": 0.7}}, False),
    ]:
        ans = {**base, **extra}
        monkeypatch.setattr(
            verify.jev_router_common, "validated_call_jev", lambda *_, ans=ans: ({"answers": ans, "usage": {}}, 5.0)
        )
        assert verify.verify({"goal": "g", "page": PAGE, "elements": []})["goal_met"] is expect, extra


# ---------------------------------------------------------------------------
# smoke test oracle
# ---------------------------------------------------------------------------
