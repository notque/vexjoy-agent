"""Shared constants, errors, hashing, and path helpers for the vexinstall engine."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path

SCHEMA_VERSION = 1

# Root-level dirs under repo `skills/` that hold reference material, not skills.
# They have no SKILL.md and install next to skills so relative links such as
# `../shared-patterns/x.md` and `~/.claude/skills/voice-shared/...` resolve.
#   shared-patterns: referenced by 64 skill/agent/hook files.
#   kb: carries skills/kb/scripts/kb-compile-cron.sh (tracked).
#   voice-shared: tracked (.gitignore negation), read by voice skills in the
#     private overlay and by scripts/scan-ai-patterns.py via the skills root.
SUPPORT_DIRS = frozenset({"shared-patterns", "kb", "voice-shared"})

# Runtime data dirs that other tools write under a skills root. The engine
# never installs, adopts, or removes them; doctor names them as non-skill dirs.
DATA_DIRS = frozenset({"reddit-data", "synced"})

# Names never copied, hashed, or treated as install entries.
IGNORE_NAMES = frozenset(
    {"__pycache__", "node_modules", ".git", ".DS_Store", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
)
IGNORE_SUFFIXES = (".pyc", ".pyo")

TRASH_RETENTION_DAYS = 14
REPORTS_KEEP = 50
SETTINGS_BACKUPS_KEEP = 10
MASS_REMOVE_MAX = 10
MASS_REMOVE_FRACTION = 0.20
APPLY_LOCK_TIMEOUT_S = 30.0

TARGET_NAMES = ("claude", "codex", "factory", "hermes", "reasonix")
MODES = ("symlink", "copy")

# Colon-separated realpath prefixes treated as ephemeral (symlink mode refused).
EPHEMERAL_ENV = "VEXINSTALL_EPHEMERAL_PREFIXES"
DEFAULT_EPHEMERAL = "/tmp"


class ExitCode(IntEnum):
    """Process exit codes."""

    OK = 0
    ERROR = 1
    USAGE = 2
    COLLISION = 3
    GUARD = 4
    MASS_REMOVE = 5
    SOURCE_REFUSED = 6
    LOCK_TIMEOUT = 7


class VexinstallError(Exception):
    """Base error carrying an exit code."""

    exit_code: ExitCode = ExitCode.ERROR


class GuardError(VexinstallError):
    """A write would land inside the source repo or an overlay root."""

    exit_code = ExitCode.GUARD

    def __init__(self, path: Path | str, root: Path | str) -> None:
        super().__init__(f"guard: refusing write to {path} (resolves inside {root})")
        self.path = str(path)
        self.root = str(root)


class OverlayConfigError(VexinstallError):
    """overlays.json is invalid."""

    exit_code = ExitCode.USAGE


class CollisionError(VexinstallError):
    """Two sources claim one dest name."""

    exit_code = ExitCode.COLLISION


class MassRemovalError(VexinstallError):
    """Plan removes more than the cap allows."""

    exit_code = ExitCode.MASS_REMOVE


class SourceRefusedError(VexinstallError):
    """Symlink-mode run from a worktree, ephemeral path, or unadopted source."""

    exit_code = ExitCode.SOURCE_REFUSED


class LockTimeoutError(VexinstallError):
    """The engine lock could not be acquired."""

    exit_code = ExitCode.LOCK_TIMEOUT


def utc_ts() -> str:
    """Return a sortable, filesystem-safe UTC timestamp with microseconds."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def utc_iso() -> str:
    """Return an ISO-8601 UTC timestamp (seconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(ts: str) -> datetime | None:
    """Parse a timestamp produced by :func:`utc_ts`."""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_ignored_name(name: str) -> bool:
    """True for cache/vendor names the engine never copies or hashes."""
    return name in IGNORE_NAMES or name.endswith(IGNORE_SUFFIXES)


def is_inside(path: str | Path, root: str | Path) -> bool:
    """True when normalized *path* equals *root* or sits below it (string check)."""
    p = os.path.normpath(str(path))
    r = os.path.normpath(str(root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def realpath(path: str | Path) -> str:
    """Non-strict realpath as a string."""
    return os.path.realpath(str(path))


def is_dangling(path: str | Path) -> bool:
    """Strict dangling check: the link exists (lstat) but its target does not."""
    return os.path.lexists(path) and not os.path.exists(path)


def iter_tree_files(root: Path) -> Iterator[str]:
    """Yield POSIX relative paths of regular files under *root*.

    Does not descend into symlinked dirs; symlinked files are included when
    they resolve to a regular file. Ignored names are skipped.
    """
    root_s = str(root)
    for dirpath, dirnames, filenames in os.walk(root_s, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not is_ignored_name(d))
        for name in sorted(filenames):
            if is_ignored_name(name):
                continue
            full = os.path.join(dirpath, name)
            if os.path.isfile(full):
                yield os.path.relpath(full, root_s).replace(os.sep, "/")


def file_sha256(path: str | Path) -> str:
    """SHA-256 of a file's content (follows symlinks)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha256(path: str | Path, files: Iterable[str] | None = None) -> str | None:
    """Content hash of a file or directory tree; None when *path* is missing.

    Directory hashes cover sorted (relpath, file hash) pairs, so a copy and its
    source hash equal when they hold the same files with the same bytes.
    """
    p = Path(path)
    if p.is_file():
        return "f:" + file_sha256(p)
    if not p.is_dir():
        return None
    rels = sorted(files if files is not None else iter_tree_files(p))
    h = hashlib.sha256()
    for rel in rels:
        full = p / rel
        if not full.is_file():
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(file_sha256(full).encode())
        h.update(b"\n")
    return "d:" + h.hexdigest()


def expand_home(value: str, home: Path) -> Path:
    """Expand a leading ``~``, ``$HOME``, or ``${HOME}`` against *home*."""
    for prefix in ("${HOME}", "$HOME", "~"):
        if value == prefix:
            return home
        if value.startswith(prefix + "/"):
            return home / value[len(prefix) + 1 :]
    return Path(value)
