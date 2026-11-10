"""pretool-config-protection denies linter-config edits and survives malformed input.

The hook is registered in .claude/settings.json under PreToolUse
``Write|Edit|MultiEdit``; test_hook_is_registered_for_every_tool_it_checks pins that.

Run with: python3 -m pytest hooks/tests/test_pretool_config_protection.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "pretool-config-protection.py"


def _run(payload: str, tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}
    base.update({"HOME": str(tmp_path), "CLAUDE_LEARNING_DIR": str(tmp_path / "learning")})
    base.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        env=base,
        cwd=tmp_path,
        timeout=30,
    )


def _denied(result: subprocess.CompletedProcess[str]) -> bool:
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _errors() -> str:
    path = Path(os.environ["CLAUDE_HOOK_ERRORS_PATH"])
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.mark.parametrize(
    "event",
    [
        {"tool_name": "Write", "tool_input": {"file_path": "/repo/.eslintrc.json"}},
        {"tool_name": "Edit", "tool_input": {"file_path": "/repo/ruff.toml"}},
        {"tool_name": "Edit", "tool_input": json.dumps({"file_path": "/repo/ruff.toml"})},
        {"tool_name": "MultiEdit", "tool_input": {"file_path": "/repo/biome.json", "edits": [{"old_string": "a"}]}},
        {"tool_name": "MultiEdit", "tool_input": {"edits": [{"file_path": "ok.py"}, {"file_path": "setup.cfg"}]}},
        {"tool_name": "MultiEdit", "tool_input": {"edits": [None, "x", {"file_path": ".prettierrc"}]}},
    ],
    ids=["write", "edit", "edit-json-string", "multiedit-top-level", "multiedit-per-edit", "multiedit-mixed-edits"],
)
def test_protected_config_is_denied(event: dict, tmp_path: Path) -> None:
    result = _run(json.dumps(event), tmp_path)

    assert result.returncode == 0
    assert _denied(result)
    assert _errors() == ""


@pytest.mark.parametrize(
    "event",
    [
        {"tool_name": "Write", "tool_input": {"file_path": "/repo/pyproject.toml"}},
        {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/eslint.config.js.md"}},
        {"tool_name": "Read", "tool_input": {"file_path": "/repo/ruff.toml"}},
        {"tool_name": "Bash", "tool_input": {"command": "cat ruff.toml"}},
    ],
)
def test_other_files_and_tools_pass(event: dict, tmp_path: Path) -> None:
    result = _run(json.dumps(event), tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        "null",
        "[]",
        json.dumps({"tool_name": "Write", "tool_input": None}),
        json.dumps({"tool_name": "Write", "tool_input": ["ruff.toml"]}),
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": 7}}),
        json.dumps({"tool_name": "MultiEdit", "tool_input": {"edits": "ruff.toml"}}),
        json.dumps({"tool_name": "MultiEdit", "tool_input": {"edits": [3, None, {"file_path": None}]}}),
        json.dumps({"tool_name": ["Write"], "tool_input": {"file_path": "ruff.toml"}}),
    ],
)
def test_malformed_input_exits_zero_without_a_crash(payload: str, tmp_path: Path) -> None:
    result = _run(payload, tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "HOOK-ERROR" not in result.stderr
    assert _errors() == ""


def test_bypass_env_allows(tmp_path: Path) -> None:
    event = {"tool_name": "Write", "tool_input": {"file_path": "/repo/ruff.toml"}}

    result = _run(json.dumps(event), tmp_path, CONFIG_PROTECTION_BYPASS="1")

    assert result.returncode == 0
    assert result.stdout == ""


def test_denial_records_the_real_tool_name(tmp_path: Path) -> None:
    import sqlite3

    event = {"tool_name": "Edit", "session_id": "s1", "tool_input": {"file_path": "/repo/ruff.toml"}}
    assert _denied(_run(json.dumps(event), tmp_path))

    conn = sqlite3.connect(tmp_path / "learning" / "learning.db")
    try:
        rows = conn.execute("SELECT tool_name, blocked FROM governance_events").fetchall()
    finally:
        conn.close()
    assert rows == [("Edit", 1)]


def test_hook_is_registered_for_every_tool_it_checks() -> None:
    """An unregistered gate enforces nothing: pin the event, the matcher, and the command form."""
    repo = HOOK_PATH.parent.parent
    settings = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
    found = [
        (group.get("matcher"), hook)
        for group in settings["hooks"]["PreToolUse"]
        for hook in group["hooks"]
        if "pretool-config-protection.py" in hook.get("command", "")
    ]

    assert len(found) == 1
    matcher, hook = found[0]
    assert set(matcher.split("|")) == {"Write", "Edit", "MultiEdit"}
    assert hook["command"] == 'sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/pretool-config-protection.py"'
    assert hook["type"] == "command"

    allowlist = (repo / "scripts" / "hook-health-allowlist.txt").read_text(encoding="utf-8")
    assert not any(line.startswith("pretool-config-protection.py") for line in allowlist.splitlines())
