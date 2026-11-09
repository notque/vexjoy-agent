#!/usr/bin/env python3
"""A crash in the unified gate stays fail-open but is now recorded (B-10).

The top-level handler used to print one stderr line and allow the tool call.
Claude Code does not show PreToolUse stderr on exit 0, so a crash bug could
switch off every check in the gate without anyone seeing it. The handler now
also calls hook_error(), which appends to hook-errors.jsonl where
validate-hook-health reports repeat offenders. Whether a crash should block
instead (B-15) is the owner's call; this keeps the allow.

Malformed input (a null or non-object ``tool_input``, a non-object event) is not
a crash: the gate reads it as empty. A ``tool_input`` sent as a string still
reaches every check.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate_crash.py -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "pretool-unified-gate.py"

_spec = importlib.util.spec_from_file_location("pretool_unified_gate_crash", HOOK_PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

# Runs the gate as __main__ with read_stdin replaced by a function that raises, so
# the top-level handler sees a crash that no input handling can absorb.
_CRASH_WRAPPER = """
import runpy, sys
sys.path.insert(0, {lib!r})
import stdin_timeout

def _boom(*args, **kwargs):
    raise RuntimeError("simulated gate crash")

stdin_timeout.read_stdin = _boom
runpy.run_path({hook!r}, run_name="__main__")
"""

_BASH_CHECKS = (
    "check_gitignore_bypass",
    "check_git_submission",
    "check_dangerous_command",
    "check_public_dev_server",
    "check_sysadmin_security",
    "check_sensitive_bash",
)


def _run(args: list[str], payload: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path), "CLAUDE_LEARNING_DIR": str(tmp_path / "learning")},
        cwd=tmp_path,
        timeout=30,
    )


def _error_entries() -> list[dict]:
    errors = Path(os.environ["CLAUDE_HOOK_ERRORS_PATH"])
    if not errors.exists():
        return []
    return [json.loads(line) for line in errors.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_crash_is_recorded_and_still_allows(tmp_path: Path) -> None:
    wrapper = tmp_path / "crash_wrapper.py"
    wrapper.write_text(
        _CRASH_WRAPPER.format(lib=str(HOOK_PATH.parent / "lib"), hook=str(HOOK_PATH)),
        encoding="utf-8",
    )

    result = _run([str(wrapper)], "{}", tmp_path)

    assert result.returncode == 0
    assert result.stdout == "", "a crash must not emit a decision (fail-open)"
    assert "[unified-gate] HOOK-CRASH: RuntimeError" in result.stderr
    assert [(e["hook"], e["type"]) for e in _error_entries()] == [("pretool-unified-gate", "RuntimeError")]


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[]",
        "42",
        '"a string"',
        json.dumps({"tool_name": "Bash", "tool_input": None}),
        json.dumps({"tool_name": "Bash", "tool_input": ["not", "an", "object"]}),
        json.dumps({"tool_name": "Bash", "tool_input": 7}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": None}}),
        json.dumps({"tool_name": "Bash", "tool_input": {"command": ["echo", "hi"]}}),
        json.dumps({"tool_name": "Bash"}),
        json.dumps({"tool_name": "Write", "tool_input": None, "cwd": 5}),
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": 12}}),
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": None}}),
        json.dumps({"tool_name": "Read", "tool_input": []}),
        json.dumps({"tool_name": ["Bash"], "tool_input": None}),
    ],
)
def test_malformed_input_does_not_crash(payload: str, tmp_path: Path) -> None:
    """Malformed input has nothing to check: exit 0, no decision, and no crash recorded."""
    result = _run([str(HOOK_PATH)], payload, tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "HOOK-CRASH" not in result.stderr
    assert _error_entries() == []


def _checked_commands(event: dict) -> dict[str, list[str]]:
    """Run main() in-process with every Bash check replaced by a recorder."""
    seen: dict[str, list[str]] = {name: [] for name in _BASH_CHECKS}
    patches = [patch.object(gate, name, side_effect=seen[name].append) for name in _BASH_CHECKS]
    with (
        patch.object(gate, "read_stdin", return_value=json.dumps(event)),
        patch("sys.stdout", io.StringIO()),
        patch("sys.stderr", io.StringIO()),
    ):
        for p in patches:
            p.start()
        try:
            gate.main()
        finally:
            for p in patches:
                p.stop()
    return seen


@pytest.mark.parametrize(
    "tool_input",
    [
        {"command": "echo hi"},
        "echo hi",
        json.dumps({"command": "echo hi"}),
    ],
    ids=["object", "bare-string", "json-string"],
)
def test_every_bash_check_sees_the_command(tool_input: object) -> None:
    """A tool_input sent as a string is checked like an object, not skipped."""
    seen = _checked_commands({"tool_name": "Bash", "tool_input": tool_input})

    assert seen == {name: ["echo hi"] for name in _BASH_CHECKS}


@pytest.mark.parametrize("tool_input", [None, [], 7, {"command": None}, {"command": ["echo", "hi"]}])
def test_malformed_bash_input_reaches_no_check(tool_input: object) -> None:
    seen = _checked_commands({"tool_name": "Bash", "tool_input": tool_input})

    assert seen == {name: [] for name in _BASH_CHECKS}


def test_input_key_is_read_when_tool_input_is_null() -> None:
    """The legacy ``input`` key still carries the command when ``tool_input`` is null."""
    seen = _checked_commands({"tool_name": "Bash", "tool_input": None, "input": {"command": "echo hi"}})

    assert seen["check_dangerous_command"] == ["echo hi"]
