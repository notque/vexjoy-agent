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
# Regen on agent edit
# ---------------------------------------------------------------------------


def test_regen_on_agent_edit_writes_target_index_without_touching_source(tmp_path: Path) -> None:
    agent = tmp_path / "agents" / "isolated-agent.md"
    agent.parent.mkdir()
    agent.write_text(
        "---\nname: isolated-agent\ndescription: Isolated agent fixture.\n---\n",
        encoding="utf-8",
    )
    before = AGENTS_INDEX.read_bytes() if AGENTS_INDEX.exists() else None
    proc = run_hook(
        {"cwd": str(tmp_path), "tool_input": {"file_path": str(agent)}},
        cwd=Path("/"),
    )
    assert proc.returncode == 0, proc.stderr
    target_index = tmp_path / "agents" / "INDEX.json"
    assert target_index.is_file()
    data = json.loads(target_index.read_text(encoding="utf-8"))
    assert set(data["agents"]) == {"isolated-agent"}
    after = AGENTS_INDEX.read_bytes() if AGENTS_INDEX.exists() else None
    assert after == before
    assert "[sync-agent-index]" in proc.stdout


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
