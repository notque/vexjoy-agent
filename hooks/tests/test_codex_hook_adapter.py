"""Tests for the Codex-to-VexJoy hook compatibility adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / "hooks" / "codex-hook-adapter.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("codex_hook_adapter", ADAPTER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def adapter():
    return _load_adapter()


def _event(event: str = "PreToolUse", **extra: object) -> dict:
    payload = {
        "hook_event_name": event,
        "session_id": "session-123",
        "cwd": str(ROOT),
        "tool_name": "apply_patch",
        "tool_input": {},
    }
    payload.update(extra)
    return payload


def _run_cli(
    hook: Path,
    event: str,
    mode: str,
    failure_policy: str,
    payload: dict | str,
    *,
    matcher: str = "Write|Edit",
    timeout: float = 2,
) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [
            sys.executable,
            str(ADAPTER_PATH),
            "--hook",
            str(hook),
            "--event",
            event,
            "--matcher",
            matcher,
            "--mode",
            mode,
            "--failure-policy",
            failure_policy,
            "--timeout",
            str(timeout),
        ],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )


def _write_hook(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "child-hook.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_apply_patch_handles_add_update_move_delete_and_spaces(adapter):
    patch = """*** Begin Patch
*** Add File: docs/new guide.md
+first
+second
*** Update File: src/current.py
@@
-old
+new
 context
*** End of File
*** Update File: src/old name.py
*** Move to: src/new name.py
@@
-before
+after
*** Delete File: obsolete/data.txt
*** End Patch"""

    edits = adapter.parse_apply_patch(patch)

    assert [(item.tool_name, item.file_path) for item in edits] == [
        ("Write", "docs/new guide.md"),
        ("Edit", "src/current.py"),
        ("Edit", "src/old name.py"),
        ("Write", "src/new name.py"),
        ("Edit", "obsolete/data.txt"),
    ]
    assert edits[0].tool_input == {
        "file_path": "docs/new guide.md",
        "content": "first\nsecond\n",
    }
    assert edits[1].tool_input == {
        "file_path": "src/current.py",
        "old_string": "old\ncontext\n",
        "new_string": "new\ncontext\n",
    }
    assert edits[2].tool_input["old_string"] == "before\n"
    assert edits[2].tool_input["new_string"] == "after\n"
    assert edits[3].tool_input == {
        "file_path": "src/new name.py",
        "content": "after\n",
    }
    assert edits[4].tool_input == {
        "file_path": "obsolete/data.txt",
        "old_string": "",
        "new_string": "",
    }


@pytest.mark.parametrize(
    "patch",
    [
        "not a patch",
        "*** Begin Patch\n*** Add File: x\n+data",
        "*** Begin Patch\n*** Unknown File: x\n*** End Patch",
        "*** Begin Patch\n*** Add File:\n+x\n*** End Patch",
        "*** Begin Patch\n*** Add File: x\nraw\n*** End Patch",
    ],
)
def test_parse_apply_patch_rejects_ambiguous_input(adapter, patch):
    with pytest.raises(adapter.PatchParseError):
        adapter.parse_apply_patch(patch)


def test_prompt_transcript_and_common_compatibility_mappings(adapter):
    prompt = _event("UserPromptSubmit", prompt="review this", tool_input={})
    prompt_normalized = adapter.normalize_event(prompt, mode="prompt")
    assert prompt_normalized["prompt"] == "review this"
    assert prompt_normalized["userMessage"] == "review this"
    assert prompt_normalized["tool_input"]["prompt"] == "review this"

    stop = _event(
        "SubagentStop",
        agent_transcript_path="/tmp/agent transcript.jsonl",
        transcript_path="/tmp/parent.jsonl",
    )
    stop_normalized = adapter.normalize_event(stop, mode="subagent-stop")
    assert stop_normalized["transcript_path"] == "/tmp/agent transcript.jsonl"

    env = adapter.compatibility_environment(prompt)
    assert env["CLAUDE_PROJECT_DIR"] == str(ROOT)
    assert env["CLAUDE_SESSION_ID"] == "session-123"
    assert os.environ.keys() <= env.keys()


def test_patch_mode_filters_normalized_events_by_original_matcher(adapter):
    payload = _event(
        tool_input={
            "command": "*** Begin Patch\n*** Add File: a.py\n+x\n*** Update File: b.py\n@@\n-x\n+y\n*** End Patch"
        }
    )

    write_only = adapter.build_invocations(payload, mode="patch", matcher="^Write$")
    edit_only = adapter.build_invocations(payload, mode="patch", matcher="^Edit$")

    assert [(item["tool_name"], item["tool_input"]["file_path"]) for item in write_only] == [("Write", "a.py")]
    assert [(item["tool_name"], item["tool_input"]["file_path"]) for item in edit_only] == [("Edit", "b.py")]
    assert payload["tool_name"] == "apply_patch"


@pytest.mark.parametrize(
    ("event", "text", "expected"),
    [
        (
            "SessionStart",
            "session context",
            {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "session context"}},
        ),
        (
            "UserPromptSubmit",
            "prompt context",
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "prompt context",
                }
            },
        ),
        (
            "PostToolUse",
            "test warning",
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "test warning"}},
        ),
        ("PreCompact", "archive note", {"systemMessage": "archive note"}),
        ("PostCompact", "compact note", {"systemMessage": "compact note"}),
        ("SubagentStop", "agent note", {"systemMessage": "agent note"}),
        ("Stop", "summary note", {"systemMessage": "summary note"}),
    ],
)
def test_plain_output_is_normalized_for_each_event(adapter, event, text, expected):
    assert adapter.normalize_output(event, text, "") == expected


def test_claude_json_is_translated_and_codex_json_passes_through(adapter):
    claude_context = json.dumps({"additionalContext": "context"})
    assert adapter.normalize_output("PostToolUse", claude_context, "") == {
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "context"}
    }

    deny = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "blocked",
        }
    }
    assert adapter.normalize_output("PreToolUse", json.dumps(deny), "") == deny

    subagent_deny = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "permissionDecision": "deny",
            "permissionDecisionReason": "finish tests",
        }
    }
    assert adapter.normalize_output("SubagentStop", json.dumps(subagent_deny), "") == {
        "decision": "block",
        "reason": "finish tests",
    }


def test_empty_success_is_valid_json_for_json_required_events(adapter):
    assert adapter.normalize_output("Stop", "", "") == {}
    assert adapter.normalize_output("SubagentStop", "", "") == {}


def test_aggregate_deduplicates_in_first_seen_order_and_deny_wins(adapter):
    results = [
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "shared\nfirst",
            },
            "systemMessage": "warning",
        },
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "blocked b.py",
                "additionalContext": "shared\nsecond",
            }
        },
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "blocked b.py",
            },
            "systemMessage": "warning",
        },
    ]

    combined = adapter.aggregate_outputs("PreToolUse", results)

    assert combined == {
        "systemMessage": "warning",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "blocked b.py",
            "additionalContext": "shared\nfirst\nsecond",
        },
    }


def test_aggregate_continue_false_precedes_stop_continuation(adapter):
    combined = adapter.aggregate_outputs(
        "Stop",
        [
            {"decision": "block", "reason": "continue tests"},
            {"continue": False, "stopReason": "stop now"},
        ],
    )

    assert combined == {"continue": False, "stopReason": "stop now"}


def test_exit_two_becomes_event_specific_enforcement(adapter):
    assert adapter.result_from_exit("PreToolUse", 2, "", "blocked edit") == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "blocked edit",
        }
    }
    assert adapter.result_from_exit("UserPromptSubmit", 2, "", "blocked prompt") == {
        "decision": "block",
        "reason": "blocked prompt",
    }
    assert adapter.result_from_exit("Stop", 2, "", "continue work") == {
        "decision": "block",
        "reason": "continue work",
    }
    assert adapter.result_from_exit("PostToolUse", 2, "", "review result") == {
        "decision": "block",
        "reason": "review result",
    }


def test_child_receives_normalized_json_environment_and_session_cwd(tmp_path):
    hook = _write_hook(
        tmp_path,
        """import json, os, sys
