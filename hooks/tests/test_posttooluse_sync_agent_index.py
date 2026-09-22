#!/usr/bin/env python3
"""
Tests for hooks/posttooluse-sync-agent-index.py.

ADR: agents-index-autosync (Part 1). The hook mirrors the skill-index hook:
on Write|Edit of agents/*.md it regenerates agents/INDEX.json. It must always
exit 0, stay silent + fast on non-matching paths, and exclude INDEX.md/README.md.

Run with: python3 -m pytest hooks/tests/test_posttooluse_sync_agent_index.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "posttooluse-sync-agent-index.py"
REPO_ROOT = HOOK.parent.parent
AGENTS_INDEX = REPO_ROOT / "agents" / "INDEX.json"


def run_hook(event_obj_or_str, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    payload = event_obj_or_str if isinstance(event_obj_or_str, str) else json.dumps(event_obj_or_str)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# Agent edit: engine index-only refresh, never a repo write (spec 7.3)
# ---------------------------------------------------------------------------


def test_agent_edit_without_engine_target_writes_nothing(tmp_path: Path) -> None:
    import os

    agent = tmp_path / "agents" / "isolated-agent.md"
    agent.parent.mkdir()
    agent.write_text("---\nname: isolated-agent\ndescription: Isolated agent fixture.\n---\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    before = AGENTS_INDEX.read_bytes() if AGENTS_INDEX.exists() else None
    env = {**os.environ, "HOME": str(home)}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"cwd": str(tmp_path), "tool_input": {"file_path": str(agent)}}),
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    assert not (tmp_path / "agents" / "INDEX.json").exists(), "hook must not write into the project"
    after = AGENTS_INDEX.read_bytes() if AGENTS_INDEX.exists() else None
    assert after == before


def test_agent_edit_with_engine_target_refreshes_installed_index(tmp_path: Path, monkeypatch) -> None:
    import os

    sys.path.insert(0, str(REPO_ROOT / "scripts" / "tests"))
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from vexinstall_support import assert_repo_clean, make_world

    world = make_world(tmp_path, monkeypatch)
    assert world.run("apply", "--target", "claude").code == 0
    index = world.home / ".claude" / "vexjoy" / "index" / "agents.json"
    index.unlink()
    env = {
        **os.environ,
        "HOME": str(world.home),
        "VEXINSTALL_SOURCE_ROOT": str(world.repo),
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(
            {"cwd": str(world.repo), "tool_input": {"file_path": str(world.repo / "agents" / "a-eng.md")}}
        ),
        capture_output=True,
        text=True,
        timeout=60,
        cwd="/",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[sync-agent-index] installed index refreshed (claude)" in proc.stdout, proc.stderr
    assert index.is_file()
    assert not (world.repo / "agents" / "INDEX.json").exists()
    assert_repo_clean(world.repo)


# ---------------------------------------------------------------------------
# Non-match silent + fast (no subprocess spawned)
# ---------------------------------------------------------------------------

NON_MATCH_PATHS = [
    "README.md",
    "src/app.py",
    "skills/meta/do/SKILL.md",
    "agents/INDEX.md",
    "agents/README.md",
]


def test_non_match_paths_silent_and_exit_zero() -> None:
    for path in NON_MATCH_PATHS:
        proc = run_hook({"tool_input": {"file_path": path}})
        assert proc.returncode == 0, (path, proc.stderr)
        assert proc.stdout == "", (path, proc.stdout)


# ---------------------------------------------------------------------------
# Robustness: empty / malformed / missing file_path
# ---------------------------------------------------------------------------


def test_empty_stdin_exits_zero() -> None:
    proc = run_hook("")
    assert proc.returncode == 0


def test_malformed_json_exits_zero() -> None:
    proc = run_hook("not json at all")
    assert proc.returncode == 0
    assert "Traceback" not in proc.stderr


def test_missing_file_path_exits_zero() -> None:
    proc = run_hook({"tool_input": {}})
    assert proc.returncode == 0
    assert proc.stdout == ""


# ---------------------------------------------------------------------------
# Path-matching helper (imported as a module)
# ---------------------------------------------------------------------------


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("posttooluse_sync_agent_index", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_is_agent_file_matches_flat_layout() -> None:
    mod = _load_module()
    assert mod.is_agent_file("agents/data-engineer.md") is True
    assert mod.is_agent_file("/abs/path/agents/data-engineer.md") is True
    assert mod.is_agent_file("agents/INDEX.md") is False
    assert mod.is_agent_file("agents/README.md") is False
    assert mod.is_agent_file("skills/x/SKILL.md") is False
    assert mod.is_agent_file("agents/sub/nested.md") is False
    assert mod.is_agent_file("README.md") is False
