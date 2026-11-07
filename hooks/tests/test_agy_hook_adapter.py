"""Tests for the Antigravity-to-VexJoy hook compatibility adapter (hooks/agy-hook-adapter.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / "hooks" / "agy-hook-adapter.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("agy_hook_adapter", ADAPTER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def adapter():
    return _load_adapter()


def _agy_event(
    event: str = "PreToolUse",
    *,
    conversation_id: str = "conv-agy-123",
    tool_name: str = "run_command",
    args: dict | None = None,
    **extra: object,
) -> dict:
    payload: dict = {
        "hookEventName": event,
        "conversationId": conversation_id,
        "workspacePaths": [str(ROOT)],
        "modelName": "gemini-4-argon-high",
        "stepIndex": 4,
    }
    if event in ("PreToolUse", "PostToolUse"):
        payload["toolCall"] = {
            "name": tool_name,
            "id": "call-1",
            "args": args if args is not None else {"CommandLine": "git status"},
        }
    payload.update(extra)
    return payload


def _write_hook(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "child-hook.py"
    path.write_text(body, encoding="utf-8")
    return path


def _run_cli(
    hook: Path,
    event: str,
    failure_policy: str,
    payload: dict | str,
    *,
    matcher: str = "run_command",
    drain_deferred: bool = False,
    timeout: float = 5,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    cmd = [
        sys.executable,
        str(ADAPTER_PATH),
        "--hook",
        str(hook),
        "--event",
        event,
        "--matcher",
        matcher,
        "--failure-policy",
        failure_policy,
        "--timeout",
        str(timeout),
    ]
    if drain_deferred:
        cmd.append("--drain-deferred")
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        check=False,
    )


def test_normalize_agy_payload_maps_camel_case_and_tools(adapter):
    payload = _agy_event(
        "PreToolUse",
        tool_name="run_command",
        args={"CommandLine": "pytest -q", "toolSummary": "Run tests"},
        transcriptPath="/tmp/transcript.jsonl",
    )
    norm = adapter.normalize_agy_payload(payload, agy_event="PreToolUse")

    assert norm["hook_event_name"] == "PreToolUse"
    assert norm["session_id"] == "conv-agy-123"
    assert norm["cwd"] == str(ROOT)
    assert norm["transcript_path"] == "/tmp/transcript.jsonl"
    assert norm["tool_name"] == "Bash"
    assert norm["agy_tool_name"] == "run_command"
    assert norm["tool_input"]["command"] == "pytest -q"
    assert norm["tool_input"]["description"] == "Run tests"


@pytest.mark.parametrize(
    ("agy_tool", "agy_args", "expected_claude_tool", "expected_keys"),
    [
        (
            "write_file",
            {"Path": "/tmp/a.py", "Content": "print(1)\n"},
            "Write",
            {"file_path": "/tmp/a.py", "content": "print(1)\n"},
        ),
        (
            "edit_file",
            {"Path": "/tmp/a.py", "Target": "old", "Replacement": "new"},
            "Edit",
            {"file_path": "/tmp/a.py", "old_string": "old", "new_string": "new"},
        ),
        (
            "read_file",
            {"Path": "/tmp/a.py"},
            "Read",
            {"file_path": "/tmp/a.py"},
        ),
        (
            "invoke_subagent",
            {"TypeName": "research", "Role": "Explorer", "Prompt": "check files", "Model": "flash"},
            "Agent",
            {"subagent_type": "research", "description": "Explorer", "prompt": "check files", "model": "flash"},
        ),
        (
            "run_workflow",
            {"Script": "def workflow(ctx): pass", "Description": "fan-out"},
            "Workflow",
            {"script": "def workflow(ctx): pass", "description": "fan-out"},
        ),
    ],
)
def test_normalize_tool_input_mappings(adapter, agy_tool, agy_args, expected_claude_tool, expected_keys):
    payload = _agy_event("PreToolUse", tool_name=agy_tool, args=agy_args)
    norm = adapter.normalize_agy_payload(payload, agy_event="PreToolUse")
    assert norm["tool_name"] == expected_claude_tool
    for k, v in expected_keys.items():
        assert norm["tool_input"][k] == v


def test_normalize_pre_invocation_maps_to_user_prompt_submit(adapter):
    payload = _agy_event("PreInvocation", lastUserInput="ship the argon feature")
    norm = adapter.normalize_agy_payload(payload, agy_event="PreInvocation")
    assert norm["hook_event_name"] == "UserPromptSubmit"
    assert norm["prompt"] == "ship the argon feature"
    assert norm["userMessage"] == "ship the argon feature"


def test_map_claude_updated_input_to_agy(adapter):
    orig = {"CommandLine": "git push", "WaitMsBeforeAsync": 5000}
    updated = {"command": "git push --force-with-lease"}
    res = adapter.map_claude_updated_input_to_agy("run_command", orig, updated)
    assert res["CommandLine"] == "git push --force-with-lease"
    assert res["WaitMsBeforeAsync"] == 5000

    edit_orig = {"Path": "a.py", "Target": "x", "Replacement": "y"}
    edit_upd = {"file_path": "b.py", "old_string": "x2", "new_string": "y2"}
    edit_res = adapter.map_claude_updated_input_to_agy("edit_file", edit_orig, edit_upd)
    assert edit_res == {"Path": "b.py", "Target": "x2", "Replacement": "y2"}


def test_session_start_and_pre_invocation_emit_inject_steps(adapter):
    norm_event = {"session_id": "conv-1"}
    out_ss = adapter.translate_child_result("SessionStart", 0, "branch briefing", "", normalized_event=norm_event)
    assert out_ss == {"injectSteps": [{"systemMessage": {"systemMessage": "branch briefing"}}]}

    claude_json = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "[do-route] skill=do model=gemini-4-argon",
            }
        }
    )
    out_pre = adapter.translate_child_result("PreInvocation", 0, claude_json, "", normalized_event=norm_event)
    assert out_pre == {
        "injectSteps": [{"systemMessage": {"systemMessage": "[do-route] skill=do model=gemini-4-argon"}}]
    }


def test_pretooluse_allow_deny_ask_and_overwrite(adapter):
    norm_event = {
        "session_id": "conv-1",
        "agy_tool_name": "run_command",
        "agy_tool_args": {"CommandLine": "git status", "WaitMsBeforeAsync": 5000},
    }

    # Exit 0 empty -> allow
    assert adapter.translate_child_result("PreToolUse", 0, "", "", normalized_event=norm_event) == {"decision": "allow"}

    # Exit 2 -> deny with stderr reason
    deny_exit2 = adapter.translate_child_result(
        "PreToolUse", 2, "", "blocked by branch safety", normalized_event=norm_event
    )
    assert deny_exit2 == {
        "decision": "deny",
        "reason": "blocked by branch safety",
    }

    # Claude JSON deny
    claude_deny = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "credential file blocked",
            }
        }
    )
    assert adapter.translate_child_result("PreToolUse", 0, claude_deny, "", normalized_event=norm_event) == {
        "decision": "deny",
        "reason": "credential file blocked",
    }

    # Claude JSON overwrite with updatedInput
    claude_overwrite = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": {"command": "rtk git status"},
            }
        }
    )
    overwrite_out = adapter.translate_child_result("PreToolUse", 0, claude_overwrite, "", normalized_event=norm_event)
    assert overwrite_out == {
        "decision": "allow",
        "overwrite": {"CommandLine": "rtk git status", "WaitMsBeforeAsync": 5000},
    }


def test_posttooluse_returns_empty_json_and_queues_deferred_context_for_pre_invocation(tmp_path: Path):
    state_dir = tmp_path / "agy-state"
    env = {"VEXJOY_AGY_DEFERRED_DIR": str(state_dir)}

    post_hook = _write_hook(
        tmp_path,
        'import json\nprint(json.dumps({"hookSpecificOutput": {"additionalContext": "syntax warning in foo.py"}}))\n',
    )
    post_payload = _agy_event(
        "PostToolUse",
        conversation_id="conv-defer-1",
        tool_name="write_file",
        args={"Path": "foo.py", "Content": "x = 1\n"},
    )
    post_res = _run_cli(post_hook, "PostToolUse", "open", post_payload, matcher="write_file", extra_env=env)
    assert post_res.returncode == 0
    assert json.loads(post_res.stdout) == {}

    pre_hook = _write_hook(tmp_path, 'print("fresh prompt context")\n')
    pre_payload = _agy_event("PreInvocation", conversation_id="conv-defer-1", lastUserInput="next turn")
    pre_res = _run_cli(
        pre_hook,
        "PreInvocation",
        "open",
        pre_payload,
        matcher="",
        drain_deferred=True,
        extra_env=env,
    )
    assert pre_res.returncode == 0
    pre_data = json.loads(pre_res.stdout)
    assert len(pre_data["injectSteps"]) == 1
    injected = pre_data["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "syntax warning in foo.py" in injected
    assert "fresh prompt context" in injected

    # Second PreInvocation after drain should not repeat the old PostToolUse context
    pre_res_2 = _run_cli(
        pre_hook,
        "PreInvocation",
        "open",
        pre_payload,
        matcher="",
        drain_deferred=True,
        extra_env=env,
    )
    assert pre_res_2.returncode == 0
    assert json.loads(pre_res_2.stdout) == {
        "injectSteps": [{"systemMessage": {"systemMessage": "fresh prompt context"}}]
    }


def test_posttooluse_detects_run_command_failure_and_queues_diagnostic(tmp_path: Path):
    state_dir = tmp_path / "agy-state-err"
    env = {"VEXJOY_AGY_DEFERRED_DIR": str(state_dir)}

    noop_hook = _write_hook(tmp_path, "print('{}')\n")
    post_payload = _agy_event(
        "PostToolUse",
        conversation_id="conv-err-cmd",
        tool_name="run_command",
        args={"CommandLine": "pytest"},
        toolResult={"output": "Command exited with code 1.\nFAIL: test_a", "exitCode": 1},
    )
    post_res = _run_cli(noop_hook, "PostToolUse", "open", post_payload, matcher="run_command", extra_env=env)
    assert post_res.returncode == 0
    assert json.loads(post_res.stdout) == {}

    pre_hook = _write_hook(tmp_path, 'print("ready for fixes")\n')
    pre_payload = _agy_event("PreInvocation", conversation_id="conv-err-cmd", lastUserInput="fix it")
    pre_res = _run_cli(
        pre_hook,
        "PreInvocation",
        "open",
        pre_payload,
        matcher="",
        drain_deferred=True,
        extra_env=env,
    )
    assert pre_res.returncode == 0
    pre_data = json.loads(pre_res.stdout)
    assert len(pre_data["injectSteps"]) == 1
    injected = pre_data["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "[diagnostic] Tool 'run_command' execution failed (exit code 1" in injected
    assert "ready for fixes" in injected


def test_posttooluse_detects_file_error_and_queues_diagnostic(tmp_path: Path):
    state_dir = tmp_path / "agy-state-file-err"
    env = {"VEXJOY_AGY_DEFERRED_DIR": str(state_dir)}

    noop_hook = _write_hook(tmp_path, "print('{}')\n")
    post_payload = _agy_event(
        "PostToolUse",
        conversation_id="conv-err-file",
        tool_name="edit_file",
        args={"Path": "a.py", "Target": "foo", "Replacement": "bar"},
        toolResult="Error: Target must exactly match existing file text.",
    )
    post_res = _run_cli(noop_hook, "PostToolUse", "open", post_payload, matcher="edit_file", extra_env=env)
    assert post_res.returncode == 0
    assert json.loads(post_res.stdout) == {}

    pre_hook = _write_hook(tmp_path, 'print("retry turn")\n')
    pre_payload = _agy_event("PreInvocation", conversation_id="conv-err-file", lastUserInput="retry")
    pre_res = _run_cli(
        pre_hook,
        "PreInvocation",
        "open",
        pre_payload,
        matcher="",
        drain_deferred=True,
        extra_env=env,
    )
    assert pre_res.returncode == 0
    pre_data = json.loads(pre_res.stdout)
    injected = pre_data["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "[diagnostic] Tool 'edit_file' execution failed" in injected


def test_stop_and_post_invocation_translate_continuation_decisions(adapter):
    norm_event = {"session_id": "conv-1"}
    # Stop exit 2 -> continue
    stop_cont = adapter.translate_child_result("Stop", 2, "", "unfinished goals remain", normalized_event=norm_event)
    assert stop_cont == {
        "decision": "continue",
        "reason": "unfinished goals remain",
    }

    # Stop JSON decision=block -> continue
    stop_json = json.dumps({"decision": "block", "reason": "run verification first"})
    assert adapter.translate_child_result("Stop", 0, stop_json, "", normalized_event=norm_event) == {
        "decision": "continue",
        "reason": "run verification first",
    }

    # Stop exit 0 -> allow
    assert adapter.translate_child_result("Stop", 0, "", "", normalized_event=norm_event) == {"decision": "allow"}

    # PostInvocation exit 2 -> force_continue
    post_inv = adapter.translate_child_result("PostInvocation", 2, "", "keep going", normalized_event=norm_event)
    assert post_inv == {
        "terminationBehavior": "force_continue",
    }


def test_failure_policies_on_invalid_input_and_hook_crash(tmp_path: Path):
    crashing_hook = _write_hook(tmp_path, "import sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n")
    payload = _agy_event("PreToolUse", tool_name="run_command", args={"CommandLine": "rm -rf /"})

    closed_res = _run_cli(crashing_hook, "PreToolUse", "closed", payload)
    assert closed_res.returncode == 0
    closed_data = json.loads(closed_res.stdout)
    assert closed_data["decision"] == "deny"
    assert "boom" in closed_data["reason"]

    open_res = _run_cli(crashing_hook, "PreToolUse", "open", payload)
    assert open_res.returncode == 0
    open_data = json.loads(open_res.stdout)
    assert open_data["decision"] == "allow"


def test_queue_deferred_context_handles_corrupt_json(tmp_path: Path, adapter):
    state_dir = tmp_path / "agy-state-corrupt"
    os.environ["VEXJOY_AGY_DEFERRED_DIR"] = str(state_dir)
    try:
        def_path = adapter._deferred_path("conv-corrupt")
        def_path.parent.mkdir(parents=True, exist_ok=True)
        def_path.write_text("{not valid json", encoding="utf-8")
        adapter.queue_deferred_context("conv-corrupt", "advisory message")
        # Advisory must survive a corrupt file — drain must return it.
        result = adapter.drain_deferred_context("conv-corrupt")
        assert result == ["advisory message"]
    finally:
        os.environ.pop("VEXJOY_AGY_DEFERRED_DIR", None)


def test_deferred_dir_fallback_resolution(tmp_path: Path, adapter, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # never create ~/.gemini in the real home
    custom_dir = tmp_path / "custom-deferred"
    monkeypatch.setenv("VEXJOY_AGY_DEFERRED_DIR", str(custom_dir))
    assert adapter._deferred_dir() == custom_dir

    monkeypatch.delenv("VEXJOY_AGY_DEFERRED_DIR", raising=False)
    state_root = tmp_path / "custom-state"
    monkeypatch.setenv("VEXJOY_STATE_DIR", str(state_root))
    assert adapter._deferred_dir() == state_root / "agy-deferred"

    monkeypatch.delenv("VEXJOY_STATE_DIR", raising=False)
    default_dir = adapter._deferred_dir()
    assert default_dir == tmp_path / "home" / ".gemini" / "state" / "agy-deferred"
    assert default_dir.is_dir()


# ---------------------------------------------------------------------------
# B-17: the deferred queue's last-resort directory and its parallel writers
# ---------------------------------------------------------------------------

posix_only = pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX ownership and modes")


@pytest.fixture
def no_home_queue(tmp_path: Path, monkeypatch):
    """HOME cannot hold ~/.gemini (it is a file), so the queue falls back to the temp dir."""
    import tempfile

    blocked_home = tmp_path / "home-is-a-file"
    blocked_home.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(blocked_home))
    monkeypatch.delenv("VEXJOY_AGY_DEFERRED_DIR", raising=False)
    monkeypatch.delenv("VEXJOY_STATE_DIR", raising=False)
    system_tmp = tmp_path / "system-tmp"
    system_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(system_tmp))
    return system_tmp


@posix_only
def test_fallback_queue_dir_is_per_user_and_owner_only(adapter, no_home_queue: Path):
    expected = no_home_queue / f"vexjoy-agy-deferred-{os.getuid()}"

    adapter.queue_deferred_context("conv-fallback", "advisory one")

    assert adapter._deferred_dir() == expected
    info = expected.lstat()
    assert info.st_mode & 0o777 == 0o700
    assert info.st_uid == os.getuid()
    assert not (no_home_queue / "vexjoy-agy-deferred").exists(), "no shared directory any more"
    assert adapter.drain_deferred_context("conv-fallback") == ["advisory one"]


@posix_only
def test_fallback_refuses_a_planted_symlink(adapter, no_home_queue: Path, tmp_path: Path):
    attacker = tmp_path / "attacker-readable"
    attacker.mkdir()
    for name in ("vexjoy-agy-deferred", f"vexjoy-agy-deferred-{os.getuid()}"):
        (no_home_queue / name).symlink_to(attacker, target_is_directory=True)

    adapter.queue_deferred_context("conv-symlink", "private advisory")

    assert list(attacker.iterdir()) == [], "nothing may be written through the symlink"
    assert adapter._deferred_dir() is None
    assert adapter.drain_deferred_context("conv-symlink") == []


@posix_only
def test_fallback_refuses_a_dir_owned_by_someone_else(adapter, no_home_queue: Path, monkeypatch):
    other_uid = os.getuid() + 1
    planted = no_home_queue / f"vexjoy-agy-deferred-{other_uid}"
    planted.mkdir(mode=0o700)  # owned by the real uid, not the one the adapter runs as
    monkeypatch.setattr(os, "getuid", lambda: other_uid)

    adapter.queue_deferred_context("conv-foreign", "private advisory")

    assert list(planted.iterdir()) == []
    assert adapter._deferred_dir() is None


@posix_only
def test_fallback_refuses_a_dir_open_to_others(adapter, no_home_queue: Path):
    planted = no_home_queue / f"vexjoy-agy-deferred-{os.getuid()}"
    planted.mkdir()
    planted.chmod(0o777)

    adapter.queue_deferred_context("conv-open", "private advisory")

    assert list(planted.iterdir()) == []
    assert planted.stat().st_mode & 0o777 == 0o777, "the adapter must not change modes it did not set"


def test_leftover_fixed_temp_name_does_not_drop_the_advisory(adapter, tmp_path: Path, monkeypatch):
    queue_dir = tmp_path / "queue"
    monkeypatch.setenv("VEXJOY_AGY_DEFERRED_DIR", str(queue_dir))
    path = adapter._deferred_path("conv-tmp")
    queue_dir.mkdir()
    path.with_suffix(".tmp").mkdir()  # the old shared temp name, left behind

    adapter.queue_deferred_context("conv-tmp", "kept advisory")

    assert adapter.drain_deferred_context("conv-tmp") == ["kept advisory"]
    assert [p.name for p in queue_dir.iterdir() if p.name.endswith(".tmp") and p.is_file()] == []


_QUEUE_DRIVER = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("agy_driver", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for n in range(int(sys.argv[3])):
    module.queue_deferred_context("conv-parallel", f"{sys.argv[2]}-{n}")
"""


