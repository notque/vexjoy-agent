#!/usr/bin/env python3
"""Print the canonical, flat Codex skill deployment manifest.

The source tree contains implementation leaves and aggregate, user-facing
skills.  Codex must receive only the latter: the resolved INDEX is the
contract. The index comes from ``routing_index_merge.resolve_index("skills",
"codex")`` (installer spec 7.2); this script keeps no merge of its own.

Only skills whose SKILL.md resolves inside the source repo are listed: this is
the public source catalog for the legacy Codex mirror. An installed index entry
whose file does not resolve into the repo (a copy under ``~/.codex``) falls back
to the repo public index entry of the same name.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from routing_index_merge import LEGACY_LOCAL, load_index_items, load_resolved_items, resolve_index_with_base


def _source_file(base: Path, entry: object, root: Path) -> Path | None:
    if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
        return None
    skill_file = (base / entry["file"]).resolve()
    # Stale entries can outlive a disabled/private source. Ignore such entries;
    # the synchronizer must not fail or resurrect a stale mirror.
    if skill_file.name == "SKILL.md" and skill_file.is_file() and root in skill_file.parents:
        return skill_file
    return None


def manifest(source: Path) -> dict[str, Path]:
    root = source.parent.resolve()
    _, base, installed = resolve_index_with_base("skills", "codex", repo_root=root)
    catalog = load_resolved_items("skills", "codex", fallback=(source / "INDEX.json", LEGACY_LOCAL), repo_root=root)
    public = load_index_items(source / "INDEX.json", None, "skills") if installed else {}
    result: dict[str, Path] = {}
    for skill_name, entry in catalog.items():
        skill_file = _source_file(base, entry, root)
        if skill_file is None and skill_name in public:
            skill_file = _source_file(root, public[skill_name], root)
        if skill_file is not None:
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
