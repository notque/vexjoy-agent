"""Hook index readers go through routing_index_merge (installer spec 7.2).

pretool-section-integrity-validator.py prefers the installed index and falls
back to the project/runtime index. The conftest pins VEXJOY_INDEX_DIR to a
missing dir, so nothing reads the real HOME.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
VALIDATOR = HOOKS / "pretool-section-integrity-validator.py"


def _w(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run_validator(project: Path, subagent: str, home: Path) -> subprocess.CompletedProcess[str]:
    event = {"tool_name": "Agent", "tool_input": {"subagent_type": subagent}, "cwd": str(project)}
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    env.pop("VEXJOY_INDEX_TARGET", None)
    return subprocess.run(
        [sys.executable, str(VALIDATOR)], input=json.dumps(event), capture_output=True, text=True, env=env, timeout=30
    )


def test_section_integrity_accepts_agent_from_installed_index(tmp_path: Path, monkeypatch) -> None:
    index_dir = tmp_path / "installed"
    _w(index_dir / "agents.json", {"agents": {"inst-agent": {}}})
    _w(index_dir / "skills.json", {"skills": {"inst-skill": {}}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index_dir))
    project = tmp_path / "project"
    project.mkdir()
    ok = _run_validator(project, "inst-agent", tmp_path)
    assert ok.returncode == 0
    assert ok.stdout.strip() == ""
    skill = _run_validator(project, "inst-skill", tmp_path)
    assert skill.returncode == 0
    assert "is a skill name" in skill.stdout


def test_section_integrity_falls_back_to_project_index(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _w(project / "agents" / "INDEX.json", {"agents": {"repo-agent": {}}})
    _w(project / "agents" / "INDEX.local.json", {"agents": {"local-agent": {}}})
    for name in ("repo-agent", "local-agent"):
        res = _run_validator(project, name, tmp_path)
        assert res.returncode == 0
        assert res.stdout.strip() == "", name
    miss = _run_validator(project, "no-such-agent", tmp_path)
    assert miss.returncode == 0
    assert "may cause a dispatch failure" in miss.stdout


@pytest.mark.parametrize("name", ["fork", "Explore", "plan", "general-purpose", "claude-code-guide", "web-fetch"])
def test_section_integrity_accepts_harness_builtins(tmp_path: Path, name: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    res = _run_validator(project, name, tmp_path)
    assert res.returncode == 0
    assert res.stdout.strip() == "", name


def test_section_integrity_flags_a_retired_agent_even_in_a_stale_index(tmp_path: Path, monkeypatch) -> None:
    """A pre-retirement install still lists the specialist agents; they no longer validate."""
    index_dir = tmp_path / "installed"
    _w(index_dir / "agents.json", {"agents": {"golang-general-engineer": {}, "acme-overlay-engineer": {}}})
    _w(index_dir / "skills.json", {"skills": {"programming": {}}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index_dir))
    project = tmp_path / "project"
    project.mkdir()
    retired = _run_validator(project, "golang-general-engineer", tmp_path)
    assert retired.returncode == 0
    assert "retired agent" in retired.stdout and "general-purpose" in retired.stdout
    overlay = _run_validator(project, "acme-overlay-engineer", tmp_path)
    assert overlay.stdout.strip() == ""
