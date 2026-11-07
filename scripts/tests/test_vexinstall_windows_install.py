"""Windows install failures: links need Developer Mode, and running programs keep paths busy."""

from __future__ import annotations

import json
import os
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import Env, commit_all, world

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import apply as apply_mod
from vexinstall import fsops, interp, plan

REAL_RENAME = os.rename
OLD_H1 = "# hook h1.py\n"
NEW_H1 = "# hook h1.py v2\n"


def _winerror(code: int) -> OSError:
    """An OSError carrying *code* as winerror on every platform (the attribute is real only on Windows)."""
    return type("WinError", (OSError,), {"winerror": code})(13, f"winerror {code}")


def _deny_symlinks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Act like Windows without Developer Mode: os.symlink fails with WinError 1314."""

    def refuse(*_a: object, **_k: object) -> None:
        raise _winerror(1314)

    monkeypatch.setattr(os, "symlink", refuse)


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the retry sleeps of fsops instead of sleeping. The time module itself stays as it is."""
    slept: list[float] = []
    monkeypatch.setattr(fsops, "time", types.SimpleNamespace(sleep=slept.append))
    return slept


def _flaky(monkeypatch: pytest.MonkeyPatch, name: str, failures: int, make: Callable[[], OSError]) -> None:
    """Make ``os.<name>`` raise ``make()`` for its first *failures* calls, then behave."""
    real = getattr(os, name)
    errors = [make() for _ in range(failures)]

    def op(src: object, dst: object) -> None:
        if errors:
            raise errors.pop()
        real(src, dst)

    monkeypatch.setattr(os, name, op)


def _refuse_renames(monkeypatch: pytest.MonkeyPatch, refused: Callable[[str, str], bool]) -> None:
    """Make os.rename fail as busy (WinError 5) whenever ``refused(src, dst)`` is true."""

    def rename(src: object, dst: object) -> None:
        if refused(os.fspath(src), os.fspath(dst)):
            raise _winerror(5)
        REAL_RENAME(src, dst)

    monkeypatch.setattr(os, "rename", rename)


def _trash(tmp_path: Path) -> tuple[fsops.Trash, Path, Path]:
    home = tmp_path / "home"
    item = home / ".claude" / "hooks"
    item.mkdir(parents=True)
    (item / "h.py").write_text("# h\n")
    return fsops.Trash(tmp_path / "trash", "20261107T000000Z", fsops.Guard()), home, item


def _copy_install(world: Env, changes: dict[str, str]) -> Path:
    """Copy-install the claude target, commit *changes* (repo path to text), and return its hooks dir."""
    assert world.run("apply", "--target", "claude", "--mode", "copy").code == 0
    for rel, text in changes.items():
        (world.repo / rel).write_text(text, encoding="utf-8")
    if changes:
        commit_all(world.repo, "change sources")
    return world.root("claude") / "hooks"


def _leftovers(hooks: Path) -> list[str]:
    """Staged or temp siblings left beside the entries of the claude root."""
    return [p.name for p in hooks.parent.iterdir() if ".vexinstall-" in p.name]


def _trash_records(world: Env, path: Path) -> list[dict[str, str]]:
    trash = world.home / ".claude" / "vexjoy" / "trash"
    return [
        item
        for manifest in trash.glob("*/manifest.json")
        for item in json.loads(manifest.read_text(encoding="utf-8"))["items"]
        if item["original"] == str(path)
    ]


# ---------------------------------------------------------------- Windows installs copies


def test_default_mode_copies_on_windows(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plan, "_WINDOWS", True)
    assert plan.default_mode(world.repo) == "copy"


def test_default_mode_links_a_main_checkout_elsewhere(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plan, "_WINDOWS", False)
    assert plan.default_mode(world.repo) == "symlink"


