#!/usr/bin/env python3
"""Validate the ``promoted_to`` retirement tag on skills.

``promoted_to: <successor>`` marks a skill whose content was folded into an
umbrella skill. ``scripts/generate-skill-index.py`` skips those husks, so the
tag removes the skill from skills/INDEX.json and therefore from the routing
manifest — the toolkit's own delete switch, applied by one frontmatter line
with no confirmation anywhere.

Two ways that goes wrong, one check each:

  P1 PHANTOM-SUCCESSOR   The successor names a skill that exists nowhere on
                         disk. The husk is retired in favour of nothing: the
                         skill leaves routing and no replacement carries its
                         traffic. Live case at the time of writing —
                         skills/meta/do/SKILL.md promoted to ``native-router``,
                         which silently dropped /do, the toolkit's own primary
                         router, out of the skill catalogue.

  P2 INVOCABLE-EXCLUDED  The husk still declares ``user-invocable: true``. It
                         advertises a user entry point the index no longer
                         carries, so ``/skill-name`` points at a skill the
                         router cannot see.

  P3 HUSK-ASSET-REFERENCED  A file outside every husk names a path inside one:
                         ``skills/<category>/<husk>/...`` or
                         ``~/.claude/skills/[<category>/]<husk>``. The installer
                         skips husks, so the script or reference that path
                         names never reaches an install. Live case at the time
                         of writing: the /do worktree rules ran
                         worktree_capacity.py out of the worktree-agent husk.
                         Move the asset into the successor and point the
                         caller there. Files inside the husk and tests are
                         not scanned.

Resolution order for a successor: repo skills/ (nested and flat layouts),
the merged skill index, then the deployed and private overlay roots — the
same roots scripts/validate-index-integrity.py resolves against, so a
private-overlay successor counts as real.

Exit codes:
    0 — every promoted_to tag resolves, no husk stays user-invocable, and no
        live file references a path inside a husk
    1 — one or more failures

Usage:
    python3 scripts/validate-promoted-successors.py
    python3 scripts/validate-promoted-successors.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter
from scripts.lib.index_freshness import ensure_fresh_indexes

# P3 scans the trees an agent reads or runs at runtime. Tests and generated
# indexes are skipped: a fixture may name a husk path on purpose.
_REFERENCE_ROOTS = ("agents", "commands", "docs", "hooks", "scripts", "skills")
_REFERENCE_SUFFIXES = {".js", ".json", ".md", ".mjs", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml"}
_SKIP_NAMES = {"INDEX.json", "INDEX.local.json"}


def skill_files(repo_root: Path) -> list[Path]:
    """Every SKILL.md under skills/, in both the nested and flat layouts."""
    skills_dir = repo_root / "skills"
    found = set(skills_dir.glob("*/SKILL.md")) | set(skills_dir.glob("*/*/SKILL.md"))
    return sorted(found)


def indexed_skill_names(repo_root: Path) -> set[str]:
    """Skill names in the merged tracked + local overlay index.

    Reading the index as well as the disk lets a successor that only ships in
    the private overlay resolve. A missing or unparseable index contributes
    nothing, which can only produce a stricter result, never a falsely clean one.
    """
    names: set[str] = set()
    index_dir = repo_root / "skills"
    for path in (index_dir / "INDEX.json", index_dir / "INDEX.local.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        skills = data.get("skills")
        if isinstance(skills, dict):
            names.update(skills)
    return names


def overlay_roots() -> list[Path]:
    """Deployed and private roots where a successor's SKILL.md may live."""
    candidates = [Path.home() / ".claude", Path.home() / "private-skills"]
    return [r for r in candidates if r.is_dir()]


def successor_exists(name: str, repo_root: Path, indexed: set[str]) -> bool:
    """True when *name* resolves to a real skill in any known root."""
    if not name:
        return False
    if name in indexed:
        return True
    roots = [repo_root, *overlay_roots()]
    for root in roots:
        skills_dir = root / "skills"
        if (skills_dir / name / "SKILL.md").is_file():
            return True
        if any(p.is_file() for p in skills_dir.glob(f"*/{name}/SKILL.md")):
            return True
    # Private overlay stores skills as <root>/<category>/<name>/SKILL.md.
    private = Path.home() / "private-skills"
    return private.is_dir() and any(p.is_file() for p in private.glob(f"*/{name}/SKILL.md"))


