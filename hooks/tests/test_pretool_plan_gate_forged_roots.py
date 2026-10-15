"""Forged-root and malformed-input tests for the implementation plan gate.

Added from the E2 mutation check. The plan gate trusts a directory as a project
root only when its Git metadata is structurally valid. The existing suite proved
that a forged marker cannot override an outer repository, but never broke the
metadata one property at a time. A forged root in a non-repository directory is
the case where each check is the only thing standing between the forger and an
allow, so every test here plants a task_plan.md in that directory:

- a valid forged linked worktree is accepted (the control),
- the same forgery with one broken property must be denied: bad HEAD, bad ref
  name, wrong backlink, admin dir outside `worktrees/`, common dir without
  `config`,
- a symlinked gated directory that leaves the project is denied even when a plan
  exists,
- non-string tool input and cwd values fail without a crash.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "pretool-plan-gate.py"
GATED_RELATIVE = "skills/example/SKILL.md"


def _forge(
    root: Path,
    *,
    head: str = "ref: refs/heads/main",
    backlink: str | None = None,
    admin_parent: str = "worktrees",
    config: bool = True,
) -> None:
    """Build a linked-worktree marker in *root* whose metadata is valid except where overridden."""
    common = root.parent / "forged-common"
    admin = common / admin_parent / "forged"
    (common / "objects").mkdir(parents=True)
    (common / "refs").mkdir()
    (common / "worktrees").mkdir(exist_ok=True)
    admin.mkdir(parents=True)
    (common / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    if config:
        (common / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    (admin / "HEAD").write_text(head + "\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    marker = root / ".git"
    (admin / "gitdir").write_text((backlink or str(marker)) + "\n", encoding="utf-8")
    marker.write_text(f"gitdir: {admin}\n", encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "forged-project"
    (root / "skills" / "example").mkdir(parents=True)
    (root / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    return root


def _run(tool_input: object, *, cwd: object, process_cwd: str = "/") -> subprocess.CompletedProcess[str]:
    event = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": tool_input, "cwd": cwd}
    env = {
        k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "PLAN_GATE_BYPASS", "CLAUDE_HOOKS_DEBUG")
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=process_cwd,
        env=env,
        timeout=20,
        check=False,
    )


def _denied(result: subprocess.CompletedProcess[str]) -> bool:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_valid_forged_linked_worktree_with_plan_is_accepted_as_a_root(tmp_path):
    root = _project(tmp_path)
    _forge(root)
    result = _run({"file_path": GATED_RELATIVE}, cwd=str(root))
    assert _denied(result) is False
    assert result.stderr == ""


@pytest.mark.parametrize(
    "head",
    ["not a ref or a hash", "ref: refs/heads/.hidden", "ref: refs/heads/topic.lock", "ref: refs/heads/topic."],
)
def test_forged_worktree_with_invalid_head_is_not_a_root(tmp_path, head):
    root = _project(tmp_path)
    _forge(root, head=head)
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


def test_forged_worktree_with_wrong_backlink_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    other = tmp_path / "other-checkout"
    other.mkdir()
    (other / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    _forge(root, backlink=str(other / ".git"))
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


def test_forged_worktree_admin_dir_outside_worktrees_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    _forge(root, admin_parent="elsewhere")
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


def test_forged_worktree_with_common_dir_missing_config_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    _forge(root, config=False)
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


def test_git_directory_missing_config_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    git_dir = root / ".git"
    (git_dir / "objects").mkdir(parents=True)
    (git_dir / "refs").mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


def test_symlinked_gated_directory_leaving_the_project_is_denied_even_with_a_plan(tmp_path):
    root = _project(tmp_path)
    _forge(root)
    outside = tmp_path / "outside"
    (outside / "example").mkdir(parents=True)
    (root / "skills" / "example").rmdir()
    (root / "skills").rmdir()
    (root / "skills").symlink_to(outside, target_is_directory=True)
    assert _denied(_run({"file_path": GATED_RELATIVE}, cwd=str(root))) is True


@pytest.mark.parametrize("tool_input", [["not", "a", "dict"], {"file_path": 123}, "text"])
def test_malformed_tool_input_is_allowed_without_a_crash(tmp_path, tool_input):
    result = _run(tool_input, cwd=str(_project(tmp_path)))
    assert _denied(result) is False
    assert result.stderr == ""


@pytest.mark.parametrize("cwd", [123, "/tmp/with\x00nul", ""])
def test_unusable_cwd_for_a_relative_gated_path_is_denied(cwd):
    result = _run({"file_path": GATED_RELATIVE}, cwd=cwd)
    assert _denied(result) is True


def test_relative_event_cwd_is_never_trusted_as_a_root(tmp_path):
    root = _project(tmp_path)
    _forge(root)
    result = _run({"file_path": GATED_RELATIVE}, cwd=root.name, process_cwd=str(tmp_path))
    assert _denied(result) is True


def test_absolute_non_gated_path_without_a_root_is_allowed(tmp_path):
    result = _run({"file_path": str(tmp_path / "notes" / "todo.txt")}, cwd=str(tmp_path))
    assert _denied(result) is False
    assert result.stderr == ""


def test_absolute_gated_path_without_a_root_is_denied(tmp_path):
    result = _run({"file_path": str(tmp_path / "skills" / "example" / "SKILL.md")}, cwd=str(tmp_path))
    assert _denied(result) is True
