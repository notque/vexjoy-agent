"""install.sh --uninstall sets aside the post-merge hook it wrote, so the uninstall sticks (lane C, C-02).

The post-merge hook runs ``vexinstall sync --target all`` after every git pull. Once an uninstall
has removed the launcher and the settings hooks, that hook is the one thing left that runs a sync,
and a sync puts back everything the uninstall removed. --uninstall (no --target, or --target
claude) renames the hook to post-merge.vexjoy-removed.<ts> when it carries install.sh's marker
line and leaves anyone else's post-merge alone. --rollback of an uninstall writes it again.
"""

from __future__ import annotations

import json
import os
import re
import shlex
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


def _func(name: str) -> str:
    body = subprocess.run(
        ["sed", "-n", f"/^{name}() {{/,/^}}/p", str(INSTALL_SH)], capture_output=True, text=True, check=True
    ).stdout
    assert body, f"{name} not found in install.sh"
    return body


def _uninstall_git_hooks(co: Path, *, target: str = "all", dry_run: bool = False, env: dict | None = None):
    """Run install.sh's uninstall_git_hooks for the checkout *co*; prints GIT_HOOK_PROBLEM last."""
    body = (
        "set -euo pipefail\n"
        f'GREEN=""; YELLOW=""; BLUE=""; NC=""; SCRIPT_DIR="{co}"; TARGET="{target}"; DRY_RUN={str(dry_run).lower()}\n'
        'GIT_HOOK_PROBLEM=""\n'
        f"{_func('main_hooks_dir')}\n{_func('uninstall_git_hooks')}\n"
        'uninstall_git_hooks\necho "problem=${GIT_HOOK_PROBLEM}"\n'
    )
    full_env = {"PATH": "/usr/bin:/bin", **(env or {})}
    return subprocess.run(["bash", "-c", body], capture_output=True, text=True, env=full_env, timeout=60)


def _renamed(co: Path) -> list[Path]:
    return sorted((co / ".git" / "hooks").glob("post-merge.vexjoy-removed.*"))


@pytest.mark.parametrize("target", ["all", "claude"])
def test_uninstall_renames_the_post_merge_install_sh_wrote(tmp_path: Path, target: str) -> None:
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, target=target)
    assert res.returncode == 0, res.stderr
    assert not os.path.lexists(co / ".git" / "hooks" / "post-merge")
    assert [p.read_text() for p in _renamed(co)] == [_post_merge_body()]
    assert "Renamed post-merge hook" in res.stdout and res.stdout.rstrip().endswith("problem="), res.stdout


def test_uninstall_leaves_a_foreign_post_merge_alone(tmp_path: Path) -> None:
    co = _checkout(tmp_path, FOREIGN)
    res = _uninstall_git_hooks(co)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").read_text() == FOREIGN and not _renamed(co)
    assert "Keeping post-merge hook (not written by vexjoy-agent)" in res.stdout
    assert str(co / ".git" / "hooks" / "post-merge") in res.stdout


@pytest.mark.parametrize("target", ["codex", "hermes"])
def test_a_partial_uninstall_keeps_the_hook(tmp_path: Path, target: str) -> None:
    # claude stays installed, and its SessionStart sync puts the other target back either way,
    # so removing the hook would only stop claude from updating on pull.
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, target=target)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").is_file() and not _renamed(co)
    assert "Keeping post-merge hook (a --target uninstall keeps it" in res.stdout, res.stdout


def test_dry_run_only_says_so(tmp_path: Path) -> None:
    co = _checkout(tmp_path, _post_merge_body())
    res = _uninstall_git_hooks(co, dry_run=True)
    assert res.returncode == 0, res.stderr
    assert (co / ".git" / "hooks" / "post-merge").is_file() and not _renamed(co)
    assert "Would rename post-merge hook" in res.stdout


@pytest.mark.parametrize("case", ["no-git-hooks-env", "no-hook"])
def test_nothing_to_do(tmp_path: Path, case: str) -> None:
    co = _checkout(tmp_path, None if case == "no-hook" else _post_merge_body())
    env = {"VEXJOY_NO_GIT_HOOKS": "1"} if case == "no-git-hooks-env" else None
    res = _uninstall_git_hooks(co, env=env)
    assert res.returncode == 0, res.stderr
    assert not _renamed(co) and res.stdout.rstrip().endswith("problem="), res.stdout
    if case == "no-git-hooks-env":
        assert (co / ".git" / "hooks" / "post-merge").is_file()
        assert "Git hooks skipped (VEXJOY_NO_GIT_HOOKS=1)" in res.stdout


