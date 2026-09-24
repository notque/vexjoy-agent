"""Write ``~/.claude/vexjoy/overlays.json`` from the legacy private roots (``install.sh --migrate-overlays``)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .common import GuardError, OverlayConfigError, is_inside, realpath, utc_ts
from .context import Options, Result, resolve_source_root, state_dir
from .fsops import Guard, atomic_write_bytes, mkdirs
from .sources import load_overlays


def _tilde(path: Path, home: Path) -> str:
    try:
        return "~/" + path.relative_to(home).as_posix()
    except ValueError:
        return str(path)


def build_overlays(home: Path, repo_root: Path) -> tuple[dict, list[str]]:
    """Desired overlays.json from the legacy roots; returns (config, warnings).

    Legacy roots, as the old writers used them:
      * ``~/private-skills`` (sync hook): category layout; ``voice`` deploys
        with a ``voice-`` prefix, so it becomes its own flat, prefixed overlay
        and the outer overlay excludes it.
      * ``~/private-skills-jev-workbench``: flat.
      * ``<repo>/private-skills`` (install.sh): rejected when inside the repo.
    Never emits an ``overrides`` key.
    """
    overlays: list[dict] = []
    warnings: list[str] = []
    priv = home / "private-skills"
    if priv.is_dir():
        overlays.append(
            {
                "id": "private",
                "root": _tilde(priv, home),
                "layout": "category",
                "kinds": ["skills", "agents"],
                "exclude": ["voice"],
            }
        )
        if (priv / "voice").is_dir():
            overlays.append(
                {"id": "voices", "root": _tilde(priv / "voice", home), "layout": "flat", "prefix": "voice-"}
            )
    bench = home / "private-skills-jev-workbench"
    if bench.is_dir():
        overlays.append({"id": "workbench", "root": _tilde(bench, home), "layout": "flat"})
    repo_real = realpath(repo_root)
    for name in ("private-skills", "private-agents", "private-voices"):
        legacy = repo_root / name
        if not os.path.lexists(legacy):
            continue
        if is_inside(realpath(legacy), repo_real):
            warnings.append(f"skipped {name}: {legacy} is inside the repo (overlay roots must live outside it)")
            continue
        if name != "private-skills":
            warnings.append(f"skipped {name}: {legacy} has no overlay equivalent; migrate it by hand")
            continue
        target = Path(realpath(legacy))
        if str(target) in (realpath(priv), realpath(bench)):
            continue
        overlays.append({"id": "repo-private", "root": str(target), "layout": "category"})
    return {"overlays": overlays}, warnings


def migrate_overlays(home: Path, repo_root: Path, *, dry_run: bool = False) -> tuple[Path, dict, list[str], str]:
    """Write ``~/.claude/vexjoy/overlays.json``; returns (path, config, warnings, status).

    status: ``written`` | ``unchanged`` | ``dry-run``. A differing existing file
    is backed up to ``backups/overlays.<ts>.json`` first. The config is validated
    with the engine's loader before it replaces the active file.
    """
    cfg, warnings = build_overlays(home, repo_root)
    path = state_dir(home) / "overlays.json"
    blob = (json.dumps(cfg, indent=2) + "\n").encode()
    guard = Guard.for_roots([repo_root])
    tmp_check = json.loads(blob)
    if "overrides" in tmp_check:  # defensive; build_overlays never emits it
        raise OverlayConfigError("overlays: refusing to write an 'overrides' key")
    if dry_run:
        return path, cfg, warnings, "dry-run"
    try:
        if path.read_bytes() == blob:
            return path, cfg, warnings, "unchanged"
    except OSError:
        pass
    mkdirs(path.parent, guard)
    guard.check(path.parent / ".overlays-validation")
    with tempfile.TemporaryDirectory(prefix=".overlays-validation-", dir=path.parent) as temp_dir:
        validation_path = Path(temp_dir) / "overlays.json"
        atomic_write_bytes(validation_path, blob, guard, mode=0o600)
        load_overlays(validation_path, repo_root, home)
    if path.exists():
        backups = state_dir(home) / "backups"
        mkdirs(backups, guard)
        atomic_write_bytes(backups / f"overlays.{utc_ts()}.json", path.read_bytes(), guard, mode=0o600)
    atomic_write_bytes(path, blob, guard, mode=0o600)
    return path, cfg, warnings, "written"


def run_migrate_overlays(opts: Options) -> Result:
    """CLI ``migrate-overlays``: write overlays.json; ``--dry-run`` prints it only."""
    home = opts.home
    repo = (opts.source_root or resolve_source_root(opts, None)).absolute()
    try:
        path, cfg, warnings, status = migrate_overlays(home, repo, dry_run=opts.dry_run)
    except (OverlayConfigError, GuardError) as exc:
        return Result(code=int(exc.exit_code), err=[f"[migrate-overlays] error: {exc}"])
    ids = ", ".join(
        f"{o['id']} ({o['layout']}{', prefix ' + o['prefix'] if o.get('prefix') else ''})" for o in cfg["overlays"]
    )
    out = [f"[migrate-overlays] {status}: {path} -> {len(cfg['overlays'])} overlay(s): {ids or 'none'}"]
    return Result(out=out, err=[f"[migrate-overlays] warning: {w}" for w in warnings], data=cfg)
