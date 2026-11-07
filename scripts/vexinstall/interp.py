"""The python that runs toolkit hooks: resolve it, link it, check it.

Hooks need python 3.10+. A bare ``python3`` resolves through the runtime's
PATH, which can be a pyenv shim that picks 3.9 in some repos, or
``/usr/bin/python3`` 3.9 on macOS. Every repo hook command therefore runs
through the launcher script ``hooks/lib/pyrun.sh``::

    sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/x.py"

The engine points ``~/.claude/vexjoy/bin/python3`` at one verified 3.10+
interpreter, and ``pyrun.sh`` runs it first. A host that refuses symlinks
(Windows without Developer Mode) gets a script pin there instead: an sh script
that names the interpreter and execs it (:func:`pin_script_bytes`). The command string carries no
machine path, so the repo ``.claude/settings.json`` and every installed copy
hold the same string and Claude Code dedupes them (differing strings run the
hook twice in repo sessions). Its first path is inside ``hooks/``, so every
engine version, older ones included, owns the entry. Claude Code runs hook
commands with ``/bin/sh -c``. A missing or dangling pin falls back to
python3.1x on PATH, then ``python3``; the guard at the top of every hook
(``scripts/hook-pyguard.py``) re-execs or blocks under anything older.

Resolution order: ``$VEXJOY_PYTHON``, well-known system paths, ``python3`` and
``python3.N`` on PATH, then the interpreter running the engine. Each candidate
is run to read its version and whether it is a venv. Version-manager shims
(``/shims/``) and venvs are never linked. Versioned install dirs (Homebrew Cellar, pyenv, asdf, mise, uv, rye)
are used only when nothing stable qualifies, because an upgrade or uninstall
removes them.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .fsops import Guard, atomic_symlink, atomic_write_bytes, mkdirs

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
# Script pin (hosts that refuse symlinks): line 2 marks the file as ours, line 3 names the interpreter for
# read_pin and pyrun.sh, line 4 execs it. Only the first _PIN_SCRIPT_HEAD lines are ever read.
PIN_SCRIPT_MARK = "# vexjoy-python-shim"
PIN_SCRIPT_TARGET = "# vexjoy-python-target: "
_PIN_SCRIPT_HEAD = 3
_PIN_SCRIPT_READ = 4096
_WIN_NO_SYMLINK = 1314  # ERROR_PRIVILEGE_NOT_HELD: no Developer Mode and no create-symlink privilege
_WIN_NOT_SUPPORTED = 50  # ERROR_NOT_SUPPORTED: the volume has no symlinks (FAT, some network shares)
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


# The one hook entry that is not a toolkit hook: the repo-only SessionStart bootstrap. It runs
# scripts/session-bootstrap.sh from the checkout so a home with no launcher (a cloud session
# container, a new user, an install older than pyrun.sh) installs itself. Installs and mirrors
# (user settings, account homes, Factory) never copy it; ``drop_repo_only`` strips it.
REPO_BOOTSTRAP = 'sh "$CLAUDE_PROJECT_DIR/scripts/session-bootstrap.sh"'


def is_repo_only(command: object) -> bool:
    """True for the repo-only bootstrap entry's command."""
    return command == REPO_BOOTSTRAP


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


@dataclass(frozen=True)
class Pin:
    """What sits at the pin path, read once.

    ``kind`` is ``missing``, ``link`` (a symlink), ``script`` (a script pin, see
    :func:`pin_script_bytes`), or ``foreign`` (anything else; the engine never touches it).
    ``target`` is the symlink's target or the interpreter a script pin names, else None.
    """

    kind: Literal["missing", "link", "script", "foreign"]
    target: str | None = None


def read_pin(link: Path) -> Pin:
    """Classify *link*: a script pin is a regular file whose first lines carry :data:`PIN_SCRIPT_MARK`."""
    if os.path.islink(link):
        return Pin("link", os.readlink(link))
    if not os.path.lexists(link):
        return Pin("missing")
    if not os.path.isfile(link):
        return Pin("foreign")
    try:
        with open(link, encoding="utf-8", errors="replace", newline="") as fh:
            head = fh.read(_PIN_SCRIPT_READ).split("\n")[:_PIN_SCRIPT_HEAD]
    except OSError:
        return Pin("foreign")
    if PIN_SCRIPT_MARK not in (line.rstrip("\r") for line in head):
        return Pin("foreign")
    named = [line[len(PIN_SCRIPT_TARGET) :] for line in head if line.startswith(PIN_SCRIPT_TARGET)]
    # pyrun.sh reads the line as sh does, carriage return included, so a CRLF target is unusable to both.
    return Pin("script", named[0] if named and named[0] and "\r" not in named[0] else None)


def _posix(path: str) -> str:
    """Forward slashes, the way Git Bash's sh and the script pin spell a Windows path."""
    return path.replace("\\", "/")


def _same_path(a: str, b: str) -> bool:
    """True for two spellings of one path (Windows readlink returns backslashes for a forward-slash target)."""
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def pin_script_bytes(interpreter_path: str) -> bytes:
    """The script pin for *interpreter_path*: name it, then exec it with every argument.

    Hooks run the pin from sh (``pyrun.sh``), so it is an sh script: sh cannot exec a ``.cmd``
    or ``.bat``, and Git for Windows supplies the sh. ``pyrun.sh`` reads the target line and
    skips the pin once that interpreter is gone, the way a dangling symlink fails its ``-x``
    test, so hooks still fall back to a python on PATH and the sync hook can repair the pin.
    """
    target = _posix(interpreter_path)
    return f'#!/bin/sh\n{PIN_SCRIPT_MARK}\n{PIN_SCRIPT_TARGET}{target}\nexec {shlex.quote(target)} "$@"\n'.encode()


