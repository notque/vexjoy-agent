#!/usr/bin/env python3
"""Tests for the cross-platform state lock and the post-merge deploy notice.

Covers ADR windows-locking-deploy-warning:
- The `_state_lock` context manager really serializes a read-modify-write on
  the current host (POSIX fcntl OR Windows msvcrt), so a parallel append loses
  no outcomes. (The big N=60/N=25 anchor lives in test_routing_decision_recorder
  TestBridgeConcurrency; this is the cheap direct unit.)
- On Windows the fcntl shim is no longer a no-op: a real lock backend is active.
- The generated post-merge hook is valid bash, prints the deploy-staleness
  notice guarded by a hooks/scripts diff-tree check, and always exits 0.

Run with: python3 -m pytest hooks/tests/test_routing_locking.py -v
"""

import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
REPO_ROOT = HOOKS_DIR.parent
INSTALL_SH = REPO_ROOT / "install.sh"

sys.path.insert(0, str(LIB_DIR))


# ---------------------------------------------------------------------------
# Fix 1 — the lock really serializes on THIS host (no no-op on Windows)
# ---------------------------------------------------------------------------


def test_state_lock_serializes_critical_section(tmp_path):
    """Concurrent threads each do a locked read-increment-write; the lock must
    serialize them so the final count equals the thread count.

    Without a real lock the increments interleave and the count is < n. On
    Windows the old no-op fcntl shim would fail this; the msvcrt fallback passes.
    """
    import routing_outcome_state as ros

    state = tmp_path / "lock.target"
    state.write_text("0")
    n = 40
    barrier = threading.Barrier(n)

    def worker():
        barrier.wait()
        with ros._state_lock(state):
            v = int(state.read_text())
            # widen the window where a lost update would happen
            state.write_text(str(v + 1))

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert int(state.read_text()) == n, "lock did not serialize the critical section"


# ---------------------------------------------------------------------------
# Fix 2 — generated git hooks: post-merge (sync via engine / sync hook, never
# links) and pre-commit (private-leak gate). Installer spec 5.1 and 7.5.
# ---------------------------------------------------------------------------


