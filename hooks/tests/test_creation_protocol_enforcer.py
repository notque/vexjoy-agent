#!/usr/bin/env python3
"""Tests for the creation-protocol-enforcer PreToolUse:Agent hook.

Claude Code does not show plain PreToolUse stdout to anyone, so the warning
the hook printed never reached the model (B-03). It now arrives as
hookSpecificOutput.additionalContext and still never blocks: no
permissionDecision is emitted.

Run with: python3 -m pytest hooks/tests/test_creation_protocol_enforcer.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "creation-protocol-enforcer.py"


def _run(tmp_path: Path, prompt: str, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "cwd": str(tmp_path),
        "tool_input": {"prompt": prompt, "description": "dispatch"},
    }
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    env.pop("ADR_PROTOCOL_BYPASS", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
    )


def test_warning_reaches_the_model_without_a_permission_decision(tmp_path: Path) -> None:
    result = _run(tmp_path, "Create a new skill for release notes")

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}
    inner = output["hookSpecificOutput"]
    assert inner["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in inner
    context = inner["additionalContext"]
    assert "[creation-protocol-enforcer] Creation request detected" in context
    assert "ADR_PROTOCOL_BYPASS=1" in context


def test_recent_adr_session_stays_silent(tmp_path: Path) -> None:
    (tmp_path / ".adr-session.json").write_text("{}", encoding="utf-8")

    result = _run(tmp_path, "Create a new skill for release notes")

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("prompt", "env_extra"),
    [
        ("Review the open pull request", None),
        ("Create a new skill for release notes", {"ADR_PROTOCOL_BYPASS": "1"}),
    ],
    ids=["no-creation-keyword", "bypass"],
)
def test_non_creation_and_bypass_stay_silent(tmp_path: Path, prompt: str, env_extra: dict | None) -> None:
    result = _run(tmp_path, prompt, env_extra)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
