#!/usr/bin/env python3
"""
Validate YAML frontmatter in skill SKILL.md files.

Checks structural correctness, required fields, naming consistency,
and common mistakes (top-level pairs_with, force_routing typo).

Usage:
    python3 scripts/validate-skill-frontmatter.py                       # all skills
    python3 scripts/validate-skill-frontmatter.py skills/foo/SKILL.md   # one file
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
    rel = str(filepath)

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"{rel}: Cannot read file: {e}"]

    # Extract frontmatter block
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return [f"{rel}: No YAML frontmatter found (missing --- delimiters)"]

    yaml_content = match.group(1)

    # Parse YAML
    try:
        fm = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return [f"{rel}: YAML parse error: {e}"]

    if not isinstance(fm, dict):
        return [f"{rel}: Frontmatter is not a mapping (got {type(fm).__name__})"]

    # Derive expected name from directory
    dir_name = filepath.parent.name

    # Check: name exists and matches directory
    if "name" not in fm:
        errors.append(f"{rel}: Missing 'name' field")
    elif fm["name"] != dir_name:
        errors.append(f"{rel}: Name mismatch: '{fm['name']}' vs directory '{dir_name}'")

    # Check: description exists and is non-empty
    desc = fm.get("description")
    if not desc or (isinstance(desc, str) and not desc.strip()):
        errors.append(f"{rel}: Missing or empty description")

    # Check: routing section exists and is a dict
    routing = fm.get("routing")
    if routing is None:
        errors.append(f"{rel}: Missing routing section")
    elif not isinstance(routing, dict):
        errors.append(f"{rel}: routing must be a mapping, got {type(routing).__name__}")
    else:
        # Check: routing.triggers is non-empty list
        triggers = routing.get("triggers")
        if triggers is None:
            errors.append(f"{rel}: Missing routing.triggers")
        elif not isinstance(triggers, list):
            errors.append(f"{rel}: routing.triggers must be a list, got {type(triggers).__name__}")
        elif len(triggers) == 0:
            errors.append(f"{rel}: routing.triggers is empty (need at least one trigger)")

        # Check: routing.category exists
        if "category" not in routing:
            errors.append(f"{rel}: Missing routing.category")

    # Check: pairs_with NOT at top level (must be under routing:)
    if "pairs_with" in fm:
        errors.append(f"{rel}: pairs_with at top level; must be under routing:")

    # Check: no force_routing key anywhere (should be force_route)
    if _find_key_recursive(fm, "force_routing"):
        errors.append(f"{rel}: Found 'force_routing'; use 'force_route'")

    # Strict mode: check optional fields
    if strict:
        if "version" not in fm:
            errors.append(f"{rel}: [strict] Missing 'version' field")
        if "allowed-tools" not in fm:
            errors.append(f"{rel}: [strict] Missing 'allowed-tools' field")

    return errors


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate YAML frontmatter in skill SKILL.md files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific SKILL.md files to validate. If omitted, validates all skills.",
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
        # Auto-discover: find all skills/*/SKILL.md
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        skills_dir = repo_root / "skills"
        if not skills_dir.exists():
            print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
            return 2
        targets = sorted(skills_dir.glob("*/SKILL.md"))
        if not targets:
            print("Error: No SKILL.md files found", file=sys.stderr)
            return 2

    # Validate each file
    all_errors: list[str] = []
    valid_count = 0
    for filepath in targets:
        errors = validate_skill(filepath, strict=args.strict)
        if errors:
            all_errors.extend(errors)
        else:
            valid_count += 1

    # Report results
    total = len(targets)
    if all_errors:
        print(f"Skill frontmatter validation: {len(all_errors)} error(s) in {total - valid_count} file(s)")
        for err in all_errors:
            print(f"  ERROR: {err}")
        return 1

    print(f"Skill frontmatter validation: {total} file(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