def _symlink_unsupported(exc: BaseException) -> bool:
    """True when a symlink failure means this host cannot create links at all."""
    if isinstance(exc, NotImplementedError):
        return True
    return isinstance(exc, OSError) and getattr(exc, "winerror", None) in (_WIN_NO_SYMLINK, _WIN_NOT_SUPPORTED)


def _probe_path(link: Path, pin: Pin) -> str | None:
    """What to run to reach the pinned interpreter: the symlink, a script pin's absolute target, else None.

    A script pin is probed through its interpreter because Windows cannot run an sh script directly.
    """
    if pin.kind == "link":
        return str(link)
    if pin.kind == "script" and pin.target and os.path.isabs(pin.target):
        return pin.target
    return None


def link_ok(home: Path) -> bool:
    """True when the pin reaches a python 3.10+ that runs (one probe, about 25 ms)."""
    link = link_path(home)
    path = _probe_path(link, read_pin(link))
    if path is None or not os.path.exists(path):
        return False
    version = probe(path)
    return version is not None and version >= MIN_VERSION


def link_blocker(home: Path) -> str | None:
    """Why the pin cannot be written (a foreign file at its path or its dir); None when it can."""
    link = link_path(home)
    if os.path.lexists(link.parent) and (os.path.islink(link.parent) or not os.path.isdir(link.parent)):
        return f"{link.parent} is not a real directory; move it away and rerun ./install.sh"
    if read_pin(link).kind == "foreign":
        return (
            f"{link} is a regular file, not a symlink or a vexjoy script pin (no {PIN_SCRIPT_MARK!r} line); "
            "move it away and rerun ./install.sh"
        )
    return None


def write_link(home: Path, interpreter: Interpreter, guard: Guard) -> bool:
    """Point the pin at *interpreter*; True when it changed.

    Writes a symlink. A host that cannot create one (Windows error 1314 without Developer Mode or
    the create-symlink privilege, error 50 on a volume without symlinks, NotImplementedError) gets
    a script pin instead. A script pin stays a script pin and is rewritten in place when its
    interpreter or format changes; delete it and rerun ``./install.sh`` to get a symlink once the
    host allows one.
    """
    link = link_path(home)
    pin = read_pin(link)
    if pin.kind == "link" and pin.target and _same_path(pin.target, interpreter.path):
        return False
    body = pin_script_bytes(interpreter.path)
    mkdirs(link.parent, guard)
    if pin.kind == "script":  # atomic_symlink refuses to replace a regular file
        try:
            with open(link, "rb") as fh:
                current = fh.read(len(body) + 1)
        except OSError:
            current = b""
        if current == body and os.access(link, os.X_OK):
            return False
        atomic_write_bytes(link, body, guard, 0o755)
        return True
    try:
        atomic_symlink(link, Path(interpreter.path), guard)
    except (OSError, NotImplementedError) as exc:
        if not _symlink_unsupported(exc):
            raise
        atomic_write_bytes(link, body, guard, 0o755)
    return True


def drift(home: Path) -> list[tuple[str, str]]:
    """(check, detail) for each problem with the pin; empty when it reaches a verified 3.10+ python."""
    link = link_path(home)
    fix = "rerun ./install.sh"
    pin = read_pin(link)
    if pin.kind == "missing":
        return [("python-pin-missing", f"hooks fall back to bare python3; {fix}")]
    if pin.kind == "foreign":
        return [("python-pin-not-link", f"expected a symlink or a vexjoy script pin to python 3.10+; {fix}")]
    target = pin.target or ""
    if pin.kind == "script" and not os.path.isabs(target):
        what = f"names a relative interpreter {target!r}" if target else "has no readable target line"
        return [("python-pin-broken", f"script pin {link} {what}; {fix}")]
    path = str(link) if pin.kind == "link" else target
    if not os.path.exists(path):
        return [("python-pin-dangling", f"{target} is gone; hooks fall back to bare python3; {fix}")]
    version = probe(path)
    if version is None:
        return [("python-pin-broken", f"{target} does not run; {fix}")]
    if version < MIN_VERSION:
        return [("python-pin-old", f"{target} is {version[0]}.{version[1]}, need 3.10+; {fix}")]
    return []


# Top-level import name per requirements.txt entry; find_spec on a dotted name imports its parent.
REQUIRED_MODULES = ("yaml", "requests", "dotenv", "google.auth", "jsonschema", "PIL")
# Runs without -I, as pyrun.sh runs hooks, so the user site (install.sh's pip --user fallback) counts.
# The first line drops the current dir that -c puts on sys.path, before anything else is imported.
_MISSING_PROBE = (
    "import sys\n"
    "sys.path[:] = [p for p in sys.path if p not in ('', '.')]\n"
    "import importlib.util as u\n"
    "def has(n):\n"
    "    try: return u.find_spec(n) is not None\n"
    "    except ImportError: return False\n"
    "print(' '.join(n for n in sys.argv[1:] if not has(n)))"
)


def missing_modules(home: Path, modules: Iterable[str] = REQUIRED_MODULES, timeout: float = 10.0) -> list[str]:
    """Modules the pinned interpreter cannot import (find_spec only, nothing is imported); [] when unknown.

    Probed the way hooks run the pin: no ``-I``, so the user site and ``PYTHONPATH`` count, but never
    the current dir. A script pin is probed through its interpreter: Windows cannot run an sh script directly.
    """
    link = link_path(home)
    path = _probe_path(link, read_pin(link))
    if path is None:
        return []
    try:
        out = subprocess.run(
            [path, "-c", _MISSING_PROBE, *modules],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return out.stdout.split() if out.returncode == 0 else []
