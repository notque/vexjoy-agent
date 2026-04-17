#!/usr/bin/env python3
"""Validate that all pairs_with entries in agent frontmatter resolve to real
skills, pipelines, or other agents.

Exit 0 if every reference resolves; exit 1 if any are broken.
Uses only Python stdlib — no external dependencies.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from difflib import get_close_matches
from pathlib import Path


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Extract YAML frontmatter from a Markdown file as a simple dict.

    Only handles the subset of YAML we actually need:
      - scalar values
      - lists (both inline [...] and block "- item" style)
      - one level of nested mappings (e.g. routing:)
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    lines = match.group(1).splitlines()
    result: dict[str, object] = {}
    current_key: str | None = None
    current_map: dict[str, object] | None = None
    current_list_key: str | None = None
    current_list: list[str] | None = None

    for line in lines:
        stripped = line.rstrip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Detect indentation level
        indent = len(line) - len(line.lstrip())

        # Top-level key (no indent)
        if indent == 0 and ":" in stripped:
            # Flush any pending list
            if current_list_key is not None and current_list is not None:
                if current_map is not None:
                    current_map[current_list_key] = current_list
                else:
                    result[current_list_key] = current_list
                current_list_key = None
                current_list = None
            # Flush any pending map
            if current_key and current_map is not None:
                result[current_key] = current_map
                current_map = None

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if not value:
                # Could be start of a nested map or block list
                current_key = key
                current_map = {}
            elif value.startswith("["):
                # Inline list
                items = _parse_inline_list(value)
                result[key] = items
                current_key = None
                current_map = None
            else:
                result[key] = value
                current_key = None
                current_map = None

        # Indented content (inside a nested map)
        elif indent > 0:
            # Block list item
            list_match = re.match(r"^\s+-\s+(.*)", stripped)
            if list_match:
                item = list_match.group(1).strip()
                if current_list is None:
                    current_list = []
                    # Figure out which key this list belongs to
                    # It's either the last key we saw in the nested map, or current_key
                    current_list_key = current_list_key  # keep if already set
                current_list.append(item)
                continue

            # Nested key: value
            if ":" in stripped:
                # Flush pending list
                if current_list_key is not None and current_list is not None:
                    if current_map is not None:
                        current_map[current_list_key] = current_list
                    current_list_key = None
                    current_list = None

                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()

                if current_map is not None:
                    if not value:
                        # Next lines might be a list under this key
                        current_list_key = key
                        current_list = None  # will be created when first item seen
                    elif value.startswith("["):
                        current_map[key] = _parse_inline_list(value)
                    else:
                        current_map[key] = value

    # Flush remaining state
    if current_list_key is not None and current_list is not None:
        if current_map is not None:
            current_map[current_list_key] = current_list
        elif current_key:
            result[current_list_key] = current_list

    if current_key and current_map is not None:
        result[current_key] = current_map

    return result


def _parse_inline_list(value: str) -> list[str]:
    """Parse a YAML inline list like [a, b, c]."""
    inner = value.strip("[] ")
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def collect_valid_names(skills_dir: Path, pipelines_dir: Path, agents_dir: Path) -> set[str]:
    """Collect all valid skill, pipeline, and agent names."""
    valid: set[str] = set()

    # Skills: each subdirectory with a SKILL.md
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                valid.add(entry.name)

    # Pipelines: each subdirectory with a SKILL.md
    if pipelines_dir.is_dir():
        for entry in sorted(pipelines_dir.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                valid.add(entry.name)

    # Agents: *.md files (strip .md suffix)
    if agents_dir.is_dir():
        for entry in sorted(agents_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".md" and entry.name not in ("README.md", "INDEX.json"):
                valid.add(entry.stem)

    return valid


def suggest_fix(broken_ref: str, valid_names: set[str]) -> str:
    """Suggest a replacement for a broken reference."""
    matches = get_close_matches(broken_ref, sorted(valid_names), n=1, cutoff=0.6)
    if matches:
        return f"rename -> {matches[0]}"
    return "remove (no close match found)"


def validate_agents(agents_dir: Path, skills_dir: Path, pipelines_dir: Path) -> list[tuple[str, str, str]]:
    """Validate all pairs_with references. Returns list of (agent_file, broken_ref, suggestion)."""
    valid_names = collect_valid_names(skills_dir, pipelines_dir, agents_dir)
    broken: list[tuple[str, str, str]] = []

    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        sys.exit(2)

    for agent_file in sorted(agents_dir.iterdir()):
        if not agent_file.is_file() or agent_file.suffix != ".md":
            continue
        if agent_file.name in ("README.md", "README.txt", "INDEX.json"):
            continue

        text = agent_file.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        if not frontmatter:
            continue

        routing = frontmatter.get("routing")
        if not isinstance(routing, dict):
            continue

        pairs_with = routing.get("pairs_with")
        if not pairs_with:
            continue

        if isinstance(pairs_with, str):
            pairs_with = [pairs_with]
        if not isinstance(pairs_with, list):
            continue

        for ref in pairs_with:
            ref = str(ref).strip()
            if ref and ref not in valid_names:
                suggestion = suggest_fix(ref, valid_names)
                broken.append((agent_file.name, ref, suggestion))

    return broken


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate pairs_with references in agent frontmatter")
    parser.add_argument(
        "--agents-dir",
        default="agents",
        help="Path to the agents directory (default: agents/)",
    )
    parser.add_argument(
        "--skills-dir",
        default="skills",
        help="Path to the skills directory (default: skills/)",
    )
    parser.add_argument(
        "--pipelines-dir",
        default="pipelines",
        help="Path to the pipelines directory (default: skills/workflow/references/)",
    )

    args = parser.parse_args()

    agents_dir = Path(args.agents_dir).resolve()
    skills_dir = Path(args.skills_dir).resolve()
    pipelines_dir = Path(args.pipelines_dir).resolve()

    broken = validate_agents(agents_dir, skills_dir, pipelines_dir)

    if not broken:
        print("All pairs_with references are valid.")
        sys.exit(0)

    # Print results table
    max_agent = max(len(b[0]) for b in broken)
    max_ref = max(len(b[1]) for b in broken)
    max_sug = max(len(b[2]) for b in broken)

    header = f"{'Agent File':<{max_agent}}  {'Broken Reference':<{max_ref}}  {'Suggested Fix':<{max_sug}}"
    print(header)
    print("-" * len(header))

    for agent_file, ref, suggestion in broken:
        print(f"{agent_file:<{max_agent}}  {ref:<{max_ref}}  {suggestion:<{max_sug}}")

    print(f"\nTotal broken references: {len(broken)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
