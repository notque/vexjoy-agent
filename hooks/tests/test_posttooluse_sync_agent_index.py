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


def run_hook(event_obj_or_str) -> subprocess.CompletedProcess:
    payload = event_obj_or_str if isinstance(event_obj_or_str, str) else json.dumps(event_obj_or_str)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Regen on agent edit
# ---------------------------------------------------------------------------


def test_regen_on_agent_edit_writes_index_and_exits_zero() -> None:
    if AGENTS_INDEX.exists():
        AGENTS_INDEX.unlink()
    proc = run_hook({"tool_input": {"file_path": "agents/hook-development-engineer.md"}})
    assert proc.returncode == 0, proc.stderr
    assert AGENTS_INDEX.is_file()
    data = json.loads(AGENTS_INDEX.read_text(encoding="utf-8"))
    assert "agents" in data and len(data["agents"]) > 0
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
