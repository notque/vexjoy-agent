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


def test_lock_backend_not_noop_on_windows():
    """On Windows the fallback must be a REAL lock, not the old no-op shim.

    Asserts the module exposes `_acquire_lock`/`_release_lock` helpers, and on
    Windows inspects the helper source for a real backend (msvcrt/fcntl), never
    a return-None stub. No lock is acquired on any platform.
    TODO: add a real cross-platform lock acquisition test (acquire on a temp
    fd, assert a second acquisition blocks or raises).
    """
    import routing_outcome_state as ros

    assert hasattr(ros, "_acquire_lock"), "expected a _acquire_lock helper"
    assert hasattr(ros, "_release_lock"), "expected a _release_lock helper"
    if sys.platform == "win32":
        # The Windows backend must NOT be the no-op: locking twice from the same
        # process on the same byte range raises (msvcrt is process-exclusive) OR
        # at minimum the helper is the msvcrt variant, never a return-None stub.
        import inspect

        src = inspect.getsource(ros._acquire_lock)
        assert "msvcrt" in src or "fcntl" in src, "Windows lock fallback is still a no-op"


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


def test_post_merge_hook_always_exits_zero():
    body = _extract_post_merge_hook()
    assert re.search(r"^exit 0\s*$", body, re.MULTILINE), "post-merge hook must end with `exit 0`"


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
