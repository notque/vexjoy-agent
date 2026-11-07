"""install.sh --uninstall removes the post-merge hook it wrote, so the uninstall sticks (lane C, C-02).

The post-merge hook runs ``vexinstall sync --target all`` after every git pull. Once an uninstall
has removed the launcher and the settings hooks, that hook is the one thing left that runs a sync,
and a sync puts back everything the uninstall removed. --uninstall now deletes the hook when it
carries install.sh's marker line and leaves anyone else's post-merge alone. --rollback of an
uninstall writes it again.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import make_repo

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
MARKER = "Written by vexjoy-agent"
FOREIGN = "#!/bin/sh\n# my own post-merge\necho pulled\n"

if shutil.which("bash") is None:
    pytest.skip("bash not available", allow_module_level=True)


def _post_merge_body() -> str:
    """The post-merge hook install.sh writes (its _write_git_hook heredoc)."""
    m = re.search(r"_write_git_hook post-merge << 'HOOK'\n(.*?)\nHOOK\n", INSTALL_SH.read_text(), re.DOTALL)
    assert m, "post-merge heredoc not found in install.sh"
    return m.group(1) + "\n"


def _checkout(tmp_path: Path, hook: str | None) -> Path:
    co = tmp_path / "co"
    hooks = co / ".git" / "hooks"
    hooks.mkdir(parents=True)
    if hook is not None:
        (hooks / "post-merge").write_text(hook)
        (hooks / "post-merge").chmod(0o755)
    return co


def _uninstall_git_hooks(co: Path, *, target: str = "all", dry_run: bool = False, env: dict | None = None):
    """Run install.sh's uninstall_git_hooks for the checkout *co*."""
    func = subprocess.run(
        ["sed", "-n", "/^uninstall_git_hooks() {/,/^}/p", str(INSTALL_SH)], capture_output=True, text=True, check=True
    ).stdout
    assert func, "uninstall_git_hooks not found in install.sh"
    body = (
        "set -euo pipefail\n"
        f'GREEN=""; YELLOW=""; NC=""; SCRIPT_DIR="{co}"; TARGET="{target}"; DRY_RUN={str(dry_run).lower()}\n'
        f"{func}\nuninstall_git_hooks\n"
    )
    full_env = {"PATH": "/usr/bin:/bin", **(env or {})}
    return subprocess.run(["bash", "-c", body], capture_output=True, text=True, env=full_env, timeout=60)


@pytest.mark.parametrize("target", ["all", "claude"])
def test_uninstall_removes_the_post_merge_install_sh_wrote(tmp_path: Path, target: str) -> None:
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, target=target)
    assert res.returncode == 0, res.stderr
    assert not os.path.lexists(co / ".git" / "hooks" / "post-merge")
    assert "Removed post-merge hook" in res.stdout


def test_uninstall_leaves_a_foreign_post_merge_alone(tmp_path: Path) -> None:
    co = _checkout(tmp_path, FOREIGN)
    res = _uninstall_git_hooks(co)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").read_text() == FOREIGN
    assert "not install.sh's" in res.stdout and str(co / ".git" / "hooks" / "post-merge") in res.stdout


@pytest.mark.parametrize("target", ["codex", "hermes"])
def test_a_partial_uninstall_keeps_the_hook(tmp_path: Path, target: str) -> None:
    # claude stays installed, and its SessionStart sync puts the other target back either way,
    # so removing the hook would only stop claude from updating on pull.
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, target=target)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").is_file() and res.stdout == ""


def test_dry_run_only_says_so(tmp_path: Path) -> None:
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, dry_run=True)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").is_file()
    assert "Would remove post-merge hook" in res.stdout


@pytest.mark.parametrize("case", ["no-git-hooks-env", "worktree", "no-hook"])
def test_nothing_to_do(tmp_path: Path, case: str) -> None:
    co = _checkout(tmp_path, None if case == "no-hook" else _post_merge_body())
    env = {"VEXJOY_NO_GIT_HOOKS": "1"} if case == "no-git-hooks-env" else None
    if case == "worktree":  # a worktree's .git is a file; install.sh never wrote hooks there
        shutil.rmtree(co / ".git")
        (co / ".git").write_text("gitdir: /elsewhere\n")
    res = _uninstall_git_hooks(co, env=env)
    assert res.returncode == 0, res.stderr
    assert res.stdout == ""
    if case == "no-git-hooks-env":
        assert (co / ".git" / "hooks" / "post-merge").is_file()


@pytest.mark.slow
@pytest.mark.integration
def test_uninstall_sticks_and_rollback_puts_the_hook_back(tmp_path: Path) -> None:
    # A toolkit-shaped checkout with its own .git, so install.sh writes and removes hooks there
    # and never in this repo. Its engine is this repo's (scripts/vexinstall, untracked there).
    co = make_repo(tmp_path / "co")
    shutil.copy2(INSTALL_SH, co / "install.sh")
    (co / "scripts" / "vexinstall").symlink_to(REPO_ROOT / "scripts" / "vexinstall")
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith(("VEXINSTALL_", "VEXJOY_", "GIT_"))},
        "HOME": str(home),
        "VEXJOY_NO_DEPS": "1",
        "VEXJOY_INSTALL_PROFILE": str(home / "no-profile.yaml"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "TERM": "dumb",
    }

    def install(*args: str) -> subprocess.CompletedProcess[str]:
        res = subprocess.run(
            ["bash", str(co / "install.sh"), *args], capture_output=True, text=True, env=env, timeout=600, cwd=home
        )
        assert res.returncode == 0, res.stdout + res.stderr
        return res

    hook = co / ".git" / "hooks" / "post-merge"
    alpha = home / ".claude" / "skills" / "alpha" / "SKILL.md"
    install()
    assert MARKER in hook.read_text() and alpha.is_file()
    install("--uninstall")
    assert not alpha.exists()
    assert not os.path.lexists(hook), "a git pull would run the sync that reinstalls everything"
    assert (co / ".git" / "hooks" / "pre-commit").is_file(), "the private-leak gate stays"
    rb = install("--rollback")
    assert alpha.is_file()
    assert MARKER in hook.read_text(), rb.stdout
