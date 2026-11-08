"""The rollback point that ``./install.sh --rollback`` restores: ``<state>/rollback.json``.

apply, uninstall, and ``prune --unowned --confirm`` record the trash session and the
settings.json backup they made. sync never records, so a session-start sync cannot become
what a rollback restores. Steps that share a run id (``--run-id``; install.sh passes one per
run) add to one point, so a rollback restores a whole ``./install.sh`` run, its prune included,
and nothing older. A step that trashed nothing and backed up nothing leaves the point alone.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .common import parse_ts
from .fsops import Guard, atomic_write_json

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")  # \Z: "$" would let a trailing newline in
_COMMANDS = ("apply", "uninstall", "prune")


@dataclass
class Point:
    """What one run changed that a rollback can put back."""

    run: str
    commands: list[str] = field(default_factory=list)
    trash: list[str] = field(default_factory=list)  # trash session timestamps, oldest first
    settings_backup: str | None = None  # backups/settings.<ts>.json taken before the run's first settings write
    restored_at: str | None = None


def point_path(state_dir: Path) -> Path:
    """Location of the rollback point."""
    return state_dir / "rollback.json"


def _ts_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and parse_ts(value) is not None else None


def load(state_dir: Path) -> Point | None:
    """The recorded point, or None when there is none or it is unreadable.

    Timestamps that do not parse as engine timestamps are dropped, so a damaged file can never
    name a path outside the trash and backup dirs.
    """
    try:
        data = json.loads(point_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("run"), str) or not RUN_ID_RE.match(data["run"]):
        return None
    commands = data.get("commands")
    trash = data.get("trash")
    restored = data.get("restored_at")
    return Point(
        run=data["run"],
        commands=[c for c in commands if c in _COMMANDS] if isinstance(commands, list) else [],
        trash=[t for t in trash if _ts_or_none(t)] if isinstance(trash, list) else [],
        settings_backup=_ts_or_none(data.get("settings_backup")),
        restored_at=restored if isinstance(restored, str) else None,
    )


def save(state_dir: Path, point: Point, guard: Guard) -> None:
    """Write the point (mode 600)."""
    atomic_write_json(point_path(state_dir), asdict(point), guard, mode=0o600)


def record(
    state_dir: Path, guard: Guard, *, run: str, command: str, trash: str | None, settings_backup: str | None
) -> None:
    """Add one step's trash session and settings backup to the point for *run*.

    A new run id starts a new point; so does a point that was already rolled back.
    """
    if trash is None and settings_backup is None:
        return
    point = load(state_dir)
    if point is None or point.run != run or point.restored_at is not None:
        point = Point(run=run)
    point.commands.append(command)
    if trash is not None:
        point.trash.append(trash)
    if point.settings_backup is None:
        point.settings_backup = settings_backup
    save(state_dir, point, guard)
