"""Shared index resolution and tracked + local INDEX merge for the routing scripts.

Single source for the merge formerly hand-duplicated in routing-manifest.py,
pre-route.py, and index-router.py. Those scripts import this module; the
merge can no longer diverge between them.

``resolve_index(kind, target)`` (installer spec 7.2) picks the index a reader
uses, first match wins:

1. ``$VEXJOY_INDEX_DIR/<kind>.json`` when the variable is set. If it is set
   and the file is missing, step 2 is skipped (tests use this to pin the
   repo fallback).
2. ``~/.<target>/vexjoy/index/<kind>.json``, the installed index written by
   ``vexinstall`` (public + overlays), when it lists at least one item.
3. The repo public index ``<repo>/<kind>/INDEX.json``. Backward compatibility:
   on this step readers still overlay a legacy gitignored ``INDEX.local.json``
   when one exists, so routing keeps working until the engine installs an index.

Importable by name (underscores). The routing scripts add their own directory
to sys.path before importing, since they run as files, not as a package.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

INDEX_DIR_ENV = "VEXJOY_INDEX_DIR"
LEGACY_LOCAL = "INDEX.local.json"
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_index_items(tracked: Path, local_name: str | None, key: str) -> dict:
    """Load index items from the tracked file, overlaying the local override.

    Local override files (INDEX.local.json) are gitignored supersets produced
    by the generator with --include-private; they add entries for
    symlinked/private directories. The local file regenerates less often than
    the tracked one, so it can be stale. The merge is add-only (tracked first,
    local fills gaps per-name): a stale local can never hide a tracked skill
    or agent, and never overrides tracked entry content such as triggers or
    force_route — full replacement and per-name update both did.
    """
    items: dict = {}
    paths = [tracked]
    if local_name:
        local = tracked.parent / local_name
        if local.exists():
            paths.append(local)
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        loaded = raw.get(key, {})
        if isinstance(loaded, dict):
            for name, data in loaded.items():
                items.setdefault(name, data)
    return items


def installed_index_path(kind: str, target: str = "claude", home: Path | None = None) -> Path:
    """``~/.<target>/vexjoy/index/<kind>.json`` (may not exist)."""
    return (home if home is not None else Path.home()) / f".{target}" / "vexjoy" / "index" / f"{kind}.json"


def _lists_items(path: Path, kind: str) -> bool:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(raw, dict) and isinstance(raw.get(kind), dict) and bool(raw[kind])


def _resolve(kind: str, target: str, repo_root: Path | None, home: Path | None) -> tuple[Path, bool]:
    """(path, installed) where installed is False for the repo fallback."""
    env = os.environ.get(INDEX_DIR_ENV)
    if env:
        candidate = Path(env).expanduser() / f"{kind}.json"
        if candidate.is_file():
            return candidate, True
    else:
        candidate = installed_index_path(kind, target, home)
        if _lists_items(candidate, kind):
            return candidate, True
    return (repo_root if repo_root is not None else REPO_ROOT) / kind / "INDEX.json", False


def resolve_index(kind: str, target: str = "claude", repo_root: Path | None = None, home: Path | None = None) -> Path:
    """Path of the index a reader should use for *kind* (``skills`` or ``agents``)."""
    return _resolve(kind, target, repo_root, home)[0]


def resolve_index_with_base(
    kind: str, target: str = "claude", repo_root: Path | None = None, home: Path | None = None
) -> tuple[Path, Path, bool]:
    """(index path, base dir for relative ``file`` fields, installed?).

    Installed indexes (``<runtime>/vexjoy/index/<kind>.json``) resolve ``file``
    against the runtime root; ``$VEXJOY_INDEX_DIR`` indexes against the dir's
    grandparent when laid out the same way, else the repo root; the repo index
    against the repo root.
    """
    path, installed = _resolve(kind, target, repo_root, home)
    repo = repo_root if repo_root is not None else REPO_ROOT
    if installed and path.parent.name == "index" and path.parent.parent.name == "vexjoy":
        return path, path.parent.parent.parent, True
    return path, repo, installed


def load_resolved_items(
    kind: str,
    target: str = "claude",
    fallback: tuple[Path, str | None] | None = None,
    repo_root: Path | None = None,
    home: Path | None = None,
) -> dict:
    """Items of *kind* from the resolved index.

    *fallback* is the reader's ``(tracked, local_name)`` pair for step 3; it
    defaults to the repo public index plus the legacy ``INDEX.local.json``.
    """
    path, installed = _resolve(kind, target, repo_root, home)
    if installed:
        return load_index_items(path, None, kind)
    tracked, local_name = fallback if fallback is not None else (path, LEGACY_LOCAL)
    return load_index_items(tracked, local_name, kind)


TARGET_ENV = "VEXJOY_INDEX_TARGET"
RESOLVED_KINDS = frozenset({"skills", "agents"})
_RUNTIME_DIRS = {
    ".claude": "claude",
    ".codex": "codex",
    ".factory": "factory",
    ".hermes": "hermes",
    ".reasonix": "reasonix",
}


def detect_target(script_path: Path | str | None = None) -> str:
    """Runtime a reader serves: ``$VEXJOY_INDEX_TARGET``, else the ``~/.<runtime>``
    segment of the reader's unresolved path, else ``claude``."""
    env = os.environ.get(TARGET_ENV, "").strip()
    if env in _RUNTIME_DIRS.values():
        return env
    if script_path is not None:
        for part in reversed(Path(os.path.abspath(str(script_path))).parts):
            if part in _RUNTIME_DIRS:
                return _RUNTIME_DIRS[part]
    return "claude"


def load_items_for(
    kind: str,
    tracked: Path,
    local_name: str | None,
    target: str = "claude",
    repo_root: Path | None = None,
) -> dict:
    """Reader entry point: skills/agents go through ``resolve_index``; other
    kinds (pipelines) read *tracked* directly."""
    if kind in RESOLVED_KINDS:
        return load_resolved_items(kind, target, fallback=(tracked, local_name), repo_root=repo_root)
    return load_index_items(tracked, local_name, kind)
