"""Read-only git helpers: checkout shape, file listings, status."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from .common import DEFAULT_EPHEMERAL, EPHEMERAL_ENV, is_inside, realpath


def _git(root: Path, *args: str, timeout: float = 60) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", "surrogateescape")


def is_git_checkout(root: Path, *, timeout: float = 60) -> bool:
    """True when *root* is the top of a git working tree."""
    top = _git(root, "rev-parse", "--show-toplevel", timeout=timeout)
    return top is not None and realpath(top.strip()) == realpath(root)


def is_worktree(root: Path) -> bool:
    """True when *root* is a linked git worktree (not the main working tree)."""
    dot_git = root / ".git"
    if dot_git.is_file():
        try:
            if "worktrees/" in dot_git.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            return True
    git_dir = _git(root, "rev-parse", "--git-dir")
    common = _git(root, "rev-parse", "--git-common-dir")
    if git_dir is None or common is None:
        return dot_git.is_file()
    gd = git_dir.strip()
    cd = common.strip()
    gd_abs = gd if os.path.isabs(gd) else os.path.join(str(root), gd)
    cd_abs = cd if os.path.isabs(cd) else os.path.join(str(root), cd)
    return realpath(gd_abs) != realpath(cd_abs)


def _abs_path(root: Path, out: str | None) -> Path | None:
    """A path git printed under ``git -C root``, made absolute against *root*."""
    raw = (out or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else root / path


def hooks_dir(root: Path) -> Path | None:
    """The dir git runs hooks from for the working tree at *root*, or None.

    ``core.hooksPath`` when set (``~`` expanded; a relative value is relative
    to *root*, where git runs a working tree's hooks), else
    ``git rev-parse --git-path hooks``, which maps a linked worktree (``.git``
    is a file) to the common dir. None when *root* is not the top of a working
    tree, so a global ``core.hooksPath`` never applies to a plain directory.
    """
    if not is_git_checkout(root):
        return None
    configured = _abs_path(root, _git(root, "config", "--path", "--get", "core.hooksPath"))
    return configured or _abs_path(root, _git(root, "rev-parse", "--git-path", "hooks"))


def ephemeral_prefixes() -> list[str]:
    """Realpath prefixes treated as ephemeral (default ``/tmp`` plus system temp dir on Windows)."""
    raw = os.environ.get(EPHEMERAL_ENV)
    if raw is None:
        prefixes = [DEFAULT_EPHEMERAL]
        if os.name == "nt":
            import tempfile

            prefixes.append(tempfile.gettempdir())
        return [realpath(p) for p in prefixes if p]
    sep = os.pathsep if os.pathsep in raw else ":"
    return [realpath(p) for p in raw.split(sep) if p]


def is_ephemeral(path: Path) -> bool:
    """True when *path* resolves under an ephemeral prefix."""
    rp = realpath(path)
    return any(is_inside(rp, prefix) for prefix in ephemeral_prefixes())


@lru_cache(maxsize=16)
def _ls_files_cached(root: str) -> tuple[str, ...] | None:
    out = _git(Path(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is None:
        return None
    return tuple(sorted({p for p in out.split("\0") if p}))


def ls_files(root: Path) -> tuple[str, ...] | None:
    """Tracked plus untracked-not-ignored files (POSIX, relative), or None."""
    return _ls_files_cached(realpath(root))


def tracked_files(root: Path) -> list[str]:
    """Tracked files only (``git ls-files``)."""
    out = _git(root, "ls-files", "-z")
    return [p for p in (out or "").split("\0") if p]


def status_porcelain(root: Path) -> list[str]:
    """``git status --porcelain`` lines (empty list when clean or not a repo)."""
    out = _git(root, "status", "--porcelain")
    return [line for line in (out or "").splitlines() if line.strip()]


def diff_head(root: Path, rel: str, stat_only: bool) -> str:
    """``git diff HEAD -- rel`` (or ``--stat``)."""
    args = ["diff", "HEAD"]
    if stat_only:
        args.append("--stat")
    return _git(root, *args, "--", rel) or ""


def checkout_head(root: Path, rel: str) -> bool:
    """``git checkout HEAD -- rel``; True on success."""
    return _git(root, "checkout", "HEAD", "--", rel) is not None


def clear_cache() -> None:
    """Drop cached listings (tests mutate fixture repos)."""
    _ls_files_cached.cache_clear()


# The stale-source check runs inside the SessionStart sync (20 s budget): each git call gets 3 s.
_QUICK_S = 3


def _git_rc(root: Path, *args: str) -> int | None:
    """Exit code of a quick git command, or None when git cannot run or times out."""
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=_QUICK_S).returncode
    except (OSError, subprocess.SubprocessError):
        return None


def _quick(root: Path, *args: str) -> str | None:
    return _git(root, *args, timeout=_QUICK_S)


def head(root: Path) -> str | None:
    """Commit id of HEAD, or None."""
    out = _quick(root, "rev-parse", "--verify", "-q", "HEAD")
    return out.strip() if out else None


def behind_upstream(root: Path) -> int | None:
    """Commits the local tracking ref of HEAD's upstream has that HEAD lacks. Never fetches.

    None when there is no upstream or git fails.
    """
    out = _quick(root, "rev-list", "--count", "HEAD..@{upstream}")
    try:
        return int(out.strip()) if out else None
    except ValueError:
        return None


def is_ancestor(root: Path, older: str, newer: str) -> bool:
    """True when commit *older* is an ancestor of *newer* in the repo at *root*."""
    return _git_rc(root, "merge-base", "--is-ancestor", older, newer) == 0


def stale_source(ledger_root: Path, session_root: Path | None) -> str | None:
    """Why the installed source clone is out of date, or None. Local refs only: no fetch.

    Behind: its upstream tracking ref has commits HEAD lacks, or its HEAD is an older commit of
    the session's checkout and that checkout's HEAD is merged: reachable from the checkout's
    own copy of the clone's upstream ref (``origin/main``). Unmerged work on a feature branch or
    worktree, pushed or not, never counts. Never raises.
    """
    if not is_git_checkout(ledger_root, timeout=_QUICK_S):
        return None
    n = behind_upstream(ledger_root)
    if n:
        return f"{n} commit(s) behind its upstream"
    if session_root is None or realpath(session_root) == realpath(ledger_root):
        return None
    if not is_git_checkout(session_root, timeout=_QUICK_S):
        return None
    old, new = head(ledger_root), head(session_root)
    if not old or not new or old == new:
        return None
    # Merged means: the checkout's HEAD is in its own copy of the branch the clone tracks
    # (``origin/main``). A pushed feature branch has an upstream too, but is not merged.
    up = _quick(ledger_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    up = up.strip() if up else ""
    if up and is_ancestor(session_root, old, new) and is_ancestor(session_root, "HEAD", up):
        return f"behind the checkout {session_root}"
    return None
