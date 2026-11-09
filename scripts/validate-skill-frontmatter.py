#!/usr/bin/env python3
"""
Validate YAML frontmatter in skill SKILL.md files and agent description size.

Skills: structural correctness, required fields, naming consistency,
and common mistakes (top-level pairs_with, force_routing typo).

Agents (agents/*.md): the description is at most 300 bytes and holds no
<example> block. Claude Code loads every agent description into each session,
so a long one costs tokens on every turn.

Usage:
    python3 scripts/validate-skill-frontmatter.py                       # all skills and agents
    python3 scripts/validate-skill-frontmatter.py skills/foo/SKILL.md   # one skill
    python3 scripts/validate-skill-frontmatter.py agents/foo.md         # one agent
    python3 scripts/validate-skill-frontmatter.py --strict              # also check optional fields

Exit codes:
    0 - All validations passed
    1 - One or more validation errors found
    2 - Script error (bad arguments, missing directory)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# Byte cap on an agent description. Every repo agent fits (largest: 233 bytes).
AGENT_DESCRIPTION_MAX_BYTES = 300


def _find_key_recursive(data: object, key: str) -> bool:
    """Recursively check if a key exists anywhere in a nested dict."""
    if isinstance(data, dict):
        if key in data:
            return True
        return any(_find_key_recursive(v, key) for v in data.values())
    if isinstance(data, list):
        return any(_find_key_recursive(item, key) for item in data)
    return False


def validate_skill(filepath: Path, strict: bool = False) -> list[str]:
    """Validate a single SKILL.md file's frontmatter.

    Args:
        filepath: Path to a SKILL.md file.
        strict: When True, also check optional fields (version, allowed-tools).

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []
    display_path = str(filepath)

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"{display_path}: Cannot read file: {e}"]

    # Extract frontmatter block
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return [f"{display_path}: No YAML frontmatter found (missing --- delimiters)"]

    yaml_content = match.group(1)

    # Parse YAML
    try:
        fm = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return [f"{display_path}: YAML parse error: {e}"]

    if not isinstance(fm, dict):
        return [f"{display_path}: Frontmatter is not a mapping (got {type(fm).__name__})"]

    # Derive expected name from directory
    dir_name = filepath.parent.name

    # Check: name exists and matches directory
    if "name" not in fm:
        errors.append(f"{display_path}: Missing 'name' field")
    elif fm["name"] != dir_name:
        errors.append(f"{display_path}: Name mismatch: '{fm['name']}' vs directory '{dir_name}'")

    # Check: description exists and is non-empty
    desc = fm.get("description")
    if not desc or (isinstance(desc, str) and not desc.strip()):
        errors.append(f"{display_path}: Missing or empty description")

    # Check: routing section exists and is a dict
    routing = fm.get("routing")
    if routing is None:
        errors.append(f"{display_path}: Missing routing section")
    elif not isinstance(routing, dict):
        errors.append(f"{display_path}: routing must be a mapping, got {type(routing).__name__}")
    else:
        # Check: routing.triggers is non-empty list
        triggers = routing.get("triggers")
        if triggers is None:
            errors.append(f"{display_path}: Missing routing.triggers")
        elif not isinstance(triggers, list):
            errors.append(f"{display_path}: routing.triggers must be a list, got {type(triggers).__name__}")
        elif len(triggers) == 0:
            errors.append(f"{display_path}: routing.triggers is empty (need at least one trigger)")

        # Check: non-string trigger items
        if isinstance(triggers, list) and any(not isinstance(t, str) for t in triggers):
            errors.append(f"{display_path}: routing.triggers contains non-string items")

        # Check: routing.category exists
        if "category" not in routing:
            errors.append(f"{display_path}: Missing routing.category")

    # Check: pairs_with NOT at top level (must be under routing:)
    if "pairs_with" in fm:
        errors.append(f"{display_path}: pairs_with at top level; must be under routing:")

    # Check: no force_routing key anywhere (should be force_route)
    if _find_key_recursive(fm, "force_routing"):
        errors.append(f"{display_path}: Found 'force_routing'; use 'force_route'")

    # Strict mode: check optional fields
    if strict:
        if "version" not in fm:
            errors.append(f"{display_path}: [strict] Missing 'version' field")
        if "allowed-tools" not in fm:
            errors.append(f"{display_path}: [strict] Missing 'allowed-tools' field")

    return errors


def validate_agent(filepath: Path) -> list[str]:
    """Validate the description size of one agent file.

    A file with no frontmatter is not an agent (for example a shared
    instructions file) and passes.

    Args:
        filepath: Path to an agents/*.md file.

    Returns:
        List of error strings. Empty list means valid.
    """
    display_path = str(filepath)
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"{display_path}: Cannot read file: {e}"]

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return []
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return [f"{display_path}: YAML parse error: {e}"]
    if not isinstance(fm, dict):
        return [f"{display_path}: Frontmatter is not a mapping (got {type(fm).__name__})"]

    errors: list[str] = []
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return [f"{display_path}: Missing or empty description"]
    size = len(desc.encode("utf-8"))
    if size > AGENT_DESCRIPTION_MAX_BYTES:
        errors.append(
            f"{display_path}: description is {size} bytes; the cap is {AGENT_DESCRIPTION_MAX_BYTES}. "
            "Move detail into the agent body"
        )
    if re.search(r"<example\b", desc, re.IGNORECASE):
        errors.append(f"{display_path}: description holds an <example> block; move examples into the agent body")
    return errors


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate skill SKILL.md frontmatter and agent description size.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="SKILL.md or agent .md files to validate. If omitted, validates all skills and agents.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Also check optional fields (version, allowed-tools).",
    )
    args = parser.parse_args()

    # Determine which files to validate
    if args.files:
        targets = [Path(f) for f in args.files]
        for t in targets:
            if not t.exists():
                print(f"Error: File not found: {t}", file=sys.stderr)
                return 2
    else:
        # Auto-discover: find all skills/**/SKILL.md (flat and nested)
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        skills_dir = repo_root / "skills"
        if not skills_dir.exists():
            print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
            return 2
        targets = sorted(skills_dir.glob("**/SKILL.md"))
        if not targets:
            print("Error: No SKILL.md files found", file=sys.stderr)
            return 2
        targets += sorted((repo_root / "agents").glob("*.md"))

    # Validate each file
    all_errors: list[str] = []
    valid_count = 0
    for filepath in targets:
        if filepath.name == "SKILL.md":
            errors = validate_skill(filepath, strict=args.strict)
        else:
            errors = validate_agent(filepath)
        if errors:
            all_errors.extend(errors)
        else:
            valid_count += 1

    # Report results
    total = len(targets)
    if all_errors:
        print(f"Frontmatter validation: {len(all_errors)} error(s) in {total - valid_count} file(s)")
        for err in all_errors:
            print(f"  ERROR: {err}")
        return 1

    print(f"Frontmatter validation: {total} file(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
