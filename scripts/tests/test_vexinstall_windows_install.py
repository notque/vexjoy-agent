"""Windows install failures: hosts that refuse symlinks, and dirs that running hooks keep busy."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import Env, commit_all, world

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import fsops, interp, plan


def _winerror(code: int) -> OSError:
    """An OSError carrying *code* as winerror on every platform (the attribute is real only on Windows)."""
    return type("WinError", (OSError,), {"winerror": code})(13, f"winerror {code}")


def _deny_symlinks(monkeypatch: pytest.MonkeyPatch, exc: BaseException) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise exc

    monkeypatch.setattr(os, "symlink", refuse)


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(fsops.time, "sleep", slept.append)
    return slept


def _flaky(monkeypatch: pytest.MonkeyPatch, name: str, failures: int, make: Callable[[], OSError]) -> None:
    """Make ``os.<name>`` raise ``make()`` for its first *failures* calls, then behave."""
    real = getattr(os, name)
    calls: list[str] = []

    def op(src: object, dst: object) -> None:
        calls.append(os.fspath(src))
        if len(calls) <= failures:
            raise make()
        real(src, dst)

    monkeypatch.setattr(os, name, op)


@pytest.fixture(autouse=True)
def _fresh_probe() -> Iterator[None]:
    fsops.symlinks_supported.cache_clear()
    yield
    fsops.symlinks_supported.cache_clear()


def _trash(tmp_path: Path) -> tuple[fsops.Trash, Path, Path]:
    home = tmp_path / "home"
    item = home / ".claude" / "hooks"
    item.mkdir(parents=True)
    (item / "h.py").write_text("# h\n")
    return fsops.Trash(tmp_path / "trash", "20261107T000000Z", fsops.Guard()), home, item


# ---------------------------------------------------------------- hosts that refuse symlinks


@pytest.mark.parametrize(
    "make",
    [lambda: _winerror(1314), lambda: _winerror(50), NotImplementedError],
    ids=["winerror-1314", "winerror-50", "not-implemented"],
)
def test_default_mode_copies_when_the_host_refuses_symlinks(
    world: Env, monkeypatch: pytest.MonkeyPatch, make: Callable[[], BaseException]
) -> None:
    _deny_symlinks(monkeypatch, make())
    assert fsops.symlinks_supported() is False
    assert plan.default_mode(world.repo) == "copy"


def test_default_mode_links_a_main_checkout_when_the_host_allows_symlinks(world: Env) -> None:
    if not fsops.symlinks_supported():
        pytest.skip("this host refuses symlinks")
    assert plan.default_mode(world.repo) == "symlink"


def test_symlink_probe_runs_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    real = os.symlink

    def counting(*args: object, **kwargs: object) -> None:
        calls.append(args)
        real(*args, **kwargs)

    monkeypatch.setattr(os, "symlink", counting)
    assert fsops.symlinks_supported() == fsops.symlinks_supported()
    assert len(calls) == 1


def test_fresh_apply_copies_everything_when_the_host_refuses_symlinks(
    world: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the probe, a fresh Windows install died on its first skill link with WinError 1314."""
    _deny_symlinks(monkeypatch, _winerror(1314))
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert world.ledger()["mode"] == "copy"
    root = world.root("claude")
    assert [p for p in root.rglob("*") if p.is_symlink()] == []
    assert (world.skills("claude") / "alpha" / "SKILL.md").is_file()
    assert interp.read_pin(interp.link_path(world.home)).kind == "script"


# ---------------------------------------------------------------- dirs that running hooks keep busy


def test_trash_move_retries_while_windows_reports_the_dir_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trash, home, item = _trash(tmp_path)
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "rename", 2, lambda: _winerror(5))
    moved = trash.move(item, home, "replaced")
    assert not item.exists() and (moved / "h.py").read_text() == "# h\n"
    assert slept == [0.05, 0.1]


def test_trash_move_gives_up_after_about_three_seconds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trash, home, item = _trash(tmp_path)
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "rename", 99, lambda: _winerror(32))
    with pytest.raises(OSError):
        trash.move(item, home, "replaced")
    assert (item / "h.py").is_file()
    assert slept == list(fsops._BUSY_DELAYS) and sum(slept) < 3.5


@pytest.mark.parametrize(
    "make",
    [lambda: PermissionError(13, "denied"), lambda: _winerror(1314)],
    ids=["no-winerror", "other-winerror"],
)
def test_other_rename_errors_fail_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make: Callable[[], OSError]
) -> None:
    trash, home, item = _trash(tmp_path)
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "rename", 1, make)
    with pytest.raises(OSError):
        trash.move(item, home, "replaced")
    assert slept == [] and item.is_dir()


def test_atomic_write_retries_a_busy_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "replace", 1, lambda: _winerror(32))
    dest = tmp_path / "state" / "settings.json"
    fsops.atomic_write_bytes(dest, b"{}\n", fsops.Guard())
    assert dest.read_bytes() == b"{}\n" and slept == [0.05]
    assert [p.name for p in dest.parent.iterdir()] == ["settings.json"]


def test_busy_hooks_dir_stays_in_place_until_a_later_sync(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The new copy is staged first, so a dir Windows keeps busy is never left missing."""
    assert world.run("apply", "--target", "claude", "--mode", "copy").code == 0
    hooks = world.root("claude") / "hooks"
    old = (hooks / "h1.py").read_text()
    (world.repo / "hooks" / "h1.py").write_text("# hook h1.py v2\n", encoding="utf-8")
    commit_all(world.repo, "bump h1")

    slept = _no_sleep(monkeypatch)
    real = os.rename

    def busy_hooks(src: object, dst: object) -> None:
        if os.fspath(src) == os.fspath(hooks):
            raise _winerror(5)
        real(src, dst)

    monkeypatch.setattr(os, "rename", busy_hooks)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any("engine error" in line for line in res.err), res.err
    assert (hooks / "h1.py").read_text() == old
    assert [p.name for p in hooks.parent.iterdir() if p.name.startswith(".hooks.vexinstall-")] == []
    assert slept == list(fsops._BUSY_DELAYS)

    monkeypatch.setattr(os, "rename", real)
    assert world.run("sync", "--target", "claude").code == 0
    assert (hooks / "h1.py").read_text() == "# hook h1.py v2\n"