event = json.load(sys.stdin)
print(json.dumps({"additionalContext": "|".join([
    event["tool_input"]["prompt"], event["userMessage"],
    os.environ["CLAUDE_PROJECT_DIR"], os.environ["CLAUDE_SESSION_ID"], os.getcwd()
])}))
""",
    )
    payload = _event("UserPromptSubmit", prompt="hello", tool_input={})

    result = _run_cli(hook, "UserPromptSubmit", "prompt", "closed", payload)

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert context == f"hello|hello|{ROOT}|session-123|{ROOT}"


def test_patch_cli_invokes_child_once_per_affected_file_and_aggregates(tmp_path):
    hook = _write_hook(
        tmp_path,
        """import json, sys
event = json.load(sys.stdin)
path = event["tool_input"]["file_path"]
print(json.dumps({"additionalContext": f"checked:{event['tool_name']}:{path}"}))
""",
    )
    payload = _event(
        tool_input={
            "command": "*** Begin Patch\n*** Add File: one file.py\n+x\n*** Update File: two.py\n@@\n-a\n+b\n*** Delete File: gone.py\n*** End Patch"
        }
    )

    result = _run_cli(hook, "PreToolUse", "patch", "closed", payload)

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["additionalContext"] == (
        "checked:Write:one file.py\nchecked:Edit:two.py\nchecked:Edit:gone.py"
    )


@pytest.mark.parametrize("failure_policy", ["open", "closed"])
def test_patch_parse_failure_obeys_explicit_policy(tmp_path, failure_policy):
    hook = _write_hook(tmp_path, "raise AssertionError('child must not run')\n")
    payload = _event(tool_input={"command": "not a patch"})

    result = _run_cli(hook, "PreToolUse", "patch", failure_policy, payload)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    message = json.dumps(output)
    assert "apply_patch" in message
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    assert decision == ("deny" if failure_policy == "closed" else None)


@pytest.mark.parametrize("failure_policy", ["open", "closed"])
def test_timeout_obeys_explicit_policy(tmp_path, failure_policy):
    hook = _write_hook(tmp_path, "import time\ntime.sleep(1)\n")

    result = _run_cli(
        hook,
        "PreToolUse",
        "native",
        failure_policy,
        _event("PreToolUse", tool_name="Bash"),
        timeout=0.02,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "timed out" in json.dumps(output).lower()
    decision = output.get("hookSpecificOutput", {}).get("permissionDecision")
    assert decision == ("deny" if failure_policy == "closed" else None)


@pytest.mark.parametrize("body", ["print('not-json')\n", "raise RuntimeError('boom')\n"])
def test_ambiguous_child_result_is_visible_and_fail_closed(tmp_path, body):
    hook = _write_hook(tmp_path, body)

    result = _run_cli(hook, "PreToolUse", "native", "closed", _event("PreToolUse", tool_name="Bash"))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "adapter" in output["hookSpecificOutput"]["permissionDecisionReason"].lower()


def test_malformed_adapter_input_is_visible_without_traceback(tmp_path):
    hook = _write_hook(tmp_path, "raise AssertionError('child must not run')\n")

    result = _run_cli(hook, "Stop", "stop", "open", "not-json")

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "invalid" in output["systemMessage"].lower()
    assert "traceback" not in result.stderr.lower()
