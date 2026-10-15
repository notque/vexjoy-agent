"""Push-detection and project-scope tests for pretool-ruff-format-gate.

Added from the E2 mutation check. The existing suite never proved that:
- `env -i git push` is still seen as a push, while `docker push` is not,
- a `( cd bad-repo && ... )` subshell does not leak its directory into a later push,
- the pyproject.toml search climbs from a subdirectory,
- committed branch changes (clean working tree) are checked,
- a push outside any ruff project, or with ruff missing, is allowed quietly,
- the RUFF_FORMAT_GATE_BYPASS=1 bypass wins over a real violation,
- the ruff output in the denial is cut with "..." only when it is long.

Each test runs the hook as a subprocess against a real tmp git repo and the real
`ruff`. The tests are skipped when `ruff` is not installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "pretool-ruff-format-gate.py"

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not installed")

BAD = "x = {  'a':1 }\n"
GOOD = 'x = {"a": 1}\n'
PUSH = "git " + "push"


def _git(repo: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def _repo(root: Path, name: str = "project", *, ruff: bool = True) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    (repo / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n" if ruff else "[project]\n", encoding="utf-8")
    (repo / "ok.py").write_text(GOOD, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "base")
    return repo


def _run(command: str, cwd: Path, *, env_extra: dict[str, str] | None = None, path: str | None = None):
    env = {k: v for k, v in os.environ.items() if k not in ("RUFF_FORMAT_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
    env["HOME"] = str(cwd.parent)
    if path is not None:
        env["PATH"] = path
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False, "", proc.stderr
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny", out["permissionDecisionReason"], proc.stderr


@pytest.fixture
def bad_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    (repo / "bad.py").write_text(BAD, encoding="utf-8")
    return repo


def test_push_with_an_unformatted_file_is_denied(bad_repo):
    assert _run(PUSH, bad_repo)[0] is True


def test_push_with_only_formatted_files_is_allowed(tmp_path):
    repo = _repo(tmp_path)
    (repo / "fine.py").write_text(GOOD, encoding="utf-8")
    assert _run(PUSH, repo)[0] is False


@pytest.mark.parametrize("prefix", ["env -i ", "env A=1 B=2 ", "command ", "command -p "])
def test_push_behind_a_wrapper_is_still_a_push(bad_repo, prefix):
    assert _run(prefix + PUSH, bad_repo)[0] is True


def test_another_tool_named_push_is_not_a_git_push(bad_repo):
    assert _run("docker push registry.example/app:1", bad_repo)[0] is False


def test_subshell_cd_does_not_leak_into_a_later_push(tmp_path, bad_repo):
    clean = _repo(tmp_path, "clean")
    command = f"(cd {bad_repo} && true); {PUSH}"
    assert _run(command, clean)[0] is False


def test_push_inside_a_subshell_uses_the_subshell_directory(tmp_path, bad_repo):
    clean = _repo(tmp_path, "clean")
    assert _run(f"(cd {bad_repo} && {PUSH})", clean)[0] is True


def test_push_from_a_subdirectory_finds_the_project_pyproject(bad_repo):
    sub = bad_repo / "pkg" / "inner"
    sub.mkdir(parents=True)
    assert _run(PUSH, sub)[0] is True


def test_committed_branch_changes_are_checked(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "--quiet", "-b", "feature")
    (repo / "bad.py").write_text(BAD, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "bad format")
    assert _run(PUSH, repo)[0] is True


def test_push_outside_a_ruff_project_is_allowed_quietly(tmp_path):
    repo = _repo(tmp_path, ruff=False)
    (repo / "bad.py").write_text(BAD, encoding="utf-8")
    denied, _, stderr = _run(PUSH, repo)
    assert denied is False
    assert stderr == ""


def test_missing_ruff_allows_quietly(bad_repo, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(shutil.which("git"))
    denied, _, stderr = _run(PUSH, bad_repo, path=str(bin_dir))
    assert denied is False
    assert stderr == ""


def test_bypass_env_allows_a_real_violation(bad_repo):
    assert _run(PUSH, bad_repo, env_extra={"RUFF_FORMAT_GATE_BYPASS": "1"})[0] is False


def test_short_ruff_output_is_not_cut(bad_repo):
    _, reason, _ = _run(PUSH, bad_repo)
    assert "bad.py" in reason
    assert "..." not in reason


def test_long_ruff_output_is_cut_with_an_ellipsis(bad_repo):
    for i in range(30):
        (bad_repo / f"unformatted_module_with_a_long_name_{i:02d}.py").write_text(BAD, encoding="utf-8")
    _, reason, _ = _run(PUSH, bad_repo)
    assert reason.endswith("...")
