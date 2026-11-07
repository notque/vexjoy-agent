"""Guarded filesystem writes: no write-through, atomic replace, trash moves."""

from __future__ import annotations

import contextlib
import errno
import json
import os
import secrets
import shutil
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import GuardError, is_inside, iter_tree_files, parse_ts, realpath, utc_iso

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

# Windows refuses to rename a dir while another process holds a file in it open or works
# inside it, and to replace a file another process has open: ERROR_ACCESS_DENIED or
# ERROR_SHARING_VIOLATION. Hooks and virus scanners let go within a second, so a rename
# retries for about 3 s. A terminal or editor working inside the dir does not let go; that
# entry then fails, and apply.execute_target leaves it as it was and goes on.
_WIN_BUSY = frozenset({5, 32})
_BUSY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6)


def is_busy(exc: BaseException) -> bool:
    """True for the Windows errors a rename gets while another process uses the path."""
    return getattr(exc, "winerror", None) in _WIN_BUSY


def retry_rename(src: Path | str, dest: Path | str, *, replace: bool = False) -> None:
    """``os.rename`` (``os.replace`` with *replace*), retried while Windows reports *src* or *dest* busy."""
    op = os.replace if replace else os.rename
    for delay in _BUSY_DELAYS:
        try:
            op(src, dest)
            return
        except OSError as exc:
            if not is_busy(exc):
                raise
        time.sleep(delay)
    op(src, dest)


@dataclass
class Guard:
    """Refuses any write whose parent resolves inside a protected root (spec 7.4)."""

    protected: list[str] = field(default_factory=list)
    trips: list[str] = field(default_factory=list)

    @classmethod
    def for_roots(cls, roots: list[Path]) -> Guard:
        """Build a guard from repo and overlay roots (realpath'd)."""
        seen: list[str] = []
        for r in roots:
            rp = realpath(r)
            if rp not in seen:
                seen.append(rp)
        return cls(protected=seen)

    def check(self, path: Path | str) -> None:
        """Raise GuardError when realpath(parent of *path*) is inside a protected root."""
        parent = realpath(os.path.dirname(os.path.abspath(str(path))))
        for root in self.protected:
            if is_inside(parent, root):
                self.trips.append(str(path))
                raise GuardError(path, root)


def symlink_in_chain(path: Path, stop: Path) -> Path | None:
    """First symlinked dir among the parents of *path* up to *stop* (inclusive).

    *path* itself is not checked; callers handle a leaf symlink explicitly.
    """
    current = path.parent
    stop_s = os.path.normpath(str(stop))
    while True:
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            st = None
        if st is not None and stat.S_ISLNK(st.st_mode):
            return current
        if os.path.normpath(str(current)) == stop_s or current.parent == current:
            return None
        if not is_inside(current, stop_s):
            return None
        current = current.parent


def _tmp_name(dest: Path) -> Path:
    return dest.parent / f".{dest.name}.vexinstall-{secrets.token_hex(6)}"


def mkdirs(path: Path, guard: Guard) -> None:
    """Create *path* and missing parents; refuse symlinked components."""
    missing: list[Path] = []
    cur = path
    while not os.path.lexists(cur):
        missing.append(cur)
        cur = cur.parent
    for p in reversed(missing):
        guard.check(p)
        os.mkdir(p)
    if os.path.islink(path) or not os.path.isdir(path):
        raise NotADirectoryError(f"not a real directory: {path}")


def atomic_write_bytes(dest: Path, data: bytes, guard: Guard, mode: int = 0o644) -> None:
    """Write *data* to *dest* via O_NOFOLLOW|O_EXCL temp file plus os.replace."""
    guard.check(dest)
    mkdirs(dest.parent, guard)
    tmp = _tmp_name(dest)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        retry_rename(tmp, dest, replace=True)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(dest: Path, obj: object, guard: Guard, mode: int = 0o644) -> None:
    """Pretty JSON through :func:`atomic_write_bytes`."""
    atomic_write_bytes(dest, (json.dumps(obj, indent=2, sort_keys=False) + "\n").encode(), guard, mode)


def atomic_symlink(dest: Path, target: Path, guard: Guard) -> None:
    """Point *dest* at *target* (absolute) atomically; replaces a leaf link, never follows it."""
    guard.check(dest)
    if os.path.lexists(dest) and not os.path.islink(dest):
        raise FileExistsError(errno.EEXIST, "refusing to replace non-link", str(dest))
    tmp = _tmp_name(dest)
    os.symlink(str(target), tmp)
    try:
        os.replace(tmp, dest)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _copy_file(src: Path, dst: Path) -> None:
    mode = stat.S_IMODE(os.stat(src).st_mode) | stat.S_IRUSR | stat.S_IWUSR
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
        shutil.copyfileobj(inp, out, 1 << 16)
    os.chmod(dst, mode)


