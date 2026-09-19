#!/usr/bin/env python3
"""Print the canonical, flat Codex skill deployment manifest.

The source tree contains implementation leaves and aggregate, user-facing
skills.  Codex must receive only the latter: the merged INDEX is the contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def manifest(source: Path) -> dict[str, Path]:
    merged: dict[str, dict] = {}
    # Tracked entries win; the local overlay may add private/runtime entries.
    for name in ("INDEX.local.json", "INDEX.json"):
        index = source / name
        if not index.is_file():
            continue
        data = json.loads(index.read_text(encoding="utf-8"))
        for skill_name, entry in data.get("skills", {}).items():
            if isinstance(entry, dict) and isinstance(entry.get("file"), str):
                merged[skill_name] = entry

    result: dict[str, Path] = {}
    root = source.parent.resolve()
    for skill_name, entry in merged.items():
        skill_file = (root / entry["file"]).resolve()
        # Local overlays can outlive a disabled/private source. Ignore such
        # entries; the synchronizer must not fail or resurrect a stale mirror.
        if skill_file.name == "SKILL.md" and skill_file.is_file() and root in skill_file.parents:
            result[skill_name] = skill_file.parent
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--format", choices=("tsv", "json"), default="tsv")
    args = parser.parse_args()
    entries = manifest(args.source.resolve())
    if args.format == "json":
        print(json.dumps({name: str(path) for name, path in entries.items()}, sort_keys=True))
    else:
        for name, path in sorted(entries.items()):
            print(f"{name}\t{path}")


if __name__ == "__main__":
    main()
