"""Router guards persist before classification and reject native bypasses."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import router_gate


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "hooks" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


injector = load("mandatory_injector", "jev-route-injector-userprompt.py")
guard = load("mandatory_guard", "router-required-gate.py")


@pytest.fixture(autouse=True)
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_ROUTER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("JEV_SESSION_ID", "turn-test")


def submit(monkeypatch, capsys, prompt):
    monkeypatch.setattr(injector, "read_stdin", lambda **_kw: json.dumps({"prompt": prompt, "session_id": "turn-test"}))
    with pytest.raises(SystemExit):
        injector.main()
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("prefix", ["/d", "$d", "/do", "$do"])
def test_marker_precedes_classification_even_when_unavailable(monkeypatch, capsys, prefix):
    prompt = prefix + " fix intent"

    def classify(*args):
        marker = router_gate.get_required_router("turn-test")
        assert marker["pending"]
        assert marker["request_hash"] == router_gate.text_hash(prompt)
        return None

    monkeypatch.setattr(injector, "run_jev_route", classify)
    result = submit(monkeypatch, capsys, prompt)
    assert router_gate.get_required_router("turn-test")["pending"]
    assert "ALL skill phases are mandatory" in result["hookSpecificOutput"]["additionalContext"]


def test_do_does_not_run_jev_classifier(monkeypatch, capsys):
    monkeypatch.setattr(injector, "run_jev_route", lambda *_args: pytest.fail("/do must not run Jev classification"))
    submit(monkeypatch, capsys, "$do fix it")


def test_nonrouter_turn_clears_only_completed_own_marker(monkeypatch, capsys):
    router_gate.set_required_router("turn-test", "d", "/d old")
    router_gate.mark_validated("turn-test", "/d old", "old", {})
    router_gate.set_required_router("other", "d", "/d other")
    submit(monkeypatch, capsys, "new unrelated task")
    assert router_gate.get_required_router("turn-test") is None
    assert router_gate.get_required_router("other")["pending"]


def test_command_envelope():
    assert injector.extract_router("<command-name>/do</command-name>\n<command-args>fix it</command-args>") == (
        "do",
        "fix it",
    )
    assert injector.extract_router("/documentation please") is None


@pytest.mark.parametrize("tool", ["Agent", "Task"])
def test_native_dispatch_cannot_bypass_builder(tool):
    router_gate.set_required_router("turn-test", "d", "/d fix")
    result = guard.evaluate({"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": "turn-test"})
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_final_answer_cannot_bypass_intent_even_when_stop_hook_active():
    router_gate.set_required_router("turn-test", "d", "/d fix")
    result = guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test", "stop_hook_active": True})
    assert result["decision"] == "block"


def test_setup_tools_and_unrelated_sessions_allowed():
    router_gate.set_required_router("turn-test", "d", "/d fix")
    assert guard.evaluate({"tool_name": "Read", "session_id": "turn-test"}) == {}
    assert guard.evaluate({"tool_name": "Agent", "session_id": "other"}) == {}


def test_malformed_state_blocks(monkeypatch):
    monkeypatch.setattr(
        router_gate, "get_required_router", lambda _session: (_ for _ in ()).throw(ValueError("corrupt"))
    )
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"})["decision"] == "block"


def test_checked_blocker_can_report_but_cannot_dispatch(monkeypatch):
    monkeypatch.setattr(
        router_gate, "get_required_router", lambda _session: {"pending": True, "status": "checked_blocked"}
    )
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"}) == {}
    assert (
        guard.evaluate({"tool_name": "Agent", "session_id": "turn-test"})["hookSpecificOutput"]["permissionDecision"]
        == "deny"
    )


def test_generated_codex_stop_command_preserves_block(tmp_path):
    import os
    import shlex
    import subprocess

    spec = importlib.util.spec_from_file_location("mandatory_generator", ROOT / "scripts/generate-codex-hooks-json.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    entries = generator.parse_allowlist((ROOT / "scripts/codex-hooks-allowlist.txt").read_text())
    entry = next(item for item in entries if item["event"] == "Stop" and item["filename"] == "router-required-gate.py")
    config = generator.build_hooks_json([entry], codex_hooks_dir=str(ROOT / "hooks"))
    command = config["hooks"]["Stop"][0]["hooks"][0]["command"]
    router_gate.set_required_router("turn-test", "do", "$do intent")
    result = subprocess.run(
        shlex.split(command),
        input=json.dumps({"hook_event_name": "Stop", "session_id": "turn-test", "cwd": str(tmp_path)}),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "block"


def test_validated_dispatch_is_exact_and_single_use():
    request = "$d fix intent"
    router_gate.set_required_router("turn-test", "d", request)
    router_gate.authorize_dispatch("turn-test", request, "validated handoff")
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "session_id": "turn-test",
        "tool_input": {"prompt": "changed handoff"},
    }
    assert guard.evaluate(event)["hookSpecificOutput"]["permissionDecision"] == "deny"
    event["tool_input"]["prompt"] = "validated handoff"
    assert guard.evaluate(event) == {}
    assert guard.evaluate(event)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"}) == {}


def test_direct_finalize_does_not_authorize_agent():
    request = "$d fix intent"
    router_gate.set_required_router("turn-test", "d", request)
    router_gate.mark_validated("turn-test", request, "fix intent", {})
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"}) == {}
    assert (
        guard.evaluate({"tool_name": "Agent", "session_id": "turn-test"})["hookSpecificOutput"]["permissionDecision"]
        == "deny"
    )


def test_new_turn_same_text_invalidates_previous_dispatch():
    request = "$d fix intent"
    router_gate.set_required_router("turn-test", "d", request)
    router_gate.authorize_dispatch("turn-test", request, "old handoff")
    router_gate.set_required_router("turn-test", "d", request)
    assert not router_gate.consume_dispatch("turn-test", "old handoff")
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"})["decision"] == "block"


def test_parallel_fanout_authorizations_are_preserved_and_single_use():
    from concurrent.futures import ThreadPoolExecutor

    request = "$d parallel fix"
    router_gate.set_required_router("turn-test", "d", request)
    prompts = [f"checked handoff {index}" for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda prompt: router_gate.authorize_dispatch("turn-test", request, prompt), prompts))
    assert len(router_gate.get_required_router("turn-test")["dispatch_prompt_hashes"]) == 8
    with ThreadPoolExecutor(max_workers=8) as pool:
        consumed = list(pool.map(lambda prompt: router_gate.consume_dispatch("turn-test", prompt), prompts + prompts))
    assert sum(consumed) == 8
    assert router_gate.get_required_router("turn-test")["status"] == "dispatched"


def test_native_stop_waits_for_every_fanout_dispatch():
    request = "$d dispatch both"
    router_gate.set_required_router("turn-test", "d", request)
    router_gate.authorize_dispatch("turn-test", request, "first")
    router_gate.authorize_dispatch("turn-test", request, "second")
    event = {"hook_event_name": "Stop", "session_id": "turn-test"}
    assert guard.evaluate(event)["decision"] == "block"
    assert router_gate.consume_dispatch("turn-test", "first")
    assert guard.evaluate(event)["decision"] == "block"
    assert router_gate.consume_dispatch("turn-test", "second")
    assert guard.evaluate(event) == {}


def test_codex_adapter_explicitly_marks_limited_dispatch_observability(tmp_path):
    import os
    import shlex
    import subprocess

    spec = importlib.util.spec_from_file_location(
        "host_marker_generator", ROOT / "scripts/generate-codex-hooks-json.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    entries = generator.parse_allowlist((ROOT / "scripts/codex-hooks-allowlist.txt").read_text())
    entry = next(item for item in entries if item["event"] == "Stop" and item["filename"] == "router-required-gate.py")
    command = generator.build_hooks_json([entry], codex_hooks_dir=str(ROOT / "hooks"))["hooks"]["Stop"][0]["hooks"][0][
        "command"
    ]
    router_gate.set_required_router("turn-test", "d", "$d task")
    router_gate.authorize_dispatch("turn-test", "$d task", "checked worker")
    event = {"hook_event_name": "Stop", "session_id": "turn-test", "cwd": str(tmp_path)}
    assert guard.evaluate(event)["decision"] == "block"
    result = subprocess.run(
        shlex.split(command), input=json.dumps(event), text=True, capture_output=True, env=os.environ.copy(), timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}
    # The adapter exception never consumes or claims that the worker ran.
    assert router_gate.get_required_router("turn-test")["status"] == "dispatch_ready"


@pytest.mark.parametrize("phase", ["pending", "checked_blocked", "dispatch_ready"])
def test_unprefixed_continuation_retains_unfinished_obligation(monkeypatch, capsys, phase):
    request = "$d fix the checks"
    router_gate.set_required_router("turn-test", "d", request)
    if phase == "checked_blocked":
        router_gate.mark_checked_blocked("turn-test", request)
    elif phase == "dispatch_ready":
        router_gate.authorize_dispatch("turn-test", request, "old handoff")
    previous = router_gate.get_required_router("turn-test")
    result = submit(monkeypatch, capsys, "yes, both routers")
    marker = router_gate.get_required_router("turn-test")
    assert marker["pending"] is True
    assert marker["request_hash"] == router_gate.text_hash("yes, both routers")
    assert marker["generation"] != previous["generation"]
    assert router_gate.text_hash(request) in marker["prior_request_hashes"]
    assert not router_gate.consume_dispatch("turn-test", "old handoff")
    assert "task_spec.prior_context" in result["hookSpecificOutput"]["additionalContext"]
    assert (
        guard.evaluate({"tool_name": "Agent", "session_id": "turn-test"})["hookSpecificOutput"]["permissionDecision"]
        == "deny"
    )
    assert guard.evaluate({"hook_event_name": "Stop", "session_id": "turn-test"})["decision"] == "block"
