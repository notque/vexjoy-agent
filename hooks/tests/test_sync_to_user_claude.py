"""SessionStart sync hook: a thin, fail-open wrapper around ``vexinstall sync --target all``."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.tests import vexinstall_support
from scripts.tests.vexinstall_support import Env, repo_hash

world = vexinstall_support.world  # pytest fixture

HOOK = Path(__file__).resolve().parents[1] / "sync-to-user-claude.py"
LEGACY_HOOK = (
    "#!/bin/sh\n# Written by vexjoy-agent install.sh — auto-syncs new items after git pull.\n"
    'for d in "$HOME/.claude" "$HOME/.codex"; do ln -s "$PWD/skills/alpha" "$d/skills/alpha"; done\n'
)


def _run(cwd: Path, home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k not in ("VEXJOY_SYNC_DISABLED", "PYTHONPATH")}
    # Fixture repos live under /tmp; only the ephemeral test keeps the default prefix.
    base["VEXINSTALL_EPHEMERAL_PREFIXES"] = "/nonexistent-ephemeral"
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=cwd,
        env={**base, "HOME": str(home), **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def _load():
    spec = importlib.util.spec_from_file_location("sync_hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def legacy_world(world: Env, monkeypatch: pytest.MonkeyPatch) -> Env:
    """World whose main checkout runs a pre-engine post-merge; git reads no host config."""
    (world.work / "global.gitconfig").write_text("")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(world.work / "global.gitconfig"))
    hook = world.repo / ".git" / "hooks" / "post-merge"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(LEGACY_HOOK, encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return world


def test_legacy_git_hook_warns_once_before_the_sync(legacy_world: Env, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mod = _load()
    monkeypatch.setattr(
        mod,
        "build_command",
        lambda _repo, _scripts: ([sys.executable, "-c", "print('[sync] claude: +0')"], dict(os.environ)),
    )
    monkeypatch.chdir(legacy_world.repo)
    assert mod.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2 and lines[1] == "[sync] claude: +0", lines
    assert lines[0].startswith("[sync] warning: legacy git hook ") and "delete it" in lines[0], lines


def test_worktree_session_warns_about_the_main_checkout_hook(legacy_world: Env) -> None:
    wt = legacy_world.work / "wt"
    subprocess.run(
        ["git", "-C", str(legacy_world.repo), "worktree", "add", "-q", str(wt)], check=True, capture_output=True
    )
    r = _run(wt, legacy_world.home)
    assert r.returncode == 0
    assert r.stdout.startswith("[sync] warning: legacy git hook "), r.stdout + r.stderr
    assert "git worktree" in r.stderr


def test_sync_runs_engine_and_prints_one_summary_line(world: Env) -> None:
    r = _run(world.repo, world.home)
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1 and lines[0].startswith("[sync] claude: +"), r.stdout
    assert (world.home / ".claude" / "vexjoy" / "ledger.json").is_file()
    assert (world.home / ".claude" / "skills" / "alpha").exists()


def test_home_inside_repo_is_skipped_without_writes(world: Env) -> None:
    before = repo_hash(world.repo)
    r = _run(world.repo, world.repo)
    assert r.returncode == 0
    assert "HOME resolves inside" in r.stderr
    assert repo_hash(world.repo) == before
    assert not (world.repo / ".claude" / "vexjoy").exists()
    assert not (world.repo / ".claude" / "skills").exists()


def test_ephemeral_checkout_is_skipped_without_writes(world: Env) -> None:
    r = _run(world.repo, world.home, VEXINSTALL_EPHEMERAL_PREFIXES=str(world.repo.parent))
    assert r.returncode == 0
    assert "ephemeral checkout" in r.stderr
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()


def test_worktree_is_skipped(world: Env) -> None:
    wt = world.work / "wt"
    subprocess.run(["git", "-C", str(world.repo), "worktree", "add", "-q", str(wt)], check=True, capture_output=True)
    r = _run(wt, world.home)
    assert r.returncode == 0
    assert "git worktree" in r.stderr
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()


def test_disabled_env_is_a_no_op(world: Env) -> None:
    r = _run(world.repo, world.home, VEXJOY_SYNC_DISABLED="1")
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert not (world.home / ".claude" / "vexjoy" / "ledger.json").exists()


def test_outside_toolkit_repo_is_a_no_op(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    r = _run(tmp_path, home)
    assert r.returncode == 0 and r.stdout == ""
    assert not (home / ".claude").exists()


def test_engine_failure_fails_open(world: Env, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mod = _load()
    monkeypatch.setattr(
        mod, "build_command", lambda _repo, _scripts: ([sys.executable, "-c", "raise SystemExit(9)"], {})
    )
    monkeypatch.chdir(world.repo)
    assert mod.main() == 0
    assert "exited 9" in capsys.readouterr().err


def test_internal_exception_fails_open(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mod = _load()

    def boom(_repo: Path) -> int:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(mod, "run", boom)
    assert mod.main() == 0
    assert "kaboom" in capsys.readouterr().err