def discard_staged(tmp: Path) -> None:
    """Remove a staged temp copy (file, link, or tree)."""
    if os.path.isdir(tmp) and not os.path.islink(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    elif os.path.lexists(tmp):
        os.unlink(tmp)


def stage_copy(src: Path, dest: Path, guard: Guard, files: tuple[str, ...] | None) -> Path:
    """Copy a file or tree into a temp sibling of *dest* and return it. *dest* is not touched."""
    guard.check(dest)
    tmp = _tmp_name(dest)
    try:
        if src.is_file():
            _copy_file(src, tmp)
        else:
            os.mkdir(tmp)
            rels = files if files is not None else tuple(iter_tree_files(src))
            for rel in rels:
                s = src / rel
                if not s.is_file():
                    continue
                d = tmp / rel
                d.parent.mkdir(parents=True, exist_ok=True)
                _copy_file(s, d)
    except BaseException:
        discard_staged(tmp)
        raise
    return tmp


def stage_link(target: Path, dest: Path, guard: Guard) -> Path:
    """Create a symlink to *target* in a temp sibling of *dest* and return it. *dest* is not touched."""
    guard.check(dest)
    tmp = _tmp_name(dest)
    os.symlink(str(target), tmp)
    return tmp


def place_staged(tmp: Path, dest: Path) -> None:
    """Rename the staged copy or link *tmp* onto the absent *dest*. Remove *tmp* when that fails."""
    try:
        if os.path.lexists(dest):
            raise FileExistsError(errno.EEXIST, "dest exists", str(dest))
        retry_rename(tmp, dest)
    except BaseException:
        discard_staged(tmp)
        raise


def copy_entry(src: Path, dest: Path, guard: Guard, files: tuple[str, ...] | None) -> None:
    """Copy a file or tree to an absent *dest* via a temp sibling and rename."""
    guard.check(dest)
    if os.path.lexists(dest):
        raise FileExistsError(errno.EEXIST, "dest exists", str(dest))
    place_staged(stage_copy(src, dest, guard, files), dest)


@dataclass
class Trash:
    """Session trash dir: ``<state>/trash/<ts>/``; records a manifest."""

    root: Path
    ts: str
    guard: Guard
    items: list[dict[str, str]] = field(default_factory=list)

    @property
    def dir(self) -> Path:
        """This session's trash directory."""
        return self.root / self.ts

    def move(self, path: Path, home: Path, reason: str) -> Path:
        """Move *path* (link, file, or dir; never followed) into trash.

        The manifest names the move before the rename. A run killed in between leaves a
        record that restore-trash skips, never an entry in trash that nothing points to.
        """
        self.guard.check(path)
        try:
            rel = path.relative_to(home)
        except ValueError:
            rel = Path(str(path).lstrip("/"))
        dest = self.dir / "files" / rel
        mkdirs(dest.parent, self.guard)
        if os.path.lexists(dest):
            dest = dest.with_name(dest.name + "." + secrets.token_hex(3))
        item = {"original": str(path), "trashed": str(dest), "reason": reason, "at": utc_iso()}
        self._save([*self.items, item])
        try:
            retry_rename(path, dest)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                with contextlib.suppress(OSError):
                    self._save(self.items)
                raise
            shutil.move(str(path), str(dest))
        self.items.append(item)
        return dest

    def put_back(self, trashed: Path, original: Path) -> None:
        """Undo :meth:`move` for an entry whose replacement could not be placed.

        When the entry cannot come back, the OSError says where it is in trash.
        """
        self.guard.check(original)
        try:
            retry_rename(trashed, original)
        except OSError as exc:
            raise OSError(exc.errno, f"missing; the old entry is in trash at {trashed} ({exc})") from exc
        self.items = [i for i in self.items if i["trashed"] != str(trashed)]
        with contextlib.suppress(OSError):  # restore-trash skips a record whose trashed path is gone
            self._save(self.items)

    def _save(self, items: list[dict[str, str]]) -> None:
        atomic_write_json(self.dir / "manifest.json", {"ts": self.ts, "items": items}, self.guard)


def _is_empty_real_dir(path: Path) -> bool:
    return os.path.isdir(path) and not os.path.islink(path) and not os.listdir(path)


def restore_trash(
    trash_root: Path,
    ts: str,
    guard: Guard,
    clear_occupant: Callable[[Path], bool] | None = None,
) -> tuple[list[str], list[str]]:
    """Move every item of trash session *ts* back. Returns (restored, skipped).

    An empty real dir at the original path is removed first. Any other occupant
    is left alone unless *clear_occupant* moves it away and returns True.
    """
    manifest = trash_root / ts / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    restored: list[str] = []
    skipped: list[str] = []
    for item in reversed(data.get("items", [])):
        orig = Path(item["original"])
        src = Path(item["trashed"])
        if not os.path.lexists(src):
            skipped.append(str(orig))
            continue
        if os.path.lexists(orig) and clear_occupant is not None:
            clear_occupant(orig)
        if _is_empty_real_dir(orig):
            guard.check(orig)
            os.rmdir(orig)
        if os.path.lexists(orig):
            skipped.append(str(orig))
            continue
        guard.check(orig)
        mkdirs(orig.parent, guard)
        retry_rename(src, orig)
        restored.append(str(orig))
    return restored, skipped


def prune_trash(trash_root: Path, max_age_days: int) -> list[str]:
    """Delete trash sessions older than *max_age_days* (the only real deletion)."""
    removed: list[str] = []
    if not trash_root.is_dir():
        return removed
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    for child in trash_root.iterdir():
        when = parse_ts(child.name)
        if when is not None and when < cutoff and child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child.name)
    return removed
