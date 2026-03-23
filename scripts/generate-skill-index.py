#!/usr/bin/env python3
"""
Generate skill routing index from YAML frontmatter.

Reads all skills/*/SKILL.md files, extracts routing metadata from YAML frontmatter,
and generates skills/INDEX.json for fast /do router lookups.

Usage:
    python scripts/generate-skill-index.py

Output:
    skills/INDEX.json - Routing index for /do router

Exit codes:
    0 - Success
    1 - Fatal error (directory not found, write failed)
    2 - Completed with warnings (some skills failed to parse)
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def extract_frontmatter(content: str) -> tuple[dict | None, bool]:
    """Extract YAML frontmatter from markdown content.

    Attempts YAML parsing first, then falls back to regex extraction
    for key fields (name, description, version, user-invocable, routing)
    when YAML parsing fails due to malformed or edge-case frontmatter.

    Returns:
        tuple: (frontmatter dict or None, used_fallback bool)
    """
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None, False

    yaml_content = match.group(1)

    try:
        result = yaml.safe_load(yaml_content)
        return result, False
    except yaml.YAMLError as e:
        # Log the parsing failure - regex fallback will be attempted
        print(f"  Warning: YAML parsing failed, using regex fallback: {e}", file=sys.stderr)

    # Fallback: extract key fields via regex when YAML parsing fails
    frontmatter = {}

    name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_match:
        frontmatter["name"] = name_match.group(1).strip()

    # Handle YAML block scalar indicators (> for folded, | for literal)
    desc_match = re.search(
        r"^description:\s*(?:[>|][\-+]?\s*\n\s+)?(.+?)(?=\n[a-z_-]+:|$)",
        yaml_content,
        re.MULTILINE | re.DOTALL,
    )
    if desc_match:
        # Clean up multiline descriptions
        desc = desc_match.group(1).strip()
        desc = re.sub(r"\s+", " ", desc)
        frontmatter["description"] = desc

    version_match = re.search(r"^version:\s*(.+)$", yaml_content, re.MULTILINE)
    if version_match:
        frontmatter["version"] = version_match.group(1).strip()

    # Normalize to lowercase for boolean comparison (handles "True", "TRUE", etc.)
    user_invocable_match = re.search(r"^user-invocable:\s*(.+)$", yaml_content, re.MULTILINE)
    if user_invocable_match:
        val = user_invocable_match.group(1).strip().lower()
        frontmatter["user-invocable"] = val == "true"

    # Parse nested routing section structure:
    #   routing:
    #     triggers:
    #       - "trigger1"
    #       - trigger2
    #     category: category-name
    routing_match = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_match:
        routing_content = routing_match.group(1)
        routing = {}

        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if triggers_match:
            triggers = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', triggers_match.group(1))
            routing["triggers"] = [t.strip() for t in triggers]

        category_match = re.search(r"category:\s*(.+)$", routing_content, re.MULTILINE)
        if category_match:
            routing["category"] = category_match.group(1).strip()

        if routing:
            frontmatter["routing"] = routing

    return (frontmatter if frontmatter else None), True


def extract_short_description(description: str) -> str:
    """Extract first sentence from description, truncating to 150 chars if needed."""
    if not description:
        return ""

    desc = description.replace("\\n", " ").strip()
    desc = re.sub(r"\s+", " ", desc)

    # First sentence - but don't split on dots in identifiers like t.Run, Next.js,
    # config.fish, CLAUDE.md (dot followed by lowercase letter or known extension)
    match = re.match(r"((?:[^.!?]|\.(?=[a-zA-Z0-9_]))+[.!?])", desc)
    if match and len(match.group(1)) <= 200:
        return match.group(1).strip()

    # Truncate if too long
    if len(desc) > 150:
        return desc[:147] + "..."

    return desc


def generate_index(skills_dir: Path, dir_prefix: str | None = None) -> tuple[dict, list[str]]:
    """Generate routing index from all skill directories.

    Scans skills_dir for subdirectories containing SKILL.md files,
    extracts frontmatter, and builds index entries with routing metadata.

    Args:
        skills_dir: Directory to scan for skill subdirectories.
        dir_prefix: Override for the file path prefix (e.g., "pipelines" instead of "skills").
                    If None, uses the directory name.

    Returns:
        tuple: (index dict with keys: version, generated, generated_by, skills[],
                list of warning messages)
    """
    # Index format version - increment on breaking changes to schema
    index = {
        "version": "1.1",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/generate-skill-index.py",
        "skills": [],
    }
    warnings = []

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            # Skip directories without SKILL.md
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"  - {skill_dir.name}: Failed to read: {e}")
            continue

        try:
            frontmatter, used_fallback = extract_frontmatter(content)
            if used_fallback:
                warnings.append(f"  - {skill_dir.name}: Used regex fallback (YAML parsing failed)")
        except re.error as e:
            warnings.append(f"  - {skill_dir.name}: Regex error in frontmatter: {e}")
            frontmatter = None

        if not frontmatter:
            warnings.append(f"  - {skill_dir.name}: No valid frontmatter found")
            continue

        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")

        skill_entry = {
            "name": name,
            "description": extract_short_description(description),
            "file": f"{dir_prefix or skills_dir.name}/{skill_dir.name}/SKILL.md",
        }

        # Add routing metadata if present
        if "routing" in frontmatter:
            routing = frontmatter["routing"]
            if "triggers" in routing:
                skill_entry["triggers"] = routing["triggers"]
            if "category" in routing:
                skill_entry["category"] = routing["category"]
        else:
            # Generate triggers from name as fallback
            # Filter short words (articles, prepositions) that make poor search triggers
            name_parts = name.replace("-", " ").split()
            stop_words = {"skill", "pipeline", "the", "and", "for", "with"}
            triggers = [p for p in name_parts if len(p) > 2 and p.lower() not in stop_words]
            # Include the full skill name as first trigger for exact matching
            skill_entry["triggers"] = [name] + triggers

        # Add version if present
        if "version" in frontmatter:
            skill_entry["version"] = frontmatter["version"]

        # Add user-invocable status (keep original kebab-case key name)
        if "user-invocable" in frontmatter:
            skill_entry["user-invocable"] = frontmatter["user-invocable"]

        index["skills"].append(skill_entry)

    return index, warnings


def main() -> int:
    """Main entry point."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    skills_dir = repo_root / "skills"

    if not skills_dir.exists():
        print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
        return 1

    # Generate index from public skills
    index, warnings = generate_index(skills_dir)

    # Also scan pipelines directory (pipelines are skills with phases)
    pipelines_dir = repo_root / "pipelines"
    if pipelines_dir.exists() and any(pipelines_dir.iterdir()):
        pipeline_index, pipeline_warnings = generate_index(pipelines_dir)
        existing_names = {s["name"] for s in index["skills"]}
        for skill in pipeline_index["skills"]:
            if skill["name"] in existing_names:
                index["skills"] = [s for s in index["skills"] if s["name"] != skill["name"]]
            index["skills"].append(skill)
        warnings.extend(pipeline_warnings)

    # Also scan private skills if they exist (gitignored, user-specific)
    private_skills_dir = repo_root / "private-skills"
    if private_skills_dir.exists() and any(private_skills_dir.iterdir()):
        private_index, private_warnings = generate_index(private_skills_dir)
        existing_names = {s["name"] for s in index["skills"]}
        for skill in private_index["skills"]:
            if skill["name"] in existing_names:
                index["skills"] = [s for s in index["skills"] if s["name"] != skill["name"]]
            index["skills"].append(skill)
        warnings.extend(private_warnings)

    # Report warnings if any
    if warnings:
        print("Warnings during index generation:", file=sys.stderr)
        for warning in warnings:
            print(warning, file=sys.stderr)

    # Validate index has content before writing
    if not index["skills"]:
        print("Error: No skills found. INDEX.json not written.", file=sys.stderr)
        return 1

    # Write index file
    index_file = skills_dir / "INDEX.json"
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
    except PermissionError:
        print(f"Error: Permission denied writing to {index_file}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error: Failed to write index file: {e}", file=sys.stderr)
        return 1

    # Summary (to stdout)
    print(f"Generated {index_file}")
    print(f"  Total skills: {len(index['skills'])}")

    # Show breakdown by category
    categories: dict[str, int] = {}
    for skill in index["skills"]:
        cat = skill.get("category", "uncategorized")
        categories[cat] = categories.get(cat, 0) + 1

    print("  By category:")
    for cat, count in sorted(categories.items()):
        print(f"    {cat}: {count}")

    # Show skills with/without triggers
    with_explicit = sum(1 for s in index["skills"] if s.get("triggers", [None])[0] != s["name"])
    print(f"  With explicit triggers: {with_explicit}")
    print(f"  With auto-generated triggers: {len(index['skills']) - with_explicit}")

    # Return warning exit code if there were issues
    if warnings:
        print(f"\nCompleted with {len(warnings)} warning(s)", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
