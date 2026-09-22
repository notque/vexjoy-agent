"""posttooluse-sync-skill-index.py: engine index-only refresh, never a repo write (spec 7.3)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "posttooluse-sync-skill-index.py"
SCRIPTS = HOOK.parent.parent / "scripts"
SOURCE_INDEX = HOOK.parent.parent / "skills" / "INDEX.json"
sys.path.insert(0, str(SCRIPTS / "tests"))
sys.path.insert(0, str(SCRIPTS))

from vexinstall_support import assert_repo_clean, make_world


def _run(event: dict, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        env=env,
        timeout=60,
    )


def test_no_engine_target_writes_nothing(tmp_path: Path) -> None:
    skill = tmp_path / "proj" / "skills" / "testing" / "isolated-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: isolated-skill\ndescription: fixture.\n---\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    before = SOURCE_INDEX.read_bytes() if SOURCE_INDEX.exists() else None
    env = {**os.environ, "HOME": str(home)}
    result = _run({"cwd": str(tmp_path / "proj"), "tool_input": {"file_path": str(skill)}}, env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not (tmp_path / "proj" / "skills" / "INDEX.json").exists(), "hook must not write into the project"
    assert not (home / ".claude" / "vexjoy" / "index").exists()
    after = SOURCE_INDEX.read_bytes() if SOURCE_INDEX.exists() else None
    assert after == before


def test_engine_target_refreshes_installed_index_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    world = make_world(tmp_path, monkeypatch)
    assert world.run("apply", "--target", "claude").code == 0
    index = world.home / ".claude" / "vexjoy" / "index" / "skills.json"
    index.unlink()
    skill_md = world.repo / "skills" / "meta" / "alpha" / "SKILL.md"
    env = {
        **os.environ,
        "HOME": str(world.home),
        "VEXINSTALL_SOURCE_ROOT": str(world.repo),
    }
    result = _run({"cwd": str(world.repo), "tool_input": {"file_path": str(skill_md)}}, env)
    assert result.returncode == 0, result.stderr
    assert "[sync-skill-index] installed index refreshed (claude)" in result.stdout, result.stderr
    assert "alpha" in json.loads(index.read_text(encoding="utf-8"))["skills"]
    assert not (world.repo / "skills" / "INDEX.json").exists()
    assert_repo_clean(world.repo)


def test_non_skill_path_is_silent(tmp_path: Path) -> None:
    result = _run({"tool_input": {"file_path": "src/app.py"}}, {**os.environ, "HOME": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


def test_malformed_input_exits_zero() -> None:
    result = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
