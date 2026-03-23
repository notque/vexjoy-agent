#!/usr/bin/env python3
"""Add Companion Skills sections to agents that declare pairs_with in their routing metadata.

Scans agents/*.md, parses YAML frontmatter for routing.pairs_with, resolves each
paired skill/agent description from its SKILL.md or agent .md frontmatter, and
injects a '### Companion Skills' markdown table before '### Optional Behaviors'
or '### Default Behaviors'. Agents that already have the section are skipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"

SKIP_MARKER = "### Companion Skills"


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Extract YAML frontmatter and the remaining body from a markdown file.

    Args:
        text: Full file content.

    Returns:
        Tuple of (parsed YAML dict or None, body after frontmatter).
    """
    match = re.match(r"^---\n(.*?\n)---\n?(.*)", text, re.DOTALL)
    if not match:
        return None, text
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text
    return data, match.group(2)


def extract_description(frontmatter: dict) -> str:
    """Pull a one-line description from frontmatter, stripping examples and newlines.

    Args:
        frontmatter: Parsed YAML frontmatter dict.

    Returns:
        A single-line description string suitable for a table cell.
    """
    desc = frontmatter.get("description", "")
    if not desc:
        return ""
    # Take only text before any <example> block or double newline (paragraph break)
    desc = re.split(r"<example>|\n\n", str(desc))[0]
    # Collapse whitespace
    desc = re.sub(r"\s+", " ", desc).strip()
    # Truncate if very long (keep it readable in a table)
    if len(desc) > 120:
        desc = desc[:117] + "..."
    return desc


def resolve_paired_description(name: str) -> str | None:
    """Look up description for a paired skill or agent by name.

    Checks skills/{name}/SKILL.md first, then agents/{name}.md.

    Args:
        name: The skill or agent name from pairs_with.

    Returns:
        Description string, or None if not found.
    """
    # Try skill first
    skill_path = SKILLS_DIR / name / "SKILL.md"
    if skill_path.exists():
        fm, _ = parse_frontmatter(skill_path.read_text())
        if fm:
            return extract_description(fm)

    # Try agent
    agent_path = AGENTS_DIR / f"{name}.md"
    if agent_path.exists():
        fm, _ = parse_frontmatter(agent_path.read_text())
        if fm:
            return extract_description(fm)

    return None


def build_companion_section(pairs: list[str]) -> str:
    """Build the Companion Skills markdown section from a list of paired names.

    Args:
        pairs: List of skill/agent names from routing.pairs_with.

    Returns:
        Markdown string for the Companion Skills section.
    """
    rows: list[str] = []
    for name in pairs:
        desc = resolve_paired_description(name)
        if desc is None:
            desc = f"(description not found for `{name}`)"
        rows.append(f"| `{name}` | {desc} |")

    table_rows = "\n".join(rows)
    return (
        "### Companion Skills (invoke via Skill tool when applicable)\n"
        "\n"
        "| Skill | When to Invoke |\n"
        "|-------|---------------|\n"
        f"{table_rows}\n"
        "\n"
        "**Rule**: If a companion skill exists for what you're about to do manually, use the skill instead.\n"
    )


def insert_section(content: str, section: str) -> str | None:
    """Insert the Companion Skills section before Optional or Default Behaviors.

    Args:
        content: Full file content of the agent markdown.
        section: The generated Companion Skills section markdown.

    Returns:
        Modified content with section inserted, or None if no insertion point found.
    """
    # Try inserting before "### Optional Behaviors" first
    for marker in ["### Optional Behaviors", "### Default Behaviors"]:
        idx = content.find(marker)
        if idx != -1:
            # Insert before the marker, with proper spacing
            before = content[:idx].rstrip("\n")
            after = content[idx:]
            return f"{before}\n\n{section}\n{after}"
    return None


def process_agent(agent_path: Path) -> bool:
    """Process a single agent file, adding Companion Skills if needed.

    Args:
        agent_path: Path to the agent .md file.

    Returns:
        True if the file was modified, False otherwise.
    """
    content = agent_path.read_text()

    # Skip if already has Companion Skills
    if SKIP_MARKER in content:
        print(f"  SKIP (already present): {agent_path.name}")
        return False

    fm, _ = parse_frontmatter(content)
    if fm is None:
        print(f"  SKIP (no frontmatter): {agent_path.name}")
        return False

    routing = fm.get("routing", {})
    if not isinstance(routing, dict):
        return False

    pairs = routing.get("pairs_with", [])
    if not pairs:
        return False

    section = build_companion_section(pairs)
    new_content = insert_section(content, section)
    if new_content is None:
        print(f"  SKIP (no insertion point): {agent_path.name}")
        return False

    agent_path.write_text(new_content)
    print(f"  UPDATED: {agent_path.name} ({len(pairs)} companion(s))")
    return True


def main() -> int:
    """Scan all agent .md files and add Companion Skills sections.

    Returns:
        Exit code: 0 on success, 1 if no agents directory found.
    """
    if not AGENTS_DIR.is_dir():
        print(f"ERROR: agents directory not found at {AGENTS_DIR}", file=sys.stderr)
        return 1

    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    updated = 0
    skipped_no_pairs = 0

    print(f"Scanning {len(agent_files)} agent files in {AGENTS_DIR}...")
    for agent_path in agent_files:
        content = agent_path.read_text()
        fm, _ = parse_frontmatter(content)
        if fm is None:
            continue

        routing = fm.get("routing", {})
        if not isinstance(routing, dict):
            continue

        pairs = routing.get("pairs_with", [])
        if not pairs:
            skipped_no_pairs += 1
            continue

        if process_agent(agent_path):
            updated += 1

    print(f"\nDone. Updated: {updated}, No pairs_with: {skipped_no_pairs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