def test_fresh_windows_install_copies_everything(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """Before, a fresh Windows install picked symlink mode and died on its first link with WinError 1314."""
    monkeypatch.setattr(plan, "_WINDOWS", True)
    _deny_symlinks(monkeypatch)
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert world.ledger()["mode"] == "copy"
    assert [p for p in world.root("claude").rglob("*") if p.is_symlink()] == []
    assert (world.skills("claude") / "alpha" / "SKILL.md").is_file()
    assert interp.read_pin(interp.link_path(world.home)).kind == "script"


# ---------------------------------------------------------------- renames retry while Windows reports a path busy


def test_trash_move_retries_while_windows_reports_the_dir_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trash, home, item = _trash(tmp_path)
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "rename", 2, lambda: _winerror(5))
    moved = trash.move(item, home, "replaced")
    assert not item.exists() and (moved / "h.py").read_text() == "# h\n"
    assert slept == [0.05, 0.1]


def test_trash_move_gives_up_after_about_three_seconds_and_drops_its_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trash, home, item = _trash(tmp_path)
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "rename", 99, lambda: _winerror(32))
    with pytest.raises(OSError):
        trash.move(item, home, "replaced")
    assert (item / "h.py").is_file()
    assert slept == list(fsops._BUSY_DELAYS) and sum(slept) < 3.5
    assert json.loads((trash.dir / "manifest.json").read_text(encoding="utf-8"))["items"] == []


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


def test_trash_manifest_names_a_move_before_the_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run killed between the two leaves a record restore-trash skips, never an entry nothing points to."""
    trash, home, item = _trash(tmp_path)
    seen: list[list[str]] = []

    def rename(src: object, dst: object) -> None:
        items = json.loads((trash.dir / "manifest.json").read_text(encoding="utf-8"))["items"]
        seen.append([i["trashed"] for i in items])
        REAL_RENAME(src, dst)

    monkeypatch.setattr(os, "rename", rename)
    moved = trash.move(item, home, "replaced")
    assert seen == [[str(moved)]]


def test_atomic_write_retries_a_busy_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slept = _no_sleep(monkeypatch)
    _flaky(monkeypatch, "replace", 1, lambda: _winerror(32))
    dest = tmp_path / "state" / "settings.json"
    fsops.atomic_write_bytes(dest, b"{}\n", fsops.Guard())
    assert dest.read_bytes() == b"{}\n" and slept == [0.05]
    assert [p.name for p in dest.parent.iterdir()] == ["settings.json"]


# ---------------------------------------------------------------- a failed entry stays as it was, and the run goes on


def test_busy_dir_keeps_its_entry_while_the_rest_of_the_sync_runs(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    hooks = _copy_install(world, {"hooks/h1.py": NEW_H1, "agents/b-eng.md": "# b-eng v2\n"})
    agent = world.root("claude") / "agents" / "b-eng.md"
    slept = _no_sleep(monkeypatch)
    _refuse_renames(monkeypatch, lambda src, _dst: src == str(hooks))

    res = world.run("sync", "--target", "claude")
    assert res.code == 0
    assert any(line.startswith("[sync] warning:") and str(hooks) in line and "in use" in line for line in res.err), (
        res.err
    )
    assert (hooks / "h1.py").read_text() == OLD_H1 and agent.read_text() == "# b-eng v2\n"
    assert slept == list(fsops._BUSY_DELAYS)
    assert _leftovers(hooks) == [] and _trash_records(world, hooks) == []

    res = world.run("apply", "--target", "claude")
    assert res.code == 1 and any(str(hooks) in line for line in res.err), res.err

    monkeypatch.setattr(os, "rename", REAL_RENAME)
    assert world.run("sync", "--target", "claude").code == 0
    assert (hooks / "h1.py").read_text() == NEW_H1


def test_a_failed_step_still_saves_the_ledger(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the save, an entry replaced before the failure kept its old hash, read as a user edit,
    and stopped updating."""
    _copy_install(world, {"agents/b-eng.md": "# b-eng v2\n"})
    agent = world.root("claude") / "agents" / "b-eng.md"
    real = apply_mod.apply_settings

    def full_disk(*_a: object, **_k: object) -> dict:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(apply_mod, "apply_settings", full_disk)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any("run stopped early" in line for line in res.err), res.err
    assert agent.read_text() == "# b-eng v2\n"
    assert world.run("apply", "--target", "claude").code == 1

    monkeypatch.setattr(apply_mod, "apply_settings", real)
    (world.repo / "agents" / "b-eng.md").write_text("# b-eng v3\n", encoding="utf-8")
    commit_all(world.repo, "b-eng v3")
    assert world.run("sync", "--target", "claude").code == 0
    assert agent.read_text() == "# b-eng v3\n"


