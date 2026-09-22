"""Schema-versioned install ledger at ``~/.claude/vexjoy/ledger.json``."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .common import SCHEMA_VERSION, utc_iso, utc_ts
from .fsops import Guard, atomic_write_json

STATUS_OK = "ok"
STATUS_STALE = "stale-source"


@dataclass
class LedgerEntry:
    """One owned install entry."""

    target: str
    dest: str
    kind: str
    source: str
    owner: str
    mode: str
    created_at: str
    sha256: str | None = None
    status: str = STATUS_OK


@dataclass
class Ledger:
    """Everything the engine owns."""

    schema: int = SCHEMA_VERSION
    source_root: str | None = None
    mode: str | None = None
    updated_at: str | None = None
    overlays_mtime: float | None = None
    entries: dict[str, LedgerEntry] = field(default_factory=dict)
    settings: dict[str, list[str]] = field(default_factory=dict)

    def for_target(self, target: str) -> dict[str, LedgerEntry]:
        """Entries of one target keyed by dest."""
        return {d: e for d, e in self.entries.items() if e.target == target}

    def to_json(self) -> dict:
        """Serializable form."""
        return {
            "schema": self.schema,
            "source_root": self.source_root,
            "mode": self.mode,
            "updated_at": self.updated_at,
            "overlays_mtime": self.overlays_mtime,
            "entries": [asdict(e) for e in sorted(self.entries.values(), key=lambda e: (e.target, e.dest))],
            "settings": {k: sorted(v) for k, v in sorted(self.settings.items())},
        }


class LedgerCorrupt(Exception):
    """The ledger file exists but cannot be parsed."""


def ledger_path(state_dir: Path) -> Path:
    """Ledger file location."""
    return state_dir / "ledger.json"


def load(path: Path) -> tuple[Ledger | None, str]:
    """Return (ledger, state) where state is ok | missing | corrupt."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "corrupt"
    try:
        return parse(json.loads(raw)), "ok"
    except (json.JSONDecodeError, LedgerCorrupt, KeyError, TypeError, ValueError):
        return None, "corrupt"


def parse(data: object) -> Ledger:
    """Validate and build a Ledger from JSON data."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
        raise LedgerCorrupt("bad schema")
    entries: dict[str, LedgerEntry] = {}
    for raw in data.get("entries", []):
        if not isinstance(raw, dict):
            raise LedgerCorrupt("bad entry")
        entry = LedgerEntry(**raw)
        entries[entry.dest] = entry
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise LedgerCorrupt("bad settings")
    return Ledger(
        schema=SCHEMA_VERSION,
        source_root=data.get("source_root"),
        mode=data.get("mode"),
        updated_at=data.get("updated_at"),
        overlays_mtime=data.get("overlays_mtime"),
        entries=entries,
        settings={str(k): list(v) for k, v in settings.items()},
    )


def save(path: Path, ledger: Ledger, guard: Guard) -> None:
    """Atomic write (temp + os.replace)."""
    ledger.updated_at = utc_iso()
    atomic_write_json(path, ledger.to_json(), guard, mode=0o600)


def quarantine(path: Path, guard: Guard) -> Path | None:
    """Rename a corrupt ledger to ``ledger.corrupt.<ts>``."""
    if not os.path.lexists(path):
        return None
    dest = path.with_name(f"ledger.corrupt.{utc_ts()}")
    guard.check(dest)
    os.rename(path, dest)
    return dest