def _reference_files(repo_root: Path, husk_dirs: list[Path]) -> list[Path]:
    """Text files under the runtime roots, outside every husk and every tests/ dir."""
    husks = [d.resolve() for d in husk_dirs]
    files: list[Path] = []
    for name in _REFERENCE_ROOTS:
        base = repo_root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in _REFERENCE_SUFFIXES or path.name in _SKIP_NAMES or not path.is_file():
                continue
            if "tests" in path.relative_to(repo_root).parts:
                continue
            resolved = path.resolve()
            if any(resolved.is_relative_to(h) for h in husks):
                continue
            files.append(path)
    return files


def husk_reference_failures(repo_root: Path, husks: dict[str, tuple[Path, str]]) -> list[str]:
    """P3: lines outside every husk that name a path inside one.

    *husks* maps each husk's directory name (its install name) to its
    directory and successor.
    """
    if not husks:
        return []
    alternation = "|".join(re.escape(n) for n in sorted(husks, key=len, reverse=True))
    pattern = re.compile(
        rf"\.claude/skills/(?:[\w-]+/)?(?P<installed>{alternation})(?![\w-])"
        rf"|(?<![\w.-])skills/(?:[\w-]+/)?(?P<repo>{alternation})/"
    )
    failures: list[str] = []
    for path in _reference_files(repo_root, [d for d, _ in husks.values()]):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(repo_root)
        for lineno, line in enumerate(lines, 1):
            for match in pattern.finditer(line):
                name = match.group("installed") or match.group("repo")
                successor = husks[name][1]
                failures.append(
                    f"  [P3 HUSK-ASSET-REFERENCED] {rel}:{lineno}: '{match.group(0)}' points inside "
                    f"husk '{name}', which the installer skips, so that path never exists in an "
                    f"install. Move the asset into '{successor}' and point this line there."
                )
    return failures


def check(repo_root: Path, verbose: bool = False) -> list[str]:
    """Run P1 and P2 over every promoted skill, then P3 over every other file. Returns failure messages."""
    failures: list[str] = []
    indexed = indexed_skill_names(repo_root)
    promoted = 0
    husks: dict[str, tuple[Path, str]] = {}

    for skill_md in skill_files(repo_root):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        frontmatter, _ = parse_frontmatter(text)
        if not frontmatter:
            continue
        successor = frontmatter.get("promoted_to")
        if not successor:
            continue

        promoted += 1
        rel = skill_md.relative_to(repo_root)
        name = frontmatter.get("name", skill_md.parent.name)
        successor = str(successor).strip()
        husks[skill_md.parent.name] = (skill_md.parent, successor)

        if successor_exists(successor, repo_root, indexed):
            if verbose:
                print(f"  OK   {rel}: promoted_to '{successor}' resolves")
        else:
            failures.append(
                f"  [P1 PHANTOM-SUCCESSOR] {rel}: skill '{name}' is retired into "
                f"'{successor}', which exists nowhere in the repo. The generator drops "
                f"'{name}' from skills/INDEX.json, so it left routing with no successor "
                f"carrying its traffic. Point promoted_to at a real skill, or remove the "
                f"tag to return '{name}' to the index."
            )

        if frontmatter.get("user-invocable") is True:
            failures.append(
                f"  [P2 INVOCABLE-EXCLUDED] {rel}: skill '{name}' declares "
                f"user-invocable: true while promoted_to '{successor}' excludes it from "
                f"skills/INDEX.json. It advertises an entry point the router cannot see. "
                f"Set user-invocable: false, or drop promoted_to to keep it routable."
            )

    failures.extend(husk_reference_failures(repo_root, husks))

    if verbose:
        print(f"\nChecked {promoted} skill(s) carrying promoted_to")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="Show every promoted skill checked")
    args = parser.parse_args()

    # P2 reads skills/INDEX.json: regenerate a missing or stale one first.
    try:
        ensure_fresh_indexes(REPO_ROOT, ("skills",))
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Checking promoted_to successors...")
    failures = check(REPO_ROOT, verbose=args.verbose)

    for msg in failures:
        print(f"FAIL: {msg}")

    print("\n" + "=" * 60)
    print(f"Total failures: {len(failures)}")
    if failures:
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