# ---------------------------------------------------------------- a replace never leaves its dest missing


def test_a_staging_failure_leaves_the_old_dir_alone(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The new copy is staged before anything moves, so a copy that fails midway touches nothing."""
    hooks = _copy_install(world, {"hooks/h1.py": NEW_H1})
    real = fsops._copy_file

    def full_disk(src: Path, dst: Path) -> None:
        if Path(dst).name == "h2.py":
            raise OSError(28, "No space left on device")
        real(src, dst)

    monkeypatch.setattr(fsops, "_copy_file", full_disk)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any(str(hooks) in line for line in res.err), res.err
    assert (hooks / "h1.py").read_text() == OLD_H1 and (hooks / "h2.py").is_file()
    assert _leftovers(hooks) == [] and _trash_records(world, hooks) == []


def test_a_manifest_that_cannot_be_written_moves_nothing(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The trash records a move before it happens, so a failed record leaves the old dir in place."""
    hooks = _copy_install(world, {"hooks/h1.py": NEW_H1})
    real = fsops.atomic_write_json

    def full_disk(dest: Path, obj: object, guard: fsops.Guard, mode: int = 0o644) -> None:
        if Path(dest).name == "manifest.json":
            raise OSError(28, "No space left on device")
        real(dest, obj, guard, mode)

    monkeypatch.setattr(fsops, "atomic_write_json", full_disk)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any(str(hooks) in line for line in res.err), res.err
    assert (hooks / "h1.py").read_text() == OLD_H1 and _leftovers(hooks) == []


def test_old_entry_comes_back_when_the_staged_copy_cannot_be_placed(
    world: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    hooks = _copy_install(world, {"hooks/h1.py": NEW_H1})
    _no_sleep(monkeypatch)
    _refuse_renames(monkeypatch, lambda src, _dst: os.path.basename(src).startswith(".hooks.vexinstall-"))
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any(str(hooks) in line for line in res.err), res.err
    assert (hooks / "h1.py").read_text() == OLD_H1
    assert _leftovers(hooks) == [] and _trash_records(world, hooks) == []

    monkeypatch.setattr(os, "rename", REAL_RENAME)
    assert world.run("sync", "--target", "claude").code == 0
    assert (hooks / "h1.py").read_text() == NEW_H1


def test_an_entry_that_cannot_come_back_is_named_and_restorable(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    hooks = _copy_install(world, {"hooks/h1.py": NEW_H1})
    _no_sleep(monkeypatch)

    def refused(src: str, dst: str) -> bool:
        return os.path.basename(src).startswith(".hooks.vexinstall-") or (dst == str(hooks) and "trash" in src)

    _refuse_renames(monkeypatch, refused)
    res = world.run("sync", "--target", "claude")
    assert res.code == 0 and any("the old entry is in trash at" in line for line in res.err), res.err
    assert not os.path.lexists(hooks)
    [record] = _trash_records(world, hooks)

    monkeypatch.setattr(os, "rename", REAL_RENAME)
    ts = Path(record["trashed"]).relative_to(world.home / ".claude" / "vexjoy" / "trash").parts[0]
    assert world.run("restore-trash", ts).code == 0
    assert (hooks / "h1.py").read_text() == OLD_H1


def test_a_refused_link_leaves_the_copy_in_place(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each link is staged before its copy moves. Before, a switch to symlink mode on a host that
    refuses links moved every copy to trash and left its dest missing."""
    hooks = _copy_install(world, {})
    _deny_symlinks(monkeypatch)
    res = world.run("apply", "--target", "claude", "--mode", "symlink")
    assert res.code == 1 and any("more not done" in line for line in res.err), res.err
    assert any(line.startswith(f"{hooks} not updated") for line in res.data["failed"]), res.data["failed"]
    assert hooks.is_dir() and not hooks.is_symlink() and (hooks / "h1.py").read_text() == OLD_H1
    assert (world.skills("claude") / "alpha" / "SKILL.md").is_file()
    assert _leftovers(hooks) == [] and _trash_records(world, hooks) == []
