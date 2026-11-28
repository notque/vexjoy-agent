#!/usr/bin/env python3
"""Unit tests for hooks/pretool-section-integrity-validator.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
VALIDATOR = HOOKS_DIR / "pretool-section-integrity-validator.py"
AGY_ADAPTER = HOOKS_DIR / "agy-hook-adapter.py"


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _seed_index(tmp_path: Path) -> tuple[Path, Path]:
    """Create isolated installed index (with 'research' and 'debugging' skills) and project dir."""
    index_dir = tmp_path / "installed-index"
    _write_json(index_dir / "agents.json", {"agents": {}})
    _write_json(index_dir / "skills.json", {"skills": {"research": {}, "debugging": {}}})
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    return index_dir, project


def _clean_env(tmp_path: Path, index_dir: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "VEXJOY_HOOK_RUNTIME",
            "ANTIGRAVITY_AGENT",
            "VEXJOY_INDEX_TARGET",
            "PRETOOL_SECTION_INTEGRITY_VALIDATOR_BYPASS",
            "CLAUDE_HOOKS_DEBUG",
        }
    }
    env.update(
        {
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "VEXJOY_INDEX_DIR": str(index_dir),
            "CLAUDE_HOOK_ERRORS_PATH": str(tmp_path / "hook-errors.jsonl"),
        }
    )
    if extra:
        env.update(extra)
    return env


def _run_validator(
    tmp_path: Path,
    subagent_type: str,
    *,
    env_extra: dict[str, str] | None = None,
    event_extra: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    index_dir, project = _seed_index(tmp_path)
    event: dict = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": subagent_type},
        "cwd": str(project),
    }
    if event_extra:
        event.update(event_extra)
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=_clean_env(tmp_path, index_dir, env_extra),
        timeout=30,
    )


@pytest.mark.parametrize("subagent_type", ["self", "research", "image-generator", "Research", "SELF"])
@pytest.mark.parametrize(
    ("env_extra", "event_extra"),
    [
        ({"VEXJOY_HOOK_RUNTIME": "antigravity"}, None),
        ({"ANTIGRAVITY_AGENT": "1"}, None),
        (None, {"agy_tool_name": "invoke_subagent"}),
    ],
    ids=["vexjoy-hook-runtime", "antigravity-agent-env", "agy-tool-name"],
)
def test_antigravity_builtin_subagents_allowed_silently(
    tmp_path: Path,
    subagent_type: str,
    env_extra: dict[str, str] | None,
    event_extra: dict | None,
) -> None:
    """Antigravity built-ins bypass the skill-name warning even though 'research' is also a skill."""
    result = _run_validator(tmp_path, subagent_type, env_extra=env_extra, event_extra=event_extra)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"expected silent allow for {subagent_type!r}, got: {result.stdout!r}"


def test_antigravity_still_warns_on_non_builtin_skill_or_unknown(tmp_path: Path) -> None:
    """Antigravity detection only adds AGY_BUILTIN_AGENTS; other skills and typos still warn."""
    skill_res = _run_validator(tmp_path, "debugging", env_extra={"VEXJOY_HOOK_RUNTIME": "antigravity"})
    assert skill_res.returncode == 0
    assert "is a skill name" in skill_res.stdout

    unknown_res = _run_validator(tmp_path, "nonexistent-worker", env_extra={"VEXJOY_HOOK_RUNTIME": "antigravity"})
    assert unknown_res.returncode == 0
    assert "may cause a dispatch failure" in unknown_res.stdout


def test_claude_code_still_warns_on_research_skill_and_agy_builtins(tmp_path: Path) -> None:
    """Under Claude Code (no Antigravity markers), 'research' warns as a skill and 'self'/'image-generator' warn."""
    research_res = _run_validator(tmp_path, "research")
    assert research_res.returncode == 0
    assert "is a skill name" in research_res.stdout

    for agy_only in ("self", "image-generator"):
        res = _run_validator(tmp_path, agy_only)
        assert res.returncode == 0
        assert "may cause a dispatch failure" in res.stdout, agy_only


def test_claude_code_builtins_allowed_silently(tmp_path: Path) -> None:
    for name in ("general-purpose", "Explore", "plan"):
        res = _run_validator(tmp_path, name)
        assert res.returncode == 0
        assert res.stdout.strip() == "", name


def test_agy_hook_adapter_allows_research_without_queuing_warning(tmp_path: Path) -> None:
    """End-to-end through agy-hook-adapter.py: invoke_subagent(TypeName='research') emits allow and queues nothing."""
    index_dir, project = _seed_index(tmp_path)
    deferred_dir = tmp_path / "deferred"
    payload = {
        "hookEventName": "PreToolUse",
        "conversationId": "conv-section-integrity",
        "workspacePaths": [str(project)],
        "toolCall": {
            "name": "invoke_subagent",
            "id": "call-1",
            "args": {"TypeName": "research", "Role": "Scout", "Prompt": "Find references"},
        },
    }
    env = _clean_env(tmp_path, index_dir, {"VEXJOY_AGY_DEFERRED_DIR": str(deferred_dir)})
    result = subprocess.run(
        [
            sys.executable,
            str(AGY_ADAPTER),
            "--hook",
            str(VALIDATOR),
            "--event",
            "PreToolUse",
            "--matcher",
            "invoke_subagent",
            "--failure-policy",
            "open",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"decision": "allow"}
    assert not list(deferred_dir.glob("deferred-*.json"))
