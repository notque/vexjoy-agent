#!/usr/bin/env python3
"""Resolve a routing decision into concrete file paths for agent dispatch.

Takes an agent name, skill name(s), and optional injections from the
routing decision. Resolves to file paths in ~/.toolkit/ and outputs
a dispatch block the router prepends to the agent prompt.

Usage:
    python3 scripts/resolve-dispatch.py --agent golang-general-engineer --skill go-patterns
    python3 scripts/resolve-dispatch.py --agent golang-general-engineer --skill go-patterns --skill systematic-code-review
    python3 scripts/resolve-dispatch.py --agent golang-general-engineer --skill go-patterns --inject anti-rationalization-core --inject verification-checklist
    python3 scripts/resolve-dispatch.py --agent golang-general-engineer --skill go-patterns --request "fix goroutine leak"

Exit codes:
    0 — Success (dispatch block printed to stdout)
    1 — Agent not found
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLKIT_DIR = Path.home() / ".toolkit"
AGENTS_DIR = TOOLKIT_DIR / "agents"
SKILLS_DIR = TOOLKIT_DIR / "skills"
SHARED_PATTERNS_DIR = SKILLS_DIR / "shared-patterns"


def extract_model(path: Path) -> str | None:
    """Extract model field from YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    for line in text[3:end].split("\n"):
        stripped = line.strip()
        if stripped.startswith("model:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    return None


def resolve_agent(name: str) -> Path | None:
    path = AGENTS_DIR / f"{name}.md"
    return path if path.exists() else None


def resolve_skill(name: str) -> Path | None:
    path = SKILLS_DIR / name / "SKILL.md"
    return path if path.exists() else None


def resolve_injection(name: str) -> Path | None:
    """Resolve an injection name to a shared-patterns file."""
    path = SHARED_PATTERNS_DIR / f"{name}.md"
    if path.exists():
        return path
    path = SKILLS_DIR / name / "SKILL.md"
    return path if path.exists() else None


def list_references(base_dir: Path, name: str) -> list[Path]:
    """List reference .md files for an agent or skill."""
    refs_dir = base_dir / name / "references"
    if not refs_dir.exists():
        return []
    return sorted(refs_dir.glob("*.md"))


def format_dispatch(
    agent_path: Path | None,
    agent_model: str | None,
    skill_paths: list[tuple[str, Path]],
    inject_paths: list[tuple[str, Path]],
    agent_refs: list[Path],
    skill_refs: list[tuple[str, list[Path]]],
) -> str:
    lines = ["## Dispatch Package", "", "Read these files before starting work:", ""]

    if agent_path:
        lines.append(f"**Agent:** `{agent_path}`")
    if agent_model:
        lines.append(f"**Model:** `{agent_model}`")

    for name, path in skill_paths:
        lines.append(f"**Skill ({name}):** `{path}`")

    if inject_paths:
        lines.append("")
        for name, path in inject_paths:
            lines.append(f"**Inject ({name}):** `{path}`")

    if agent_refs:
        lines.append("")
        lines.append("**Agent references** (load those matching this task):")
        for ref in agent_refs:
            lines.append(f"  - `{ref}`")

    for skill_name, refs in skill_refs:
        if refs:
            lines.append("")
            lines.append(f"**{skill_name} references** (load those matching this task):")
            for ref in refs:
                lines.append(f"  - `{ref}`")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve routing to file paths.")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--skill", action="append", default=[], help="Skill name (repeatable)")
    parser.add_argument("--inject", action="append", default=[], help="Injection name (repeatable)")
    parser.add_argument("--request", default="", help="User request (for future reference matching)")
    args = parser.parse_args()

    agent_path = resolve_agent(args.agent)
    if not agent_path:
        print(f"Agent not found: {args.agent}", file=sys.stderr)
        return 1

    agent_model = extract_model(agent_path) if agent_path else None

    skill_paths = []
    skill_refs: list[tuple[str, list[Path]]] = []
    for skill_name in args.skill:
        path = resolve_skill(skill_name)
        if path:
            skill_paths.append((skill_name, path))
            refs = list_references(SKILLS_DIR, skill_name)
            if refs:
                skill_refs.append((skill_name, refs))

    inject_paths = []
    for inject_name in args.inject:
        path = resolve_injection(inject_name)
        if path:
            inject_paths.append((inject_name, path))

    agent_refs = list_references(AGENTS_DIR, args.agent)

    dispatch = format_dispatch(agent_path, agent_model, skill_paths, inject_paths, agent_refs, skill_refs)
    print(dispatch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
