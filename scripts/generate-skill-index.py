#!/usr/bin/env python3
"""
Generate skill routing index from YAML frontmatter.

Reads skills/*/SKILL.md, extracts routing metadata
from YAML frontmatter, and generates a dict-keyed index file:
  - skills/INDEX.json   (skills only, v2.0)

Usage:
    python scripts/generate-skill-index.py

Output:
    skills/INDEX.json    - Skill routing index for /do router


Exit codes:
    0 - Success
    1 - Fatal error (directory not found, write failed)
    2 - Trigger collisions detected among force-routed entries
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Phase header regex: matches "## Phase 1:" or "### Phase 1:", "### Phase 0.5:", "### Phase 4b:", etc.
# Captures the NAME part after the colon, stopping before parenthetical or em-dash suffixes.
PHASE_HEADER_RE = re.compile(r"^##+ Phase [\d]+[a-z.]?[\d]*:\s*(.+?)(?:\s*\(|\s*--|\s*\u2014|$)")


def extract_frontmatter(content: str) -> tuple[dict | None, bool]:
    """Extract YAML frontmatter from markdown content.

    Attempts YAML parsing first, then falls back to regex extraction
    for key fields (name, description, version, user-invocable, routing,
    agent, model) when YAML parsing fails due to malformed or edge-case
    frontmatter.

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
    frontmatter: dict = {}

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

    # Top-level agent field
    agent_match = re.search(r"^agent:\s*(.+)$", yaml_content, re.MULTILINE)
    if agent_match:
        frontmatter["agent"] = agent_match.group(1).strip()

    # Top-level model field
    model_match = re.search(r"^model:\s*(.+)$", yaml_content, re.MULTILINE)
    if model_match:
        frontmatter["model"] = model_match.group(1).strip()

    # Parse nested routing section structure:
    #   routing:
    #     triggers:
    #       - "trigger1"
    #       - trigger2
    #     category: category-name
    #     force_route: true
    #     pairs_with:
    #       - agent-name
    routing_match = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_match:
        routing_content = routing_match.group(1)
        routing: dict = {}

        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if triggers_match:
            triggers = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', triggers_match.group(1))
            routing["triggers"] = [t.strip() for t in triggers]

        category_match = re.search(r"category:\s*(.+)$", routing_content, re.MULTILINE)
        if category_match:
            routing["category"] = category_match.group(1).strip()

        force_route_match = re.search(r"force_route:\s*(.+)$", routing_content, re.MULTILINE)
        if force_route_match:
            val = force_route_match.group(1).strip().lower()
            routing["force_route"] = val == "true"

        pairs_match = re.search(r"pairs_with:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if pairs_match:
            pairs = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', pairs_match.group(1))
            routing["pairs_with"] = [p.strip() for p in pairs]

        # Also handle inline empty list: pairs_with: []
        pairs_empty_match = re.search(r"pairs_with:\s*\[\]", routing_content)
        if pairs_empty_match and "pairs_with" not in routing:
            routing["pairs_with"] = []

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


def extract_phases(content: str) -> list[str]:
    """Extract phase names from pipeline SKILL.md body.

    Looks for ### Phase N: NAME headers and extracts the name part,
    uppercased. Handles variants like Phase 0.5, Phase 4b, Phase 2a.
    Strips parenthetical and em-dash suffixes from phase names.

    Args:
        content: Full SKILL.md file content.

    Returns:
        List of phase names in document order (e.g., ["CLASSIFY", "STAGE", "REVIEW"]).
    """
    phases = []
    for line in content.splitlines():
        m = PHASE_HEADER_RE.match(line)
        if m:
            phase_name = m.group(1).strip().upper()
            # Remove trailing whitespace artifacts
            phase_name = phase_name.strip()
            if phase_name:
                phases.append(phase_name)
    return phases


def build_entry(
    frontmatter: dict,
    skill_dir: Path,
    dir_prefix: str,
    content: str | None = None,
    is_pipeline: bool = False,
) -> dict:
    """Build a single index entry from frontmatter and optional content.

    Args:
        frontmatter: Parsed YAML frontmatter dict.
        skill_dir: Directory containing the SKILL.md file.
        dir_prefix: Path prefix for file field (e.g., "skills" or "pipelines").
        content: Full SKILL.md content (needed for pipeline phase extraction).
        is_pipeline: Whether this entry is a pipeline (enables phase extraction).

    Returns:
        Dict representing the index entry for this skill/pipeline.
    """
    name = frontmatter.get("name", skill_dir.name)

    entry: dict = {
        "file": f"{dir_prefix}/{skill_dir.name}/SKILL.md",
        "description": extract_short_description(frontmatter.get("description", "")),
    }

    # Triggers: from routing.triggers or auto-generated from name
    routing = frontmatter.get("routing", {})
    if isinstance(routing, dict) and "triggers" in routing:
        entry["triggers"] = routing["triggers"]
    else:
        # Generate triggers from name as fallback
        name_parts = name.replace("-", " ").split()
        stop_words = {"skill", "pipeline", "the", "and", "for", "with"}
        triggers = [p for p in name_parts if len(p) > 2 and p.lower() not in stop_words]
        entry["triggers"] = [name] + triggers

    # Category: from routing.category, omit if not present
    if isinstance(routing, dict) and "category" in routing:
        entry["category"] = routing["category"]

    # Force route: from routing.force_route, only include when true
    if isinstance(routing, dict) and routing.get("force_route") is True:
        entry["force_route"] = True

    # User invocable: normalize kebab-case to snake_case, default false
    user_invocable = frontmatter.get("user-invocable", False)
    entry["user_invocable"] = bool(user_invocable)

    # Version: from frontmatter, omit if not present
    if "version" in frontmatter:
        entry["version"] = frontmatter["version"]

    # Phases: pipelines only, extracted from body content
    if is_pipeline and content:
        phases = extract_phases(content)
        if phases:
            entry["phases"] = phases

    # Pairs with: from routing.pairs_with, omit if not present
    if isinstance(routing, dict) and "pairs_with" in routing:
        entry["pairs_with"] = routing["pairs_with"]

    # Agent: top-level frontmatter field, omit if not present
    if "agent" in frontmatter:
        entry["agent"] = frontmatter["agent"]

    # Model: top-level frontmatter field, omit if not present
    if "model" in frontmatter:
        entry["model"] = frontmatter["model"]

    return entry


def generate_index(
    source_dir: Path,
    dir_prefix: str,
    collection_key: str,
    is_pipeline: bool = False,
) -> tuple[dict, list[str]]:
    """Generate a dict-keyed routing index from all SKILL.md files in a directory.

    Args:
        source_dir: Directory to scan for subdirectories containing SKILL.md.
        dir_prefix: Path prefix for file field (e.g., "skills" or "pipelines").
        collection_key: Top-level key name in the index (e.g., "skills" or "pipelines").
        is_pipeline: Whether entries are pipelines (enables phase extraction).

    Returns:
        tuple: (index dict with version/generated/generated_by/collection,
                list of warning messages)
    """
    index: dict = {
        "version": "2.0",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/generate-skill-index.py",
        collection_key: {},
    }
    warnings: list[str] = []

    for skill_dir in sorted(source_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
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

        promoted_to = frontmatter.get("promoted_to")
        if promoted_to:
            print(f"  [skip] {name} promoted to {promoted_to}")
            continue

        entry = build_entry(
            frontmatter=frontmatter,
            skill_dir=skill_dir,
            dir_prefix=dir_prefix,
            content=content if is_pipeline else None,
            is_pipeline=is_pipeline,
        )
        index[collection_key][name] = entry

    return index, warnings


def check_trigger_collisions(
    skills_index: dict,
) -> list[str]:
    """Check for trigger collisions among force-routed entries.

    Scans all entries where force_route is true, and reports any
    trigger phrase that appears in more than one force-routed skill.

    Args:
        skills_index: The skills index dict (keyed under "skills").

    Returns:
        List of collision warning strings (empty if no collisions).
    """
    # Build map: trigger -> list of entry names that claim it
    trigger_owners: dict[str, list[str]] = {}

    for name, entry in skills_index.get("skills", {}).items():
        if not entry.get("force_route"):
            continue
        for trigger in entry.get("triggers", []):
            trigger_lower = trigger.lower()
            trigger_owners.setdefault(trigger_lower, []).append(name)

    collisions = []
    for trigger, owners in sorted(trigger_owners.items()):
        if len(owners) > 1:
            collisions.append(f'  Trigger collision: "{trigger}" claimed by: {", ".join(owners)}')

    return collisions


def write_index(index: dict, output_path: Path) -> bool:
    """Write an index dict to a JSON file.

    Args:
        index: The index dict to serialize.
        output_path: File path to write to.

    Returns:
        True on success, False on error (error printed to stderr).
    """
    try:
        output_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        return True
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}", file=sys.stderr)
        return False
    except OSError as e:
        print(f"Error: Failed to write index file: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Main entry point."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    skills_dir = repo_root / "skills"

    if not skills_dir.exists():
        print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
        return 1

    # Generate skills index
    skills_index, skills_warnings = generate_index(
        source_dir=skills_dir,
        dir_prefix="skills",
        collection_key="skills",
        is_pipeline=False,
    )

    # Report warnings if any
    if skills_warnings:
        print("Warnings during index generation:", file=sys.stderr)
        for warning in skills_warnings:
            print(warning, file=sys.stderr)

    # Validate index has content before writing
    if not skills_index["skills"]:
        print("Error: No skills found. Index file not written.", file=sys.stderr)
        return 1

    # Write skills/INDEX.json
    skills_index_path = skills_dir / "INDEX.json"
    if not write_index(skills_index, skills_index_path):
        return 1

    # Check for trigger collisions among force-routed entries
    collisions = check_trigger_collisions(skills_index)
    if collisions:
        print("\nTrigger collisions detected (force-routed entries):", file=sys.stderr)
        for collision in collisions:
            print(collision, file=sys.stderr)

    # Summary (to stdout)
    skills_count = len(skills_index["skills"])

    print(f"Generated {skills_index_path}")
    print(f"  Skills: {skills_count}")

    # Show skills breakdown by category
    skill_categories: dict[str, int] = {}
    for entry in skills_index["skills"].values():
        cat = entry.get("category", "uncategorized")
        skill_categories[cat] = skill_categories.get(cat, 0) + 1
    if skill_categories:
        print("  By category:")
        for cat, count in sorted(skill_categories.items()):
            print(f"    {cat}: {count}")

    # Trigger stats
    all_named = list(skills_index["skills"].items())
    with_explicit = sum(1 for name, e in all_named if (e.get("triggers") or [name])[0] != name)
    force_routed = sum(1 for _, e in all_named if e.get("force_route"))
    print(f"\nWith explicit triggers: {with_explicit}")
    print(f"Force-routed: {force_routed}")

    if collisions:
        print(f"\nCompleted with {len(collisions)} trigger collision(s)", file=sys.stderr)
        return 2

    # Return warning exit code if there were parse issues
    if skills_warnings:
        print(f"\nCompleted with {len(skills_warnings)} warning(s)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
