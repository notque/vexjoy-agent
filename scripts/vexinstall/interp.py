"""The python that runs toolkit hooks: resolve it, link it, check it.

Hooks need python 3.10+. A bare ``python3`` resolves through the runtime's
PATH, which can be a pyenv shim that picks 3.9 in some repos, or
``/usr/bin/python3`` 3.9 on macOS. Every repo hook command therefore runs
through the launcher script ``hooks/lib/pyrun.sh``::

    sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/x.py"

The engine points ``~/.claude/vexjoy/bin/python3`` at one verified 3.10+
interpreter, and ``pyrun.sh`` runs it first. The command string carries no
machine path, so the repo ``.claude/settings.json`` and every installed copy
hold the same string and Claude Code dedupes them (differing strings run the
hook twice in repo sessions). Its first path is inside ``hooks/``, so every
engine version, older ones included, owns the entry. Claude Code runs hook
commands with ``/bin/sh -c``. A missing or dangling link falls back to
python3.1x on PATH, then ``python3``; the guard at the top of every hook
(``scripts/hook-pyguard.py``) re-execs or blocks under anything older.

Resolution order: ``$VEXJOY_PYTHON``, well-known system paths, ``python3`` and
``python3.N`` on PATH, then the interpreter running the engine. Each candidate
is run to read its version and whether it is a venv. Shims and venvs are never
linked. Versioned install dirs (Homebrew Cellar, pyenv, asdf, mise, uv, rye)
are used only when nothing stable qualifies, because an upgrade or uninstall
removes them.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .fsops import Guard, atomic_symlink, mkdirs

MIN_VERSION = (3, 10)
OVERRIDE_ENV = "VEXJOY_PYTHON"
LINK_SH = "$HOME/.claude/vexjoy/bin/python3"
LAUNCHER = 'sh "$HOME/.claude/hooks/lib/pyrun.sh" '
WELL_KNOWN = ("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3")
_SHIM_PARTS = ("/shims/",)
# Checked on the literal path only: /opt/homebrew/bin/python3 resolves into Cellar but survives upgrades.
_LITERAL_UNSTABLE_PARTS = ("/Cellar/",)
# Checked on the literal path and its realpath (a python3.12 link into the uv store is still the uv store).
_UNSTABLE_PARTS = ("/.pyenv/versions/", "/.asdf/installs/", "/mise/installs/", "/uv/python/", "/.rye/")
_VERSIONED_NAME = re.compile(r"^python3\.(\d+)$")
_PROBE = "import sys; print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], sys.prefix != sys.base_prefix))"


class InterpreterError(Exception):
    """No usable python 3.10+ was found."""


@dataclass(frozen=True)
class Interpreter:
    """A verified interpreter."""

    path: str
    version: tuple[int, int]

    @property
    def label(self) -> str:
        """``/path (3.14)``."""
        return f"{self.path} ({self.version[0]}.{self.version[1]})"


def link_path(home: Path) -> Path:
    """``~/.claude/vexjoy/bin/python3``."""
    return home / ".claude" / "vexjoy" / "bin" / "python3"


def hook_command(filename: str) -> str:
    """The canonical command for a hook file in ``~/.claude/hooks``."""
    return f'{LAUNCHER}"$HOME/.claude/hooks/{filename}"'


def strip_launcher(command: str) -> str:
    """``python3 <args>`` for a launcher command; any other command unchanged."""
    if command.startswith(LAUNCHER):
        return "python3 " + command[len(LAUNCHER) :]
    return command


def probe_info(path: str, timeout: float = 5.0) -> tuple[tuple[int, int], bool] | None:
    """((major, minor), is_venv) of the interpreter at *path*, or None when it does not run."""
    try:
        out = subprocess.run([path, "-I", "-c", _PROBE], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        ver, venv = out.stdout.split()
        major, minor = ver.split(".")
        return (int(major), int(minor)), venv == "1"
    except ValueError:
        return None


def probe(path: str, timeout: float = 5.0) -> tuple[int, int] | None:
    """(major, minor) of the interpreter at *path*, or None when it does not run."""
    info = probe_info(path, timeout)
    return info[0] if info else None


def is_shim(path: str) -> bool:
    """True for a version-manager shim (resolves per directory, so never linked)."""
    return any(p in path or p in os.path.realpath(path) for p in _SHIM_PARTS)


def is_unstable(path: str) -> bool:
    """True for a path inside a versioned install dir that an upgrade or uninstall removes."""
    real = os.path.realpath(path)
    return any(p in path for p in _LITERAL_UNSTABLE_PARTS) or any(p in path or p in real for p in _UNSTABLE_PARTS)


def _usable(path: str) -> bool:
    return os.path.isabs(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def path_candidates(path_env: str) -> list[str]:
    """``python3`` then ``python3.N`` (newest first) in each absolute PATH dir, in PATH order."""
    out: list[str] = []
    for d in path_env.split(os.pathsep):
        if not d or not os.path.isabs(d) or not os.path.isdir(d):
            continue
        out.append(os.path.join(d, "python3"))
        try:
            names = os.listdir(d)
        except OSError:
            continue
        versioned = [(int(m.group(1)), n) for n in names if (m := _VERSIONED_NAME.match(n))]
        out.extend(os.path.join(d, n) for _, n in sorted(versioned, reverse=True))
    return out


def _ordered(path_env: str, well_known: Iterable[str], extra: Iterable[str]) -> Iterator[str]:
    seen: set[str] = set()
    for group in (well_known, path_candidates(path_env), extra):
        for p in group:
            if p and p not in seen:
                seen.add(p)
                yield p


def resolve(
    *,
    env: dict[str, str] | None = None,
    well_known: Iterable[str] = WELL_KNOWN,
    extra: Iterable[str] = (sys.executable,),
) -> Interpreter:
    """The interpreter to link. Raises InterpreterError when none qualifies."""
    env = dict(os.environ) if env is None else env
    override = env.get(OVERRIDE_ENV, "").strip()
    if override:
        info = probe_info(override) if os.path.isabs(override) else None
        if info is None or info[0] < MIN_VERSION or info[1]:
            got = "does not run" if info is None else "is a venv" if info[1] else "is %d.%d" % info[0]
            raise InterpreterError(
                f"{OVERRIDE_ENV}={override} {got}; it must be an absolute path to a non-venv python 3.10+"
            )
        return Interpreter(override, info[0])
    later: list[str] = []
    checked: list[str] = []

    def try_path(path: str) -> Interpreter | None:
        info = probe_info(path)
        label = "?" if info is None else "venv" if info[1] else "%d.%d" % info[0]
        checked.append(f"{path}={label}")
        if info is None or info[1] or info[0] < MIN_VERSION:
            return None
        return Interpreter(path, info[0])

    for path in _ordered(env.get("PATH", ""), well_known, extra):
        if not _usable(path) or is_shim(path):
            continue
        if is_unstable(path):
            later.append(path)
            continue
        found = try_path(path)
        if found:
            return found
    for path in later:
        found = try_path(path)
        if found:
            return found
    tried = ", ".join(checked) or "no python3 found"
    raise InterpreterError(
        f"no python 3.10+ found to run hooks (checked: {tried}). Install python 3.10+, or export "
        f"{OVERRIDE_ENV}=/absolute/path/to/python3, then rerun ./install.sh"
    )


def link_ok(home: Path) -> bool:
    """True when the link is a symlink to a python 3.10+ that runs (one probe, about 25 ms)."""
    link = link_path(home)
    if not (os.path.islink(link) and os.path.exists(link)):
        return False
    version = probe(str(link))
    return version is not None and version >= MIN_VERSION


def link_blocker(home: Path) -> str | None:
    """Why the link cannot be written (a non-link at its path or its dir); None when it can."""
    link = link_path(home)
    if os.path.lexists(link.parent) and (os.path.islink(link.parent) or not os.path.isdir(link.parent)):
        return f"{link.parent} is not a real directory; move it away and rerun ./install.sh"
    if os.path.lexists(link) and not os.path.islink(link):
        return f"{link} is a regular file, not a symlink; move it away and rerun ./install.sh"
    return None


def write_link(home: Path, interpreter: Interpreter, guard: Guard) -> bool:
    """Point the link at *interpreter*; True when it changed."""
    link = link_path(home)
    if os.path.islink(link) and os.readlink(link) == interpreter.path:
        return False
    mkdirs(link.parent, guard)
    atomic_symlink(link, Path(interpreter.path), guard)
    return True


def drift(home: Path) -> list[tuple[str, str]]:
    """(check, detail) for each problem with the link; empty when it is a verified 3.10+ python."""
    link = link_path(home)
    fix = "rerun ./install.sh"
    if not os.path.lexists(link):
        return [("python-pin-missing", f"hooks fall back to bare python3; {fix}")]
    if not os.path.islink(link):
        return [("python-pin-not-link", f"expected a symlink to python 3.10+; {fix}")]
    target = os.readlink(link)
    if not os.path.exists(link):
        return [("python-pin-dangling", f"{target} is gone; hooks fall back to bare python3; {fix}")]
    version = probe(str(link))
    if version is None:
        return [("python-pin-broken", f"{target} does not run; {fix}")]
    if version < MIN_VERSION:
        return [("python-pin-old", f"{target} is {version[0]}.{version[1]}, need 3.10+; {fix}")]
    return []
