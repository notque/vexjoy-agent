#!/usr/bin/env python3
"""Tests for the error-learner PostToolUse hook.

The hook must gate learning capture on the payload's actual failure
signals (is_error flag, error field, non-zero exitCode) — never on
keyword matches against successful stdout. Audit found ~135 false
learning rows in 24h from successful commands whose output merely
mentioned "error", "timeout", or "not found".

Run with: python3 -m pytest hooks/tests/test_error_learner.py -v
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

HOOK_PATH = Path(__file__).parent.parent / "error-learner.py"
LIB_PATH = Path(__file__).parent.parent / "lib"

# ---------------------------------------------------------------------------
# Import the module under test (for unit tests of detect_error)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(LIB_PATH))

spec = importlib.util.spec_from_file_location("error_learner", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# detect_error: failure-signal gate
# ---------------------------------------------------------------------------


def test_success_with_error_keywords_not_detected():
    """Successful command whose stdout mentions error keywords records nothing."""
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_result": {
            "output": "abc123 fix: retry timeout error\ndef456 handle file not found",
            "is_error": False,
        },
    }
    has_error, message = mod.detect_error(event)
    assert has_error is False
    assert message == ""


def test_success_without_flags_not_detected():
    """No is_error / error / exitCode signal means success, whatever stdout says."""
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_result": {"output": "ls: scan-error.py test-timeout.py notfound.md"},
    }
    has_error, message = mod.detect_error(event)
    assert has_error is False
    assert message == ""


def test_failure_error_field_detected():
    """Explicit error field is a genuine failure."""
    event = {
        "tool_name": "Read",
        "tool_result": {"is_error": True, "error": "No such file or directory: foo.txt"},
    }
    has_error, message = mod.detect_error(event)
    assert has_error is True
    assert "No such file" in message


def test_failure_exitcode_detected_factory_schema():
    """Factory schema: non-zero exitCode with stderr is a genuine failure."""
    event = {
        "tool_name": "Bash",
        "tool_response": {"exitCode": 1, "stderr": "Permission denied", "stdout": ""},
    }
    has_error, message = mod.detect_error(event)
    assert has_error is True
    assert "Permission denied" in message


def test_failure_is_error_flag_uses_output():
    """is_error=True with no error field falls back to output text."""
    event = {
        "tool_name": "Bash",
        "tool_result": {"is_error": True, "output": "Traceback (most recent call last): ValueError"},
    }
    has_error, message = mod.detect_error(event)
    assert has_error is True
    assert "Traceback" in message


def test_failure_without_any_text_records_nothing():
    """Failure with no error text gives the learner nothing to store."""
    event = {"tool_name": "Bash", "tool_result": {"is_error": True, "output": ""}}
    has_error, message = mod.detect_error(event)
    assert has_error is False
    assert message == ""


def test_empty_event_safe():
    has_error, message = mod.detect_error({})
    assert has_error is False
    assert message == ""


# ---------------------------------------------------------------------------
# Full hook runs (subprocess, isolated HOME + CLAUDE_LEARNING_DIR)
# ---------------------------------------------------------------------------


def _run_hook(stdin_text: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Run the hook with all on-disk state redirected into tmp_path."""
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)  # feedback_tracker state under tmp HOME
    env["CLAUDE_LEARNING_DIR"] = str(tmp_path / "learning")
    env.pop("CLAUDE_HOOKS_DEBUG", None)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _learner_rows(tmp_path: Path) -> list[tuple]:
    """Rows the hook wrote to the isolated learning DB."""
    db = tmp_path / "learning" / "learning.db"
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT error_type, value FROM learnings WHERE source = 'hook:error-learner'").fetchall()
    finally:
        conn.close()


def _event(tool_result: dict, tool_name: str = "Bash") -> str:
    return json.dumps({"hook_event_name": "PostToolUse", "tool_name": tool_name, "tool_result": tool_result})


def test_hook_successful_command_records_nothing(tmp_path):
    """The audit scenario: successful git log mentioning timeout/error/not found."""
    stdout = "a1b2c3 fix: connection timeout error\n9f8e7d docs: file not found page"
    result = _run_hook(_event({"output": stdout, "is_error": False}), tmp_path)
    assert result.returncode == 0
    assert "[new-error]" not in result.stdout
    assert "[learned-solution]" not in result.stdout
    assert _learner_rows(tmp_path) == []


def test_hook_failed_command_records_with_classification(tmp_path):
    """Genuine failure still captures, classified correctly."""
    result = _run_hook(
        _event({"is_error": True, "error": "No such file or directory: foo.txt"}, "Read"),
        tmp_path,
    )
    assert result.returncode == 0
    assert "[new-error]" in result.stdout
    rows = _learner_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0][0] == "missing_file"
    assert "No such file" in rows[0][1]


def test_hook_empty_stdin_safe(tmp_path):
    result = _run_hook("", tmp_path)
    assert result.returncode == 0
    assert _learner_rows(tmp_path) == []


def test_hook_malformed_json_safe(tmp_path):
    result = _run_hook("{not valid json", tmp_path)
    assert result.returncode == 0
    assert _learner_rows(tmp_path) == []


def test_hook_non_posttooluse_ignored(tmp_path):
    payload = json.dumps({"hook_event_name": "SessionStart"})
    result = _run_hook(payload, tmp_path)
    assert result.returncode == 0
    assert _learner_rows(tmp_path) == []