def test_an_unreadable_worktree_git_file_is_a_problem(tmp_path: Path) -> None:
    # A worktree's .git is a file; when git cannot follow it, the main checkout's hook may still run.
    co = _checkout(tmp_path, None)
    shutil.rmtree(co / ".git")
    (co / ".git").write_text("gitdir: /elsewhere\n")
    res = _uninstall_git_hooks(co)
    assert res.returncode == 0, res.stderr
    assert "run ./install.sh --uninstall in the main checkout too" in res.stdout.splitlines()[-1], res.stdout


UNDID_UNINSTALL = "[rollback] run install-1 (uninstall)\n  trash 1: restored 3, skipped 0 (occupied or missing)"


@pytest.mark.parametrize(
    ("out", "rc", "dry_run", "writes"),
    [
        (UNDID_UNINSTALL, 0, False, True),
        (UNDID_UNINSTALL, 1, False, True),
        ("[rollback] run install-1 (apply + prune)\n    skipped: /h/.claude/skills/x (uninstall)", 0, False, False),
        ("[rollback] run install-1 was already rolled back at 2026-01-01T00:00:00Z", 0, False, False),
        ("[rollback] would restore run install-1 (uninstall):\n  trash session 1", 0, True, False),
        ("", 4, False, False),
    ],
    ids=["uninstall", "uninstall-partial", "apply-with-odd-path", "already-done", "dry-run", "guard-abort"],
)
def test_rollback_writes_the_hook_back_only_for_an_uninstall_it_undid(
    out: str, rc: int, dry_run: bool, writes: bool
) -> None:
    # install.sh reads the engine's first line: "[rollback] run <id> (<commands>)" appears only for a
    # run the engine rolled back and marked done, in full (exit 0) or not (exit 1).
    func = subprocess.run(
        ["sed", "-n", "/^rollback() {/,/^}/p", str(INSTALL_SH)], capture_output=True, text=True, check=True
    ).stdout
    assert func, "rollback not found in install.sh"
    body = (
        f"set -euo pipefail\nDRY_RUN={str(dry_run).lower()}\n"
        f"vexinstall() {{ printf '%s\\n' {shlex.quote(out)}; return {rc}; }}\n"
        "install_git_hooks() { echo HOOK-WRITTEN; }\n"
        f'{func}\nrc=0; rollback || rc=$?; echo "rc=$rc"\n'
    )
    res = subprocess.run(
        ["bash", "-c", body], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=60
    )
    assert res.returncode == 0, res.stderr
    assert ("HOOK-WRITTEN" in res.stdout) is writes, res.stdout
    assert res.stdout.rstrip().endswith(f"rc={rc}"), res.stdout


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize("partial", [False, True], ids=["whole", "settings-backup-gone"])
def test_uninstall_sticks_and_rollback_puts_the_hook_back(tmp_path: Path, partial: bool) -> None:
    # A toolkit-shaped checkout with its own .git, so install.sh writes and removes hooks there
    # and never in this repo. Its engine is this repo's (scripts/vexinstall, untracked there).
    # A rollback that cannot restore everything (exit 1) has still undone the uninstall and marked
    # it done, so a second --rollback could never bring the hook back: it must come back now.
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

    def install(*args: str, rc: int = 0) -> subprocess.CompletedProcess[str]:
        res = subprocess.run(
            ["bash", str(co / "install.sh"), *args], capture_output=True, text=True, env=env, timeout=600, cwd=home
        )
        assert res.returncode == rc, res.stdout + res.stderr
        return res

    hook = co / ".git" / "hooks" / "post-merge"
    alpha = home / ".claude" / "skills" / "alpha" / "SKILL.md"
    install()
    assert MARKER in hook.read_text() and alpha.is_file()
    install("--uninstall")
    assert not alpha.exists()
    assert not os.path.lexists(hook), "a git pull would run the sync that reinstalls everything"
    assert (co / ".git" / "hooks" / "pre-commit").is_file(), "the private-leak gate stays"
    if partial:
        state = home / ".claude" / "vexjoy"
        point = json.loads((state / "rollback.json").read_text())
        (state / "backups" / f"settings.{point['settings_backup']}.json").unlink()
    rb = install("--rollback", rc=1 if partial else 0)
    assert alpha.is_file()
    assert MARKER in hook.read_text(), rb.stdout
