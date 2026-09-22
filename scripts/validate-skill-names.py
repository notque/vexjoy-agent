#!/usr/bin/env python3
"""Fail when two public skills share a flat name across categories.

Skills install flat: ``skills/<cat>/<name>`` becomes ``<name>``. Two public
skills with the same ``<name>`` would collide in every runtime.

Usage:
    python3 scripts/validate-skill-names.py [--repo PATH]

Exit codes: 0 unique, 1 duplicates found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SUPPORT_OR_DATA = {"shared-patterns", "kb", "voice-shared", "reddit-data", "synced"}


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


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    dups = find_duplicates(args.repo.resolve())
    for name, paths in sorted(dups.items()):
        print(f"duplicate skill name '{name}': {', '.join(paths)}")
    if dups:
        return 1
    print("validate-skill-names: all public skill names are unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
