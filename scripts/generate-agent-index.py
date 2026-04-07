#!/usr/bin/env python3
"""
Generate agent routing index from YAML frontmatter.

Reads all agents/*.md files, extracts routing metadata from YAML frontmatter,
and generates agents/INDEX.json for fast /do router lookups.

Usage:
    python scripts/generate-agent-index.py

Output:
    agents/INDEX.json - Routing index for /do router
"""

import json
import re
from pathlib import Path

import yaml


def extract_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content.

    Uses PyYAML for parsing, with fallback to regex for complex description fields
    that contain colons (common in agent descriptions with examples).
    """
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    yaml_content = match.group(1)

    # Try PyYAML first
    try:
        return yaml.safe_load(yaml_content)
    except yaml.YAMLError:
        pass

    # Fallback: extract key fields via regex for complex frontmatter
    # This handles cases where description contains unquoted colons
    frontmatter = {}

    # Extract name
    name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_match:
        frontmatter["name"] = name_match.group(1).strip()

    # Extract description (everything after "description:" until next top-level key or end)
    desc_match = re.search(r"^description:\s*(.+?)(?=\n[a-z]+:|$)", yaml_content, re.MULTILINE | re.DOTALL)
    if desc_match:
        frontmatter["description"] = desc_match.group(1).strip()

    # Extract color
    color_match = re.search(r"^color:\s*(.+)$", yaml_content, re.MULTILINE)
    if color_match:
        frontmatter["color"] = color_match.group(1).strip()

    # Extract routing section if present
    routing_match = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_match:
        routing_content = routing_match.group(1)
        routing = {}

        # Extract triggers list
        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if triggers_match:
            triggers = re.findall(r"-\s+[\"']?([^\"'\n]+)[\"']?", triggers_match.group(1))
            routing["triggers"] = [t.strip() for t in triggers]

        # Extract pairs_with list
        pairs_match = re.search(r"pairs_with:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if pairs_match:
            pairs = re.findall(r"-\s+[\"']?([^\"'\n]+)[\"']?", pairs_match.group(1))
            routing["pairs_with"] = [p.strip() for p in pairs]

        # Extract complexity
        complexity_match = re.search(r"complexity:\s*(.+)$", routing_content, re.MULTILINE)
        if complexity_match:
            routing["complexity"] = complexity_match.group(1).strip()

        # Extract category
        category_match = re.search(r"category:\s*(.+)$", routing_content, re.MULTILINE)
        if category_match:
            routing["category"] = category_match.group(1).strip()

        if routing:
            frontmatter["routing"] = routing

    return frontmatter if frontmatter else None


def extract_short_description(description: str) -> str:
    """Extract first sentence or phrase from description."""
    # Handle escaped newlines
    desc = description.replace("\\n", " ")

    # Find "Use this agent when" pattern and extract the core purpose
    match = re.search(r"Use this agent when you need[^.]+", desc)
    if match:
        return match.group(0)

    # Fallback: first sentence
    sentences = desc.split(".")
    if sentences:
        return sentences[0].strip()

    return description[:100]


def generate_index(agents_dir: Path, relative_to: Path | None = None) -> dict:
    """Generate routing index from all agent files.

    Args:
        agents_dir: Directory containing agent markdown files.
        relative_to: If provided, agent file paths in the index will be relative
            to this directory (e.g. repo root), so private agents get
            ``private-agents/filename.md`` instead of bare ``filename.md``.
    """
    index = {"version": "1.0", "generated_by": "scripts/generate-agent-index.py", "agents": {}}
    errors = []

    for agent_file in sorted(agents_dir.glob("*.md")):
        try:
            content = agent_file.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"  - {agent_file.name}: Failed to read: {e}")
            continue

        try:
            frontmatter = extract_frontmatter(content)
        except Exception as e:
            errors.append(f"  - {agent_file.name}: Failed to parse frontmatter: {e}")
            frontmatter = None

        if not frontmatter:
            continue

        name = frontmatter.get("name", agent_file.stem)

        if relative_to:
            try:
                file_path = str(agents_dir.relative_to(relative_to) / agent_file.name)
            except ValueError:
                file_path = agent_file.name
        else:
            file_path = agent_file.name

        agent_entry = {
            "file": file_path,
            "short_description": extract_short_description(frontmatter.get("description", "")),
        }

        # Add routing metadata if present
        if "routing" in frontmatter:
            routing = frontmatter["routing"]
            if "triggers" in routing:
                agent_entry["triggers"] = routing["triggers"]
            if "pairs_with" in routing:
                agent_entry["pairs_with"] = routing["pairs_with"]
            if "complexity" in routing:
                agent_entry["complexity"] = routing["complexity"]
            if "category" in routing:
                agent_entry["category"] = routing["category"]
        else:
            # Generate triggers from name as fallback
            name_parts = name.replace("-", " ").split()
            agent_entry["triggers"] = [p for p in name_parts if p not in ("general", "engineer", "compact")]
            # Don't add category for agents without explicit routing metadata

        index["agents"][name] = agent_entry

    # Report errors if any
    if errors:
        print("Warnings during index generation:")
        for error in errors:
            print(error)

    return index


def main():
    """Main entry point."""
    # Find agents directory relative to script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    agents_dir = repo_root / "agents"

    if not agents_dir.exists():
        print(f"Error: agents directory not found at {agents_dir}")
        return 1

    # Generate index from public agents
    index = generate_index(agents_dir, relative_to=repo_root)

    # Also scan private agents if they exist (gitignored, user-specific)
    private_agents_dir = repo_root / "private-agents"
    if private_agents_dir.exists() and any(private_agents_dir.iterdir()):
        private_index = generate_index(private_agents_dir, relative_to=repo_root)
        index["agents"].update(private_index["agents"])

    # Write index file
    index_file = agents_dir / "INDEX.json"
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    # Summary
    print(f"Generated {index_file}")
    print(f"  Total agents: {len(index['agents'])}")

    # Show agents with routing metadata
    with_routing = sum(1 for a in index["agents"].values() if "complexity" in a)
    print(f"  With routing metadata: {with_routing}")
    print(f"  Without routing metadata: {len(index['agents']) - with_routing}")

    return 0


if __name__ == "__main__":
    exit(main())
