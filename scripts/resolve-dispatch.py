#!/usr/bin/env python3
"""Validate that a Haiku routing decision names real agent and skill files.

The Haiku router returns ``agent`` and ``skill`` names. Before the parent
dispatches work, this script confirms those names resolve to files on disk.
If the router picks a name that does not exist, we surface the invalid name
and the three closest matches so the user can narrow their request.

Canonical sources:

- Agents: ``~/.toolkit/agents/INDEX.json`` lists every toolkit agent by name.
  A repo-local ``.claude/agents/<name>.md`` in the current working directory
  overrides the toolkit entry of the same name.
- Skills: globbed from ``~/.toolkit/skills/*/SKILL.md``. A repo-local
  ``.claude/skills/<name>/SKILL.md`` in the current working directory
  overrides the toolkit entry.

Usage:
    python3 scripts/resolve-dispatch.py --agent golang-general-engineer --skill go-patterns
    python3 scripts/resolve-dispatch.py --agent python-general-engineer --skill ""
    python3 scripts/resolve-dispatch.py --agent "" --skill pr-workflow

Exit codes:
    0 — Every non-empty argument resolves to an existing file.
    2 — At least one argument does not resolve. Stderr names the invalid
        value and lists the three closest matches from the canonical lists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLKIT_DIR = Path.home() / ".toolkit"
AGENTS_DIR = TOOLKIT_DIR / "agents"
SKILLS_DIR = TOOLKIT_DIR / "skills"
AGENTS_INDEX = AGENTS_DIR / "INDEX.json"


def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Pure-Python implementation with O(len(a) * len(b)) time and
    O(min(len(a), len(b))) memory. Used to rank close-match suggestions.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Keep the shorter string as the inner loop for memory efficiency.
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                current[j - 1] + 1,  # insertion
                previous[j] + 1,  # deletion
                previous[j - 1] + cost,  # substitution
            )
        previous = current
    return previous[-1]


def load_canonical_agents() -> set[str]:
    """Return the set of canonical agent names.

    Reads ``~/.toolkit/agents/INDEX.json`` and unions any repo-local agent
    files under ``./.claude/agents/*.md``. Repo-local overrides add names
    that exist locally but not in the toolkit index.
    """
    names: set[str] = set()

    try:
        payload = json.loads(AGENTS_INDEX.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        payload = {}
    agents = payload.get("agents", {}) if isinstance(payload, dict) else {}
    if isinstance(agents, dict):
        names.update(agents.keys())

    local_dir = Path.cwd() / ".claude" / "agents"
    if local_dir.is_dir():
        for md in local_dir.glob("*.md"):
            names.add(md.stem)

    return names


def load_canonical_skills() -> set[str]:
    """Return the set of canonical skill names.

    Globs ``~/.toolkit/skills/*/SKILL.md`` and unions repo-local skill
    directories under ``./.claude/skills/*/SKILL.md``. Repo-local overrides
    add names that exist locally but not in the toolkit.
    """
    names: set[str] = set()

    if SKILLS_DIR.is_dir():
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            names.add(skill_md.parent.name)

    local_dir = Path.cwd() / ".claude" / "skills"
    if local_dir.is_dir():
        for skill_md in local_dir.glob("*/SKILL.md"):
            names.add(skill_md.parent.name)

    return names


def resolve_agent(name: str) -> Path | None:
    """Return the resolved path for an agent name, or None if missing.

    Repo-local ``./.claude/agents/<name>.md`` wins over the toolkit copy
    when both exist.
    """
    local = Path.cwd() / ".claude" / "agents" / f"{name}.md"
    if local.is_file():
        return local
    toolkit = AGENTS_DIR / f"{name}.md"
    if toolkit.is_file():
        return toolkit
    # Fall back to the INDEX.json pointer when the file is not at the
    # default location (the index records the canonical ``file`` path).
    try:
        payload = json.loads(AGENTS_INDEX.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    agents = payload.get("agents", {}) if isinstance(payload, dict) else {}
    entry = agents.get(name) if isinstance(agents, dict) else None
    if isinstance(entry, dict):
        file_ref = entry.get("file")
        if isinstance(file_ref, str):
            # Index paths are repo-relative; map them under ~/.toolkit.
            indexed = TOOLKIT_DIR / file_ref
            if indexed.is_file():
                return indexed
    return None


def resolve_skill(name: str) -> Path | None:
    """Return the resolved path for a skill name, or None if missing."""
    local = Path.cwd() / ".claude" / "skills" / name / "SKILL.md"
    if local.is_file():
        return local
    toolkit = SKILLS_DIR / name / "SKILL.md"
    if toolkit.is_file():
        return toolkit
    return None


def closest_matches(needle: str, haystack: set[str], limit: int = 3) -> list[str]:
    """Return up to ``limit`` closest names to ``needle`` by edit distance."""
    if not haystack:
        return []
    scored = sorted(haystack, key=lambda n: (levenshtein(needle, n), n))
    return scored[:limit]


def validate(kind: str, name: str, canonical: set[str], resolver) -> str | None:
    """Return an error string if ``name`` does not resolve, else None.

    ``kind`` is "agent" or "skill" for the error message. ``resolver`` is
    the function that maps a name to a Path or None.
    """
    if resolver(name) is not None:
        return None
    matches = closest_matches(name, canonical)
    if matches:
        suggestion = ", ".join(matches)
    else:
        suggestion = "(no close matches found)"
    return f"router picked invalid {kind}: {name}. closest matches: {suggestion}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Haiku routing decision against the canonical agent and skill lists."
    )
    parser.add_argument(
        "--agent",
        default="",
        help="Agent name from the router, or empty string when the router returned null.",
    )
    parser.add_argument(
        "--skill",
        default="",
        help="Skill name from the router, or empty string when the router returned null.",
    )
    args = parser.parse_args(argv)

    agent = args.agent.strip()
    skill = args.skill.strip()

    if not agent and not skill:
        print(
            "resolve-dispatch: at least one of --agent or --skill must be non-empty.",
            file=sys.stderr,
        )
        return 2

    errors: list[str] = []

    if agent:
        canonical_agents = load_canonical_agents()
        err = validate("agent", agent, canonical_agents, resolve_agent)
        if err:
            errors.append(err)

    if skill:
        canonical_skills = load_canonical_skills()
        err = validate("skill", skill, canonical_skills, resolve_skill)
        if err:
            errors.append(err)

    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
