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

from .common import (
    GuardError,
    file_sha256,
    is_ignored_name,
    is_inside,
    iter_tree_files,
    parse_ts,
    realpath,
    utc_iso,
)

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


def _json_bytes(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=False) + "\n").encode()


def atomic_write_json(dest: Path, obj: object, guard: Guard, mode: int = 0o644) -> None:
    """Pretty JSON through :func:`atomic_write_bytes`."""
    atomic_write_bytes(dest, _json_bytes(obj), guard, mode)


def _read_regular(path: Path) -> tuple[bytes, int] | None:
    """(bytes, permission bits) of the regular file at *path*; None for a link, a missing or unreadable file."""
    if os.path.islink(path):
        return None
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode):
            return None
        return fh.read(), stat.S_IMODE(st.st_mode)


def write_json_if_changed(
    dest: Path, obj: dict, guard: Guard, mode: int = 0o644, *, stamps: tuple[str, ...] = ()
) -> bool:
    """:func:`atomic_write_json` unless *dest* already holds these bytes and *mode*; True when it wrote.

    *stamps* name run timestamps (an index's ``generated``, the ledger's ``updated_at``). The value
    already in *dest* stands in for them in the comparison, so a run that would move only a stamp
    leaves the file and its old stamp alone. An unchanged file gets a fresh mtime instead, as a
    rewrite gave it, because readers take the mtime as the freshness signal.
    """
    current = _read_regular(dest)
    if current is not None and current[1] == mode:
        want = obj
        if stamps:
            try:
                prev = json.loads(current[0])
            except ValueError:
                prev = None
            if isinstance(prev, dict):
                want = {**obj, **{k: prev[k] for k in stamps if k in obj and k in prev}}
        if _json_bytes(want) == current[0]:
            guard.check(dest)
            try:
                os.utime(dest)
                return False
            except OSError:
                pass  # a file we may replace but not touch (another owner): rewrite it as before
    atomic_write_json(dest, obj, guard, mode)
    return True


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
    """Remove a staged temp copy (file, link, or tree). Never raises: a leftover is only clutter."""
    if os.path.isdir(tmp) and not os.path.islink(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        with contextlib.suppress(OSError):
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


NODE_MODULES = "node_modules"


@dataclass
class CarryLog:
    """node_modules dirs moved from a copy in trash into the live copy, and warning lines for the rest."""

    carried: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _real(path: str | Path) -> str:
    return os.path.normcase(realpath(path))


def _inside(path: str | Path, top: Path) -> bool:
    """True when *path* lies physically inside *top* and *top* is no link or junction itself.

    A link or junction can lead into the repo or another checkout, whose node_modules
    must stay put and must never receive one.
    """
    top_real = _real(top)
    if top_real != os.path.join(_real(top.parent), os.path.normcase(top.name)):
        return False
    return is_inside(_real(path), top_real)


def _package_dirs(copy: Path) -> list[Path]:
    """Dirs physically inside *copy*, itself included, that hold a node_modules dir.

    Ignored names, node_modules included, are not entered.
    """
    found: list[Path] = []
    for dirpath, dirnames, _files in os.walk(copy, followlinks=False):
        if NODE_MODULES in dirnames and _inside(dirpath, copy):
            found.append(Path(dirpath))
        dirnames[:] = [d for d in dirnames if not is_ignored_name(d)]
    return found


def _lock_digest(package: Path) -> str | None:
    """sha256 of the package's package-lock.json; None when it is missing or unreadable."""
    try:
        return file_sha256(package / "package-lock.json")
    except OSError:
        return None


def carry_node_modules(old: Path, new: Path, guard: Guard, log: CarryLog) -> None:
    """Move each node_modules dir of the copy *old*, now in trash, into the same dir of the live copy *new*.

    The engine never copies or hashes node_modules (``IGNORE_NAMES``), so without this a
    replace leaves what ``npm ci`` installed in trash with the old copy, and the Jev gateway
    fails until ``./install.sh`` runs again. A restore calls it the other way round.

    A dir moves only when *new* ships the same ``package.json`` dir with a byte-identical
    ``package-lock.json`` and no node_modules yet, so a node_modules always matches the lock
    beside it, as ``npm ci`` leaves it. A changed lock leaves the dir with *old* and logs a
    warning to run ``./install.sh``; a package that left the repo leaves it there silently.

    Never raises OSError: *new* is already in place, so a dir that cannot move only logs a
    warning that says where it is.
    """
    for package in _package_dirs(old):
        into = new / package.relative_to(old)
        src, dst = package / NODE_MODULES, into / NODE_MODULES
        if not _inside(into, new) or not os.path.isfile(into / "package.json") or os.path.lexists(dst):
            continue
        if _lock_digest(package) != _lock_digest(into):
            log.warnings.append(f"{dst} not carried over: package-lock.json changed; run ./install.sh (old one: {src})")
            continue
        try:
            guard.check(dst)
            retry_rename(src, dst)
        except OSError as exc:
            log.warnings.append(f"{dst} not carried over ({exc}); run ./install.sh (old one: {src})")
            continue
        log.carried.append(str(dst))


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
                    self._forget()
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
            self._forget()

    def _save(self, items: list[dict[str, str]]) -> None:
        atomic_write_json(self.dir / "manifest.json", {"ts": self.ts, "items": items}, self.guard)

    def _forget(self) -> None:
        """Rewrite the manifest after a move failed or was undone.

        A session left with no items is removed, so no empty session lingers in trash for
        ``restore-trash`` to list, and the rollback point of the run names none.
        """
        if self.items:
            self._save(self.items)
        else:
            shutil.rmtree(self.dir, ignore_errors=True)


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
