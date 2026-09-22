"""Refresh installed routing indexes through the vexinstall engine (spec 7.3).

Shared by posttooluse-sync-skill-index.py and posttooluse-sync-agent-index.py.
They never write into a repo: for each installed target (claude plus every
present runtime dir) they run ``python3 -m vexinstall sync --index-only
--target <t>``, which writes only ``~/.<t>/vexjoy/index/``. The engine refuses
to publish an index for a target it has never applied.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_S = 12


def engine_scripts_dir() -> Path | None:
    """``<toolkit>/scripts`` holding the vexinstall package, via this hook's install."""
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    return scripts if (scripts / "vexinstall" / "__init__.py").is_file() else None


TARGETS = ("claude", "codex", "factory", "hermes", "reasonix")


def engine_targets(scripts: Path | None = None) -> list[str]:
    """Installed targets: claude plus every runtime root present under HOME."""
    home = Path.home()
    return [t for t in TARGETS if t == "claude" or (home / f".{t}").is_dir()]


def _index_stamps(target: str) -> dict[str, float]:
    index_dir = Path.home() / f".{target}" / "vexjoy" / "index"
    stamps: dict[str, float] = {}
    for name in ("skills.json", "agents.json"):
        try:
            stamps[name] = (index_dir / name).stat().st_mtime_ns
        except OSError:
            continue
    return stamps


def refresh_installed_indexes() -> tuple[list[str], list[str]]:
    """Run ``sync --index-only`` per engine target; returns (refreshed, errors)."""
    scripts = engine_scripts_dir()
    if scripts is None:
        return [], []
    refreshed: list[str] = []
    errors: list[str] = []
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in (str(scripts), os.environ.get("PYTHONPATH")) if p)}
    for target in engine_targets(scripts):
        before = _index_stamps(target)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "vexinstall", "sync", "--index-only", "--target", target],
                capture_output=True,
                text=True,
                env=env,
                timeout=TIMEOUT_S,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            errors.append(f"{target}: {type(exc).__name__}")
            continue
        skipped = "skipped" in proc.stdout
        if proc.returncode == 0 and not skipped and not proc.stderr.strip():
            if _index_stamps(target) != before:
                refreshed.append(target)
            else:
                errors.append(f"{target}: no installed index written (target never applied?)")
        elif skipped:
            errors.append(f"{target}: {proc.stdout.strip().splitlines()[0]}")
        else:
            errors.append(f"{target}: {(proc.stderr.strip().splitlines() or ['exit ' + str(proc.returncode)])[0]}")
    return refreshed, errors
