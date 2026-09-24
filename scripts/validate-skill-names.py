#!/usr/bin/env python3
"""Fail when two public skills share a flat name across categories.

Skills install flat: ``skills/<cat>/<name>`` becomes ``<name>``. Two public
skills with the same ``<name>`` would collide in every runtime.

Also fails when a top-level ``skills/`` dir holds neither a SKILL.md nor
nested skills and is not registered in vexinstall ``SUPPORT_DIRS`` or
``DATA_DIRS``: the installer ships only registered support dirs, so such a
dir silently stops reaching runtimes.

Usage:
    python3 scripts/validate-skill-names.py [--repo PATH]

Exit codes: 0 unique, 1 duplicates found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vexinstall.common import DATA_DIRS, SUPPORT_DIRS

SUPPORT_OR_DATA = SUPPORT_DIRS | DATA_DIRS


def find_duplicates(repo: Path) -> dict[str, list[str]]:
    """Flat name -> repo-relative skill dirs, for names defined more than once."""
    seen: dict[str, list[str]] = {}
    skills = repo / "skills"
    if not skills.is_dir():
        return {}
    for top in sorted(skills.iterdir()):
        if not top.is_dir() or top.name.startswith(".") or top.name in SUPPORT_OR_DATA:
            continue
        if (top / "SKILL.md").is_file():
            seen.setdefault(top.name, []).append(top.relative_to(repo).as_posix())
            continue
        for child in sorted(top.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                seen.setdefault(child.name, []).append(child.relative_to(repo).as_posix())
    return {name: paths for name, paths in seen.items() if len(paths) > 1}


def find_unregistered_dirs(repo: Path, registered: frozenset[str] = SUPPORT_OR_DATA) -> list[str]:
    """Top-level skills/ dirs with no skill inside that the installer does not know."""
    skills = repo / "skills"
    if not skills.is_dir():
        return []
    unknown = []
    for top in sorted(skills.iterdir()):
        if not top.is_dir() or top.name.startswith(".") or top.name == "__pycache__":
            continue
        if (top / "SKILL.md").is_file() or any((c / "SKILL.md").is_file() for c in top.iterdir() if c.is_dir()):
            continue
        if top.name not in registered:
            unknown.append(top.name)
    return unknown


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    dups = find_duplicates(args.repo.resolve())
    for name, paths in sorted(dups.items()):
        print(f"duplicate skill name '{name}': {', '.join(paths)}")
    unknown = find_unregistered_dirs(args.repo.resolve())
    for name in unknown:
        print(f"skills/{name}/ holds no skill; register it in vexinstall SUPPORT_DIRS or DATA_DIRS")
    if dups or unknown:
        return 1
    print("validate-skill-names: all public skill names are unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
