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
