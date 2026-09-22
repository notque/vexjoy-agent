"""Hook index readers go through routing_index_merge (installer spec 7.2).

pretool-section-integrity-validator.py and lib/skill_directives.py prefer the
installed index and fall back to the project/runtime index. The conftest pins
VEXJOY_INDEX_DIR to a missing dir, so nothing reads the real HOME.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
LIB = HOOKS / "lib"
VALIDATOR = HOOKS / "pretool-section-integrity-validator.py"


def _w(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run_validator(project: Path, subagent: str, home: Path) -> subprocess.CompletedProcess[str]:
    event = {"tool_name": "Agent", "tool_input": {"subagent_type": subagent}, "cwd": str(project)}
    env = {**os.environ, "HOME": str(home)}
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
    assert "not found" in miss.stdout


def _runtime_helper(tmp_path: Path, name: str):
    runtime_root = tmp_path / ".claude"
    (runtime_root / "hooks").mkdir(parents=True)
    (runtime_root / "hooks" / "lib").symlink_to(LIB, target_is_directory=True)
    _w(runtime_root / "skills" / "INDEX.json", {"skills": {"process": {}}})
    spec = importlib.util.spec_from_file_location(name, runtime_root / "hooks" / "lib" / "skill_directives.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return runtime_root, module


def test_skill_directives_prefers_runtime_installed_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VEXJOY_INDEX_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    runtime_root, module = _runtime_helper(tmp_path, "sd_installed")
    installed = _w(runtime_root / "vexjoy" / "index" / "skills.json", {"skills": {"inst-skill": {}}})
    assert module._default_index_paths() == (installed,)
    assert module.skill_call_directive("inst-skill") == "Call the Skill tool with `inst-skill`."
    assert module.skill_call_directive("process") is None


def test_skill_directives_falls_back_to_runtime_skills_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VEXJOY_INDEX_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    runtime_root, module = _runtime_helper(tmp_path, "sd_fallback")
    assert module._default_index_paths() == (runtime_root / "skills" / "INDEX.json",)
