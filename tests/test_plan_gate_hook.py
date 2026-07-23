#!/usr/bin/env python3
"""Tests for pretool-plan-gate.py — the plan-gate hook.

TDD: each test was written BEFORE its fix and verified to FAIL on the
unfixed code, then PASS after the fix. Covers three defects:
- Defect 1: project-root resolution (walk up to .git), so a repo-root
  task_plan.md satisfies the gate regardless of session pwd depth.
- Defect 2: the plan file itself (task_plan.md) is never gated.
- Defect 3: docstring/comments accurately state all agents//skills/ files
  (including .md) are gated.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Resolve paths
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"
HOOK = HOOKS_DIR / "pretool-plan-gate.py"


def _run(event: dict, env_extra: dict | None = None):
    """Invoke the hook with a synthetic event on stdin; return CompletedProcess."""
    env = os.environ.copy()
    # Ensure a clean slate — no inherited bypass / project-dir override.
    env.pop("PLAN_GATE_BYPASS", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _is_deny(result) -> bool:
    """A deny prints JSON with permissionDecision:deny to stdout."""
    stdout = result.stdout.strip()
    if not stdout:
        return False
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    hso = parsed.get("hookSpecificOutput", {})
    return hso.get("permissionDecision") == "deny"


def _make_git_repo(tmp_path: Path) -> Path:
    """Create a directory that looks like a git root (has .git)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Acceptance 3: gated path, no plan at git root -> deny
# ---------------------------------------------------------------------------


def test_gated_path_no_plan_denies(tmp_path):
    root = _make_git_repo(tmp_path)
    skill_file = root / "skills" / "x" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(skill_file)},
        "cwd": str(root),
    }
    result = _run(event)
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert _is_deny(result), f"Expected deny, got stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Acceptance 1 / Defect 1: plan at git root, deep cwd -> allow
# ---------------------------------------------------------------------------


def test_plan_at_git_root_deep_cwd_allows(tmp_path):
    root = _make_git_repo(tmp_path)
    (root / "task_plan.md").write_text("plan\n")
    deep = root / "skills" / "engineering" / "opensearch-api-client" / "scripts"
    deep.mkdir(parents=True)
    skill_file = root / "skills" / "engineering" / "opensearch-api-client" / "SKILL.md"
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(skill_file)},
        "cwd": str(deep),
    }
    result = _run(event)
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert not _is_deny(result), f"Expected allow (plan at git root, deep cwd), got deny. stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Acceptance 2 / Defect 2: writing task_plan.md is never gated
# ---------------------------------------------------------------------------


def test_writing_plan_file_in_gated_subtree_allows(tmp_path):
    root = _make_git_repo(tmp_path)
    # No task_plan.md at root yet — the point is to create one under skills/.
    target = root / "skills" / "x" / "task_plan.md"
    target.parent.mkdir(parents=True)
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(target)},
        "cwd": str(root),
    }
    result = _run(event)
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert not _is_deny(result), f"task_plan.md must never be gated. stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Acceptance 4: non-gated path -> allow
# ---------------------------------------------------------------------------


def test_non_gated_path_allows(tmp_path):
    root = _make_git_repo(tmp_path)
    doc = root / "docs" / "x.md"
    doc.parent.mkdir(parents=True)
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(doc)},
        "cwd": str(root),
    }
    result = _run(event)
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert not _is_deny(result), f"Non-gated path must allow. stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Acceptance 5: PLAN_GATE_BYPASS=1 -> allow
# ---------------------------------------------------------------------------


def test_bypass_env_allows(tmp_path):
    root = _make_git_repo(tmp_path)
    skill_file = root / "skills" / "x" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(skill_file)},
        "cwd": str(root),
    }
    result = _run(event, env_extra={"PLAN_GATE_BYPASS": "1"})
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert not _is_deny(result), f"PLAN_GATE_BYPASS=1 must allow. stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Defect 1 (env override): CLAUDE_PROJECT_DIR takes precedence
# ---------------------------------------------------------------------------


def test_claude_project_dir_env_used_for_root(tmp_path):
    root = tmp_path / "proj"  # no .git — force use of the env var
    (root / "skills" / "x").mkdir(parents=True)
    (root / "task_plan.md").write_text("plan\n")
    skill_file = root / "skills" / "x" / "SKILL.md"
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(skill_file)},
        "cwd": str(root / "skills" / "x"),
    }
    result = _run(event, env_extra={"CLAUDE_PROJECT_DIR": str(root)})
    assert result.returncode == 0, f"Hook exited non-zero: {result.stderr}"
    assert not _is_deny(result), f"CLAUDE_PROJECT_DIR should anchor root. stdout={result.stdout!r}"


# ---------------------------------------------------------------------------
# Defect 3: docstring/comments accurately describe gating scope
# ---------------------------------------------------------------------------


def test_docstring_states_all_files_gated():
    source = HOOK.read_text()
    lowered = source.lower()
    # Misleading "passes through" wording for docs/config/CI/tests must be gone.
    assert "passes through" not in lowered, "Misleading 'passes through' wording still present"
    # Must state gating is regardless of extension / behavioral spec rationale.
    assert "regardless of extension" in lowered or "behavioral spec" in lowered, (
        "Docstring/comments do not state that all agents//skills/ files are gated"
    )
