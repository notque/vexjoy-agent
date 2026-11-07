#!/usr/bin/env python3
"""Tests for the posttool-skill-frontmatter-check PostToolUse hook.

Claude Code shows plain PostToolUse stdout only in the transcript view
(ctrl+o); the model reads hookSpecificOutput.additionalContext. The hook used
to print its validation errors as plain text, so they never reached the model
(B-03).

Run with: python3 -m pytest hooks/tests/test_posttool_skill_frontmatter_check.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "posttool-skill-frontmatter-check.py"


def _run(file_path: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"success": True},
    }
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    env.pop("POSTTOOL_SKILL_FRONTMATTER_CHECK_BYPASS", None)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
    )


def test_validation_errors_reach_the_model_as_additional_context(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Missing frontmatter\n", encoding="utf-8")

    result = _run(skill, tmp_path)

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert set(output) == {"hookSpecificOutput"}
    inner = output["hookSpecificOutput"]
    assert inner["hookEventName"] == "PostToolUse"
    context = inner["additionalContext"]
    assert "[skill-frontmatter] Validation failed for SKILL.md:" in context
    assert "No YAML frontmatter found" in context
    assert context.rstrip().endswith("[skill-frontmatter] Fix frontmatter before proceeding.")


def test_valid_skill_is_silent(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: demo\ndescription: Use when checking the frontmatter hook stays quiet on a valid skill.\n"
        "routing:\n  triggers:\n    - demo frontmatter\n  category: meta\n---\n\n# Demo\n",
        encoding="utf-8",
    )

    result = _run(skill, tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_non_skill_file_is_silent(tmp_path: Path) -> None:
    other = tmp_path / "docs" / "notes.md"
    other.parent.mkdir(parents=True)
    other.write_text("# Notes\n", encoding="utf-8")

    result = _run(other, tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