def _extract_git_hook(name: str) -> str:
    """Pull the heredoc body a generated git hook is written from."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(rf"_write_git_hook {name} << 'HOOK'\n(.*?)\nHOOK\n", text, re.DOTALL)
    assert m, f"could not find the {name} heredoc in install.sh"
    return m.group(1)


def _extract_post_merge_hook() -> str:
    return _extract_git_hook("post-merge")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("name", ["post-merge", "pre-commit"])
def test_generated_git_hooks_are_valid_bash(tmp_path, name):
    body = _extract_git_hook(name)
    hook_file = tmp_path / name
    hook_file.write_text(body, encoding="utf-8")
    r = subprocess.run(["bash", "-n", str(hook_file)], capture_output=True, text=True)
    assert r.returncode == 0, f"{name} hook is not valid bash: {r.stderr}"
    assert "Written by vexjoy-agent" in body, "marker line keeps re-installs from clobbering user hooks"


def test_post_merge_hook_syncs_and_never_links():
    body = _extract_post_merge_hook()
    assert "ln -s" not in body, "post-merge must never link anything itself (spec 5.1)"
    assert "-m vexinstall sync --target all" in body
    assert "sync-to-user-claude.py" not in body and "rollout" not in body, "no legacy path remains"


_LEGACY_HOOK = (
    "#!/usr/bin/env bash\n# Written by vexjoy-agent install.sh — auto-syncs new items after git pull.\n"
    'for item in "$REPO_DIR"/skills/*; do ln -s "$item" "$HOME/.claude/skills/"; done\n'
)
# Passes install.sh's version probe (`python -c ...`); fails every `-m vexinstall` call.
_PROBE_ONLY_PYTHON = '#!/bin/sh\n[ "$1" = -c ] && exit 0\nexit 1\n'
needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _install_world(tmp_path: Path, python: str = _PROBE_ONLY_PYTHON) -> tuple[Path, Path, dict[str, str]]:
    """install.sh in a fake checkout whose .git/hooks holds a legacy post-merge, and an env to run it.

    No real python runs: VEXJOY_PYTHON is the stub script *python*. HOME is a temp dir.
    """
    hooks = tmp_path / "repo" / ".git" / "hooks"
    hooks.mkdir(parents=True)
    script = tmp_path / "repo" / "install.sh"
    script.write_text(INSTALL_SH.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (hooks / "post-merge").write_text(_LEGACY_HOOK, encoding="utf-8", newline="\n")
    (hooks / "post-merge").chmod(0o755)
    stub = tmp_path / "python3"
    stub.write_text(python, encoding="utf-8", newline="\n")
    stub.chmod(0o755)
    (tmp_path / "home").mkdir()
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": "/usr/bin:/bin",
        "VEXJOY_PYTHON": stub.as_posix(),
        "VEXJOY_NO_DEPS": "1",
        "TERM": "dumb",
    }
    return script, hooks, env


def _bash(script: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", script.as_posix(), *args], capture_output=True, text=True, env=env, timeout=60)


@needs_bash
@pytest.mark.parametrize(
    ("python", "failure"),
    [
        pytest.param(_PROBE_ONLY_PYTHON, "vexinstall apply failed", id="apply-fails"),
        pytest.param("#!/bin/sh\nexit 1\n", "not a runnable python 3.10+", id="no-python-3.10"),
    ],
)
def test_git_hooks_install_before_python_and_apply(tmp_path, python, failure):
    """A failed install must not leave a pre-engine post-merge running on every pull."""
    script, hooks, env = _install_world(tmp_path, python)
    r = _bash(script, env)
    assert r.returncode == 1 and failure in r.stdout, r.stdout + r.stderr
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _extract_post_merge_hook() + "\n"
    assert (hooks / "pre-commit").is_file()


@needs_bash
@pytest.mark.parametrize("flag", ["--dry-run", "--configure-only"])
def test_runs_that_do_not_apply_write_no_git_hooks(tmp_path, flag):
    script, hooks, env = _install_world(tmp_path)
    _bash(script, env, flag)
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _LEGACY_HOOK
    assert not (hooks / "pre-commit").exists()


@needs_bash
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write a read-only file")
def test_unwritable_git_hook_warns_and_install_continues(tmp_path):
    script, hooks, env = _install_world(tmp_path)
    (hooks / "post-merge").chmod(0o444)
    try:
        r = _bash(script, env)
    finally:
        (hooks / "post-merge").chmod(0o644)
    assert "Could not write post-merge hook" in r.stdout, r.stdout + r.stderr
    assert "vexinstall apply failed" in r.stdout, r.stdout + r.stderr
    assert (hooks / "pre-commit").is_file()


@needs_bash
def test_git_hooks_skipped_with_a_note_when_dot_git_is_a_file(tmp_path):
    """A linked worktree or submodule: install.sh writes no hooks there and says so."""
    script, hooks, env = _install_world(tmp_path)
    shutil.rmtree(hooks.parent)
    (script.parent / ".git").write_text("gitdir: /elsewhere/.git/worktrees/repo\n", encoding="utf-8")
    r = _bash(script, env)
    assert "Git hooks skipped" in r.stdout, r.stdout + r.stderr
    assert "vexinstall apply failed" in r.stdout, r.stdout + r.stderr


# Pass install.sh's version probe and print each engine call: `uninstall` succeeds or fails.
_UNINSTALL_PYTHON = '#!/bin/sh\n[ "$1" = -c ] && exit 0\necho "engine: $*"\n[ "$3" = uninstall ]\n'
_FAILING_ENGINE_PYTHON = '#!/bin/sh\n[ "$1" = -c ] && exit 0\necho "engine: $*"\nexit 1\n'
_ENGINE_UNINSTALL = "engine: -m vexinstall uninstall --target all"


def _renamed(hooks: Path) -> list[str]:
    """Contents of the post-merge hooks that uninstalls renamed, oldest first."""
    return [p.read_text(encoding="utf-8") for p in sorted(hooks.glob("post-merge.vexjoy-removed.*"))]


@needs_bash
def test_uninstall_renames_our_hook_first_and_keeps_the_leak_gate(tmp_path):
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    ours = _extract_post_merge_hook() + "\n"
    (hooks / "post-merge").write_text(ours, encoding="utf-8", newline="\n")
    gate = _extract_git_hook("pre-commit") + "\n"
    (hooks / "pre-commit").write_text(gate, encoding="utf-8", newline="\n")
    r = _bash(script, env, "--uninstall")
    out = r.stdout
    assert r.returncode == 0, out + r.stderr
    assert not (hooks / "post-merge").exists()
    assert _renamed(hooks) == [ours]
    assert (hooks / "pre-commit").read_text(encoding="utf-8") == gate
    assert "Keeping pre-commit hook (the private-leak gate" in out, out
    assert "Renamed post-merge hook to" in out and _ENGINE_UNINSTALL in out, out
    assert out.index("Renamed post-merge hook to") < out.index(_ENGINE_UNINSTALL), out


@needs_bash
@pytest.mark.parametrize(
    ("python", "failure"),
    [
        pytest.param(_FAILING_ENGINE_PYTHON, _ENGINE_UNINSTALL, id="engine-fails"),
        pytest.param("#!/bin/sh\nexit 1\n", "not a runnable python 3.10+", id="no-python-3.10"),
    ],
)
def test_failed_uninstall_still_renames_our_hook(tmp_path, python, failure):
    """Neither a missing python nor a failed engine run may leave a hook that re-installs on the next pull."""
    script, hooks, env = _install_world(tmp_path, python)
    r = _bash(script, env, "--uninstall")
    assert r.returncode == 1 and failure in r.stdout, r.stdout + r.stderr
    assert not (hooks / "post-merge").exists()
    assert _renamed(hooks) == [_LEGACY_HOOK]
    assert not (hooks / "pre-commit").exists()


@needs_bash
def test_a_second_uninstall_keeps_the_first_renamed_hook(tmp_path):
    """Uninstall, ./install.sh, uninstall: lines a user added to the first hook must survive."""
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    edited = _LEGACY_HOOK + "echo my own line\n"
    for second, body in (("00", edited), ("01", _LEGACY_HOOK)):
        (hooks / "post-merge").write_text(body, encoding="utf-8", newline="\n")
        # bash imports BASH_FUNC_<name>%% from the environment: a fixed clock for each run.
        clock = {"BASH_FUNC_date%%": f"() {{ echo 20261107T1200{second}Z; }}"}
        r = _bash(script, {**env, **clock}, "--uninstall")
        assert r.returncode == 0, r.stdout + r.stderr
    assert _renamed(hooks) == [edited, _LEGACY_HOOK]


@needs_bash
def test_uninstall_keeps_unmarked_hooks(tmp_path):
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    mine = "#!/bin/sh\necho my own hook\n"
    for name in ("post-merge", "pre-commit"):
        (hooks / name).write_text(mine, encoding="utf-8", newline="\n")
    r = _bash(script, env, "--uninstall")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [(hooks / n).read_text(encoding="utf-8") for n in ("post-merge", "pre-commit")] == [mine, mine]
    for name in ("post-merge", "pre-commit"):
        assert f"Keeping {name} hook (not written by vexjoy-agent)" in r.stdout, r.stdout


@needs_bash
def test_uninstall_with_a_target_keeps_the_hook(tmp_path):
    """`sync --target all` re-installs the one target either way, and still syncs the targets left."""
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    r = _bash(script, env, "--uninstall", "--target", "codex")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _LEGACY_HOOK
    assert "Keeping post-merge hook (a --target uninstall keeps it" in r.stdout, r.stdout
    assert "engine: -m vexinstall uninstall --target codex" in r.stdout, r.stdout


@needs_bash
def test_uninstall_dry_run_renames_no_hook(tmp_path):
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    r = _bash(script, env, "--uninstall", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(p.name for p in hooks.iterdir()) == ["post-merge"]
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _LEGACY_HOOK
    assert "Would rename post-merge hook to" in r.stdout, r.stdout
    engine = [line for line in r.stdout.splitlines() if line.startswith(_ENGINE_UNINSTALL)]
    assert len(engine) == 1 and " --dry-run" in engine[0], r.stdout


@needs_bash
def test_uninstall_leaves_hooks_alone_with_no_git_hooks_set(tmp_path):
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    r = _bash(script, {**env, "VEXJOY_NO_GIT_HOOKS": "1"}, "--uninstall")
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(p.name for p in hooks.iterdir()) == ["post-merge"]
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _LEGACY_HOOK
    assert "Git hooks skipped (VEXJOY_NO_GIT_HOOKS=1)" in r.stdout, r.stdout


@needs_bash
@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_uninstall_from_a_worktree_renames_the_main_checkout_hook(tmp_path):
    """Git runs the main checkout's hooks for merges in every linked worktree."""
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    git_env = {**os.environ, "HOME": env["HOME"], "GIT_CONFIG_NOSYSTEM": "1"}
    git = ["git", "-C", str(script.parent), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "init"], ["worktree", "add", "-q", "../wt"]):
        subprocess.run([*git, *args], check=True, env=git_env, capture_output=True)
    wt_script = tmp_path / "wt" / "install.sh"
    wt_script.write_text(script.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    # Git for Windows keeps git in /mingw64/bin, not /usr/bin.
    r = _bash(wt_script, {**env, "PATH": env["PATH"] + ":/mingw64/bin"}, "--uninstall")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (hooks / "post-merge").exists()
    assert _renamed(hooks) == [_LEGACY_HOOK]


@needs_bash
def test_uninstall_fails_when_git_cannot_read_dot_git(tmp_path):
    """The main checkout's hook may still run, so say where to finish, before and after the engine, and exit 1."""
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    shutil.rmtree(hooks.parent)
    (script.parent / ".git").write_text("gitdir: /elsewhere/.git/worktrees/repo\n", encoding="utf-8")
    r = _bash(script, env, "--uninstall")
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout.count("run ./install.sh --uninstall in the main checkout too") == 2, r.stdout
    assert _ENGINE_UNINSTALL in r.stdout, r.stdout


@needs_bash
def test_hook_that_cannot_be_renamed_fails_the_uninstall(tmp_path):
    script, hooks, env = _install_world(tmp_path, _UNINSTALL_PYTHON)
    # bash imports BASH_FUNC_<name>%% from the environment: here mv fails for the post-merge hook.
    mv_fails = '() { case "$*" in *post-merge*) return 1 ;; *) command mv "$@" ;; esac; }'
    r = _bash(script, {**env, "BASH_FUNC_mv%%": mv_fails}, "--uninstall")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Could not rename post-merge hook" in r.stdout and "is still in place" in r.stdout, r.stdout
    assert _ENGINE_UNINSTALL in r.stdout, r.stdout
    assert (hooks / "post-merge").read_text(encoding="utf-8") == _LEGACY_HOOK


def _post_merge_world(tmp_path: Path, *, fail: bool = False) -> tuple[Path, Path]:
    """Fake checkout with a stub vexinstall package that logs its argv."""
    repo = tmp_path / "repo"
    log = tmp_path / "calls.log"
    pkg = repo / "scripts" / "vexinstall"
    pkg.mkdir(parents=True)
    (repo / ".git" / "hooks").mkdir(parents=True)
    logger = (
        f"import sys\nwith open({str(log)!r}, 'a') as f:\n    f.write('vexinstall ' + ' '.join(sys.argv[1:]) + '\\n')\n"
    )
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text(logger + ("raise SystemExit(3)\n" if fail else ""))
    hook = repo / ".git" / "hooks" / "post-merge"
    hook.write_text(_extract_post_merge_hook(), encoding="utf-8")
    hook.chmod(0o755)
    return hook, log


def _run_post_merge(hook: Path, tmp_path: Path) -> tuple[int, list[str]]:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home")}
    r = subprocess.run(["bash", str(hook)], capture_output=True, text=True, env=env, timeout=60)
    log = tmp_path / "calls.log"
    return r.returncode, log.read_text().splitlines() if log.exists() else []


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_post_merge_calls_only_vexinstall_sync_all(tmp_path):
    hook, _ = _post_merge_world(tmp_path)
    rc, calls = _run_post_merge(hook, tmp_path)
    repo = hook.parents[2]
    assert rc == 0
    assert calls == [f"vexinstall sync --target all --source-root {repo}"], calls


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_post_merge_engine_failure_still_exits_zero(tmp_path):
    hook, _ = _post_merge_world(tmp_path, fail=True)
    rc, calls = _run_post_merge(hook, tmp_path)
    assert rc == 0
    assert len(calls) == 1 and calls[0].startswith("vexinstall sync --target all"), calls


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
@pytest.mark.parametrize(("checker_rc", "hook_rc"), [(0, 0), (1, 1), (2, 0)])
def test_pre_commit_hook_blocks_only_on_leak(tmp_path, checker_rc, hook_rc):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "scripts" / "check-private-leak.py").write_text(f"import sys\nsys.exit({checker_rc})\n")
    hook = tmp_path / "pre-commit"
    hook.write_text(_extract_git_hook("pre-commit"), encoding="utf-8")
    r = subprocess.run(["bash", str(hook)], cwd=repo, capture_output=True, text=True)
    assert r.returncode == hook_rc, r.stderr