def test_parallel_queue_writers_keep_every_message(adapter, tmp_path: Path, monkeypatch):
    queue_dir = tmp_path / "queue"
    driver = tmp_path / "driver.py"
    driver.write_text(_QUEUE_DRIVER, encoding="utf-8")
    env = {**os.environ, "VEXJOY_AGY_DEFERRED_DIR": str(queue_dir), "HOME": str(tmp_path)}
    writers, per_writer = 6, 15
    procs = [
        subprocess.Popen(
            [sys.executable, str(driver), str(ADAPTER_PATH), f"w{w}", str(per_writer)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for w in range(writers)
    ]
    for proc in procs:
        _, err = proc.communicate(timeout=60)
        assert proc.returncode == 0, err.decode()

    monkeypatch.setenv("VEXJOY_AGY_DEFERRED_DIR", str(queue_dir))
    drained = adapter.drain_deferred_context("conv-parallel")
    assert sorted(drained) == sorted(f"w{w}-{n}" for w in range(writers) for n in range(per_writer))


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl lock holder")
def test_a_held_queue_lock_is_waited_for_then_the_write_goes_ahead(adapter, tmp_path: Path, monkeypatch):
    import fcntl
    import time

    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()
    driver = tmp_path / "driver.py"
    driver.write_text(_QUEUE_DRIVER, encoding="utf-8")
    env = {**os.environ, "VEXJOY_AGY_DEFERRED_DIR": str(queue_dir), "HOME": str(tmp_path)}
    with open(queue_dir / adapter._QUEUE_LOCK_NAME, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(driver), str(ADAPTER_PATH), "held", "1"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    assert elapsed >= adapter._LOCK_WAIT_SECONDS
    monkeypatch.setenv("VEXJOY_AGY_DEFERRED_DIR", str(queue_dir))
    assert adapter.drain_deferred_context("conv-parallel") == ["held-0"]
