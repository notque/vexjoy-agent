#!/usr/bin/env python3
"""Add Companion Skills and Companion Pipelines sections to agents.

Scans agents/*.md, parses YAML frontmatter for routing.pairs_with, classifies
each paired entry as a skill (in skills/) or workflow (in skills/workflow/references/), and
injects separate '### Companion Skills' and '### Companion Pipelines' markdown
tables before '### Optional Behaviors' or '### Default Behaviors'.

Existing companion sections are removed and regenerated to stay current.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"
PIPELINES_DIR = REPO_ROOT / "skills" / "workflow" / "references"

SKILLS_MARKER = "### Companion Skills"
PIPELINES_MARKER = "### Companion Pipelines"


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Extract YAML frontmatter and the remaining body from a markdown file."""
    match = re.match(r"^---\n(.*?\n)---\n?(.*)", text, re.DOTALL)
    if not match:
        return None, text
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text
    return data, match.group(2)


def extract_description(frontmatter: dict) -> str:
    """Pull a one-line description from frontmatter, stripping examples and newlines."""
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

    Checks skills/{name}/SKILL.md first, then pipelines/, then agents/{name}.md.
    """
    for sdir in (SKILLS_DIR, PIPELINES_DIR):
        skill_path = sdir / name / "SKILL.md"
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


def is_pipeline(name: str) -> bool:
    """Check if a paired name lives in pipelines/ directory."""
    return (PIPELINES_DIR / name / "SKILL.md").exists()


def is_skill(name: str) -> bool:
    """Check if a paired name lives in skills/ directory (or is an agent)."""
    return (SKILLS_DIR / name / "SKILL.md").exists() or (AGENTS_DIR / f"{name}.md").exists()


def classify_pairs(pairs: list[str]) -> tuple[list[str], list[str]]:
    """Split pairs_with entries into skills and pipelines.

    Returns (skill_names, pipeline_names).
    """
    skills = []
    pipelines = []
    for name in pairs:
        if is_pipeline(name):
            pipelines.append(name)
        else:
            skills.append(name)
    return skills, pipelines


def build_section(names: list[str], kind: str) -> str:
    """Build a Companion Skills or Companion Pipelines markdown section.

    Args:
        names: List of skill/pipeline names.
        kind: Either "Skills" or "Pipelines".
    """
    rows: list[str] = []
    for name in names:
        desc = resolve_paired_description(name)
        if desc is None:
            desc = f"(description not found for `{name}`)"
        rows.append(f"| `{name}` | {desc} |")

    table_rows = "\n".join(rows)

    if kind == "Skills":
        return (
            "### Companion Skills (invoke via Skill tool when applicable)\n"
            "\n"
            "| Skill | When to Invoke |\n"
            "|-------|---------------|\n"
            f"{table_rows}\n"
            "\n"
            "**Rule**: If a companion skill exists for what you're about to do manually, use the skill instead.\n"
        )
    else:
        return (
            "### Companion Pipelines (invoke via Skill tool for structured multi-phase execution)\n"
            "\n"
            "| Pipeline | When to Invoke |\n"
            "|----------|---------------|\n"
            f"{table_rows}\n"
            "\n"
            "**Rule**: If a companion pipeline exists for a multi-step task, use it to get phase-gated execution with validation.\n"
        )


def remove_existing_sections(content: str) -> str:
    """Remove existing Companion Skills and Companion Pipelines sections.

    Removes from the ### heading through the **Rule** line (inclusive).
    """
    for marker in [SKILLS_MARKER, PIPELINES_MARKER]:
        idx = content.find(marker)
        if idx == -1:
            continue

        # Find the end of this section: next ### heading or end of content
        rest = content[idx:]
        # Find the **Rule** line that ends the section
        rule_match = re.search(r"\*\*Rule\*\*:.*\n", rest)
        if rule_match:
            end_idx = idx + rule_match.end()
        else:
            # Fallback: find next ### heading
            next_heading = re.search(r"\n###\s", rest[len(marker) :])
            if next_heading:
                end_idx = idx + len(marker) + next_heading.start()
            else:
                end_idx = len(content)

        # Remove the section, cleaning up extra blank lines
        before = content[:idx].rstrip("\n")
        after = content[end_idx:].lstrip("\n")
        content = before + "\n\n" + after

    return content


def insert_sections(content: str, skills_section: str | None, pipelines_section: str | None) -> str | None:
    """Insert Companion Skills and/or Pipelines sections before Optional/Default Behaviors."""
    combined = ""
    if pipelines_section:
        combined += pipelines_section + "\n"
    if skills_section:
        combined += skills_section + "\n"

    if not combined:
        return None

    # Try inserting before "### Optional Behaviors" first, then "### Default Behaviors"
    for marker in ["### Optional Behaviors", "### Default Behaviors"]:
        idx = content.find(marker)
        if idx != -1:
            before = content[:idx].rstrip("\n")
            after = content[idx:]
            return f"{before}\n\n{combined}{after}"
    return None


def process_agent(agent_path: Path) -> bool:
    """Process a single agent file, adding/updating Companion sections."""
    content = agent_path.read_text()

    fm, _ = parse_frontmatter(content)
    if fm is None:
        return False

    routing = fm.get("routing", {})
    if not isinstance(routing, dict):
        return False

    pairs = routing.get("pairs_with", [])
    if not pairs:
        return False

    skill_names, pipeline_names = classify_pairs(pairs)

    # Remove existing sections first (always regenerate)
    content = remove_existing_sections(content)

    # Build new sections
    skills_section = build_section(skill_names, "Skills") if skill_names else None
    pipelines_section = build_section(pipeline_names, "Pipelines") if pipeline_names else None

    new_content = insert_sections(content, skills_section, pipelines_section)
    if new_content is None:
        print(f"  SKIP (no insertion point): {agent_path.name}")
        return False

    agent_path.write_text(new_content)
    parts = []
    if skill_names:
        parts.append(f"{len(skill_names)} skill(s)")
    if pipeline_names:
        parts.append(f"{len(pipeline_names)} pipeline(s)")
    print(f"  UPDATED: {agent_path.name} ({', '.join(parts)})")
    return True


def main() -> int:
    """Scan all agent .md files and add Companion Skills/Pipelines sections."""
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
