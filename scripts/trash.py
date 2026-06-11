#!/usr/bin/env python3
"""Move files to the XDG Trash instead of deleting them.

Safer `rm`: targets land in $XDG_DATA_HOME/Trash (default
~/.local/share/Trash) with a .trashinfo record, so file managers can
restore them. Rebuilt in Python from the `trash.ts` helper in
steipete/agent-scripts (evidence only, no code copied).

Usage:
    python3 scripts/trash.py path [path ...]
    python3 scripts/trash.py --allow-missing path [path ...]

Behavior:
    - Name collisions in the trash get a unique "-<nonce>-<n>" suffix.
    - Cross-filesystem moves fall back to copy + delete.
    - Missing targets fail the run unless --allow-missing is set.

Exit codes: 0 = all moved, 1 = missing target or move error, 2 = usage error
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

MAX_NAME_ATTEMPTS = 10_000


def trash_root() -> Path:
    """Return the XDG Trash root: $XDG_DATA_HOME/Trash or ~/.local/share/Trash."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "Trash"


def unique_dest(files_dir: Path, name: str) -> Path:
    """Return a free destination path in the trash for `name`."""
    candidate = files_dir / name
    if not candidate.exists() and not candidate.is_symlink():
        return candidate
    stem, ext = os.path.splitext(name)
    nonce = int(time.time() * 1000)
    for attempt in range(1, MAX_NAME_ATTEMPTS):
        candidate = files_dir / f"{stem}-{nonce}-{attempt}{ext}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise OSError(f"no free trash destination for {name}")


def write_trashinfo(info_dir: Path, dest_name: str, original: Path) -> None:
    """Write the XDG .trashinfo record so the file can be restored."""
    quoted = urllib.parse.quote(str(original))
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    info = f"[Trash Info]\nPath={quoted}\nDeletionDate={stamp}\n"
    (info_dir / f"{dest_name}.trashinfo").write_text(info, encoding="utf-8")


def move(source: Path, dest: Path) -> None:
    """Rename, with copy + delete fallback for cross-filesystem moves."""
    try:
        source.rename(dest)
    except OSError:
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, dest, symlinks=True)
            shutil.rmtree(source)
        else:
            shutil.copy2(source, dest, follow_symlinks=False)
            source.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Move paths to the XDG Trash.")
    parser.add_argument("--allow-missing", action="store_true", help="skip missing targets without failing")
    parser.add_argument("paths", nargs="+", help="files or directories to trash")
    args = parser.parse_args(argv)

    root = trash_root()
    files_dir = root / "files"
    info_dir = root / "info"
    files_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)

    failed = False
    for raw in args.paths:
        expanded = Path(raw).expanduser()
        # Resolve only the parent so a symlink target stays a symlink:
        # resolving the full path would trash the link's target file.
        target = expanded.parent.resolve(strict=False) / expanded.name
        if not target.exists() and not target.is_symlink():
            if args.allow_missing:
                continue
            print(f"Error: not found: {raw}", file=sys.stderr)
            failed = True
            continue
        try:
            dest = unique_dest(files_dir, target.name)
            move(target, dest)
            write_trashinfo(info_dir, dest.name, target)
            print(f"Trashed {raw} -> {dest}")
        except OSError as error:
            print(f"Error: {raw}: {error}", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
