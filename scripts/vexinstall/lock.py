"""fcntl.flock on ``~/.claude/vexjoy/lock``."""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .common import LockTimeoutError
from .fsops import Guard, mkdirs


class LockHeld(Exception):
    """Non-blocking acquire found the lock held."""


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
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
