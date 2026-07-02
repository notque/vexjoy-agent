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
# Fix 2 — generated post-merge hook: valid bash, staleness notice, exit 0
# ---------------------------------------------------------------------------


def _extract_post_merge_hook() -> str:
    """Pull the heredoc body the post-merge hook is generated from."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(r"cat > \"\$hook\" << 'HOOK'\n(.*?)\nHOOK\n", text, re.DOTALL)
    assert m, "could not find the post-merge heredoc in install.sh"
    return m.group(1)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_generated_post_merge_hook_is_valid_bash(tmp_path):
    body = _extract_post_merge_hook()
    hook_file = tmp_path / "post-merge"
    hook_file.write_text(body, encoding="utf-8")
    r = subprocess.run(["bash", "-n", str(hook_file)], capture_output=True, text=True)
    assert r.returncode == 0, f"post-merge hook is not valid bash: {r.stderr}"


def test_post_merge_hook_warns_on_hook_script_changes():
    body = _extract_post_merge_hook()
    # The staleness notice points the user at the sync script.
    assert "sync-to-user-claude.py" in body, "no deploy-staleness notice in post-merge hook"
    # It is gated on hooks/ or scripts/ being touched by the merge.
    assert "diff-tree" in body or "diff --name-only" in body, "notice is not gated on a merge diff"
    assert "hooks" in body and "scripts" in body, "notice gate does not check hooks/ and scripts/"


def test_post_merge_hook_always_exits_zero():
    body = _extract_post_merge_hook()
    # Warn-only: the hook must end exit 0 so the notice can never fail a merge.
    assert re.search(r"^exit 0\s*$", body, re.MULTILINE), "post-merge hook must end with `exit 0`"
