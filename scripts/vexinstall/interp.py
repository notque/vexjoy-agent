"""The python that runs toolkit hooks: resolve it, link it, check it.

Hooks need python 3.10+. A bare ``python3`` resolves through the runtime's
PATH, which can be a pyenv shim that picks 3.9 in some repos, or
``/usr/bin/python3`` 3.9 on macOS. Every repo hook command therefore starts
with the launcher prefix::

    p="$HOME/.claude/vexjoy/bin/python3"; [ -x "$p" ] || p=python3; exec "$p" "$HOME/.claude/hooks/x.py"

The engine points ``~/.claude/vexjoy/bin/python3`` at one verified 3.10+
interpreter. The command string carries no machine path, so the repo
``.claude/settings.json`` and every installed copy hold the same string and
Claude Code dedupes them (differing strings run the hook twice in repo
sessions). Claude Code runs hook commands with ``/bin/sh -c``. A missing or
dangling link falls back to ``python3``; the guard at the top of every hook
(``scripts/hook-pyguard.py``) handles a fallback older than 3.10.

Resolution order: ``$VEXJOY_PYTHON``, well-known system paths, ``python3`` and
``python3.N`` on PATH, then the interpreter running the engine. Each candidate
is run to read its version. Shims are never linked. Versioned install dirs
(Homebrew Cellar, pyenv, asdf, mise, uv) are used only when nothing stable
qualifies, because an upgrade or uninstall removes them.
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
LAUNCHER = f'p="{LINK_SH}"; [ -x "$p" ] || p=python3; exec "$p" '
WELL_KNOWN = ("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3")
_SHIM_PARTS = ("/shims/",)
_UNSTABLE_PARTS = ("/Cellar/", "/.pyenv/versions/", "/.asdf/installs/", "/mise/installs/", "/uv/python/", "/.rye/")
_VERSIONED_NAME = re.compile(r"^python3\.(\d+)$")
_PROBE = "import sys; print('%d.%d' % sys.version_info[:2])"


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


def strip_launchers(obj: object) -> object:
    """Copy of hooks JSON with every launcher ``command`` turned back into bare ``python3``."""
    if isinstance(obj, dict):
        return {
            k: strip_launcher(v) if k == "command" and isinstance(v, str) else strip_launchers(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [strip_launchers(v) for v in obj]
    return obj


def probe(path: str, timeout: float = 5.0) -> tuple[int, int] | None:
    """(major, minor) of the interpreter at *path*, or None when it does not run."""
    try:
        out = subprocess.run([path, "-I", "-c", _PROBE], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        major, minor = out.stdout.strip().split(".")
        return int(major), int(minor)
    except ValueError:
        return None


def is_shim(path: str) -> bool:
    """True for a version-manager shim (resolves per directory, so never linked)."""
    return any(p in path or p in os.path.realpath(path) for p in _SHIM_PARTS)


def is_unstable(path: str) -> bool:
    """True for a path inside a versioned install dir that an upgrade or uninstall removes."""
    return any(p in path for p in _UNSTABLE_PARTS)


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
        version = probe(override) if os.path.isabs(override) else None
        if version is None or version < MIN_VERSION:
            got = "does not run" if version is None else f"is {version[0]}.{version[1]}"
            raise InterpreterError(f"{OVERRIDE_ENV}={override} {got}; it must be an absolute path to python 3.10+")
        return Interpreter(override, version)
    later: list[str] = []
    checked: list[str] = []

    def try_path(path: str) -> Interpreter | None:
        version = probe(path)
        checked.append(f"{path}={'?' if version is None else '%d.%d' % version}")
        return Interpreter(path, version) if version is not None and version >= MIN_VERSION else None

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
    """True when the link exists and its target exists (no version probe)."""
    link = link_path(home)
    return os.path.islink(link) and os.path.exists(link)


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
