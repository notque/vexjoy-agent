"""Exclusive lock on ``~/.claude/vexjoy/lock``: ``fcntl.flock``, or ``msvcrt.locking`` on Windows."""

from __future__ import annotations

import errno
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .common import LockTimeoutError
from .fsops import Guard, mkdirs

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class LockHeld(Exception):
    """Non-blocking acquire found the lock held."""


def _try_lock(fd: int) -> None:
    """Take the lock without waiting. Raise BlockingIOError when another holder has it."""
    if os.name != "nt":
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    os.lseek(fd, 0, os.SEEK_SET)  # msvcrt locks bytes from the current offset
    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        # LK_NBLCK reports a byte another handle holds as EACCES. Never name errno.EDEADLOCK
        # (LK_LOCK giving up): macOS has no such attribute, and the engine imports this module.
        if exc.errno != errno.EACCES:
            raise
        raise BlockingIOError(exc.errno, str(exc)) from exc


def _unlock(fd: int) -> None:
    if os.name != "nt":
        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


@contextmanager
def engine_lock(path: Path, guard: Guard, *, blocking: bool, timeout: float) -> Iterator[None]:
    """Hold the engine lock. Non-blocking raises LockHeld; blocking times out."""
    guard.check(path)
    mkdirs(path.parent, guard)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _try_lock(fd)
                break
            except BlockingIOError:
                if not blocking:
                    raise LockHeld(str(path)) from None
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"lock {path} held for more than {timeout:.0f}s") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
