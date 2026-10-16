"""Extra plan-gate tests: root-validation edge cases, symlink targets, and deny messaging."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "pretool-plan-gate.py"
GATED = "skills/example/SKILL.md"


def _run(file_path: str, *, cwd: Path, project_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "cwd": str(cwd),
    }
    env = {
        k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "PLAN_GATE_BYPASS", "CLAUDE_HOOKS_DEBUG")
    }
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        env=env,
        timeout=20,
        check=False,
    )


def _denied(result: subprocess.CompletedProcess[str]) -> bool:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _git(*args: str, cwd: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr


def _forge(
    root: Path,
    *,
    head: str = "ref: refs/heads/main",
    commondir: bool = True,
    backlink_file: bool = True,
) -> None:
    """Linked-worktree marker in *root* whose metadata is valid except where overridden."""
    common = root.parent / "forged-common"
    admin = common / "worktrees" / "forged"
    (common / "objects").mkdir(parents=True)
    (common / "refs").mkdir()
    admin.mkdir(parents=True)
    (common / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (common / "config").write_text("[core]\n", encoding="utf-8")
    (admin / "HEAD").write_bytes(head.encode() + b"\n")
    if commondir:
        (admin / "commondir").write_text("../..\n", encoding="utf-8")
    if backlink_file:
        (admin / "gitdir").write_text(f"{root / '.git'}\n", encoding="utf-8")
    (root / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "forged-project"
    (root / "skills" / "example").mkdir(parents=True)
    (root / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    return root


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _git("init", "--quiet", str(root), cwd=tmp_path)
    (root / "skills" / "example").mkdir(parents=True)
    return root


def test_nonexistent_project_dir_env_is_ignored_in_favor_of_cwd_repo(tmp_path):
    root = _repo(tmp_path)
    result = _run(str(root / GATED), cwd=root, project_dir=tmp_path / "does-not-exist")
    assert _denied(result) is True


def test_git_directory_without_objects_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    git_dir = root / ".git"
    (git_dir / "refs").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")
    assert _denied(_run(GATED, cwd=root)) is True


def test_forged_worktree_with_multiline_head_is_not_a_root(tmp_path):
    root = _project(tmp_path)
    _forge(root, head="ref: refs/heads/main\nextra")
    assert _denied(_run(GATED, cwd=root)) is True


@pytest.mark.parametrize(
    "head",
    ["abcdef", "ref: refs/heads/a~b", "ref: refs/heads/a b", "ref: refs/heads/a\x7fb"],
)
def test_forged_worktree_with_bad_head_is_not_a_root(tmp_path, head):
    root = _project(tmp_path)
    _forge(root, head=head)
    assert _denied(_run(GATED, cwd=root)) is True


@pytest.mark.parametrize("missing", ["commondir", "backlink_file"])
def test_forged_worktree_missing_admin_file_is_not_a_root(tmp_path, missing):
    root = _project(tmp_path)
    _forge(root, **{missing: False})
    assert _denied(_run(GATED, cwd=root)) is True


def test_linked_worktree_inside_its_own_repository_is_its_own_root(tmp_path):
    repo = _repo(tmp_path)
    _git(
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "x",
        cwd=repo,
    )
    wt = repo / "wt"
    _git("-c", "core.hooksPath=/dev/null", "worktree", "add", "--quiet", "--detach", str(wt), "HEAD", cwd=repo)
    (wt / "skills" / "example").mkdir(parents=True)
    assert _denied(_run(GATED, cwd=wt)) is True
    (wt / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    assert _denied(_run(GATED, cwd=wt)) is False


def test_symlink_loop_in_gated_directory_is_denied_even_with_a_plan(tmp_path):
    root = _repo(tmp_path)
    (root / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    (root / "skills" / "loop").symlink_to(root / "skills" / "loop")
    result = _run(str(root / "skills" / "loop" / "SKILL.md"), cwd=root)
    assert _denied(result) is True


def test_symlink_leaving_project_outside_gated_dirs_is_denied(tmp_path):
    root = _repo(tmp_path)
    (root / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "docs-link").symlink_to(outside)
    result = _run(str(root / "docs-link" / "notes.md"), cwd=root)
    assert _denied(result) is True


def test_root_plan_that_is_a_symlink_into_gated_dir_needs_a_real_plan(tmp_path):
    root = _repo(tmp_path)
    (root / "skills" / "example" / "real.md").write_text("x\n", encoding="utf-8")
    (root / "task_plan.md").symlink_to(root / "skills" / "example" / "real.md")
    assert _denied(_run(str(root / "task_plan.md"), cwd=root)) is True


def test_symlink_pointing_at_root_plan_from_gated_dir_is_denied(tmp_path):
    root = _repo(tmp_path)
    (root / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
    (root / "skills" / "example" / "link.md").symlink_to(root / "task_plan.md")
    assert _denied(_run(str(root / "skills" / "example" / "link.md"), cwd=root)) is True


def test_unsafe_target_deny_does_not_suggest_planning_skill(tmp_path):
    root = _repo(tmp_path)
    result = _run("../outside.md", cwd=root)
    assert _denied(result) is True
    assert "[fix-with-skill]" not in result.stderr


def test_missing_plan_deny_suggests_planning_skill(tmp_path):
    root = _repo(tmp_path)
    result = _run(str(root / GATED), cwd=root)
    assert _denied(result) is True
    assert "[fix-with-skill] process" in result.stderr
