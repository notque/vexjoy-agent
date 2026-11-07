"""The engine lock excludes a second holder on every platform (fcntl on POSIX, msvcrt on Windows)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall.common import LockTimeoutError
from vexinstall.fsops import Guard
from vexinstall.lock import LockHeld, engine_lock


def test_second_holder_is_refused_until_the_first_releases(tmp_path: Path) -> None:
    path = tmp_path / "lock"
    guard = Guard()
    with (
        engine_lock(path, guard, blocking=False, timeout=0),
        pytest.raises(LockHeld),
        engine_lock(path, guard, blocking=False, timeout=0),
    ):
        pytest.fail("a second holder took the lock")
    with engine_lock(path, guard, blocking=False, timeout=0):
        pass


def test_blocking_acquire_times_out_while_held(tmp_path: Path) -> None:
    path = tmp_path / "lock"
    guard = Guard()
    with (
        engine_lock(path, guard, blocking=False, timeout=0),
        pytest.raises(LockTimeoutError),
        engine_lock(path, guard, blocking=True, timeout=0.3),
    ):
        pytest.fail("a blocking acquire took a held lock")
