#!/usr/bin/env python3
"""
Initialize a new KB topic directory scaffold under research/{topic}/.

Creates the standard directory structure and starter files for a knowledge base topic.

Usage:
    kb-init.py --topic TOPIC
    kb-init.py --topic TOPIC --description "What this topic covers"
    kb-init.py --topic TOPIC --force   # overwrite existing kb.yaml and _index.md

Exit codes:
    0 = success (created or already exists with --force)
    1 = error (write failure, invalid topic name)
    2 = already exists (without --force)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# --- Constants ---

_VALID_TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# --- Data model ---


@dataclass
class ScaffoldResult:
    """Result from initializing a KB topic."""

    topic: str
    topic_dir: Path
    created_dirs: list[Path]
    created_files: list[Path]
    skipped_files: list[Path]


# --- Template builders ---


def _kb_yaml(topic: str, description: str, created: str) -> str:
    """Build default kb.yaml content.

    Args:
        topic: Topic slug.
        description: Human-readable description.
        created: ISO 8601 creation timestamp.

    Returns:
        YAML string for kb.yaml.
    """
    return f"""topic: {topic}
description: "{description}"
created: "{created}"
compile:
  schedule: nightly
  last_run: null
sources:
  types:
    - article
    - paper
    - note
    - image
"""


def _index_md(topic: str) -> str:
    """Build initial wiki/_index.md content.

    Args:
        topic: Topic slug (used for frontmatter and display name).

    Returns:
        Markdown string for _index.md.
    """
    display_name = topic.replace("-", " ").title()
    return f"""---
topic: {topic}
last_compiled: null
entry_count: 0
---
# {display_name} Knowledge Base

_No entries yet. Run `/kb compile {topic}` after adding sources to `raw/`._
"""


# --- Core logic ---


def _validate_topic(topic: str) -> str | None:
    """Validate topic name; return error message or None if valid.

    Args:
        topic: Topic name to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not topic:
        return "Topic name cannot be empty"
    if not _VALID_TOPIC_RE.match(topic):
        return (
            f"Invalid topic name '{topic}': must be lowercase alphanumeric with hyphens "
            "(e.g. 'llm-patterns', 'async-python')"
        )
    if len(topic) > 60:
        return f"Topic name too long ({len(topic)} chars, max 60)"
    return None


def init_topic(
    topic: str,
    description: str,
    output_root: Path,
    force: bool = False,
) -> ScaffoldResult:
    """Initialize KB topic directory structure.

    Creates:
        research/{topic}/
          raw/
            images/
          wiki/
            _index.md
            concepts/
            sources/
            queries/
          kb.yaml

    Args:
        topic: Topic slug (lowercase, hyphenated).
        description: Human-readable description for kb.yaml.
        output_root: Root research/ directory.
        force: If True, overwrite existing kb.yaml and _index.md.

    Returns:
        ScaffoldResult describing what was created/skipped.

    Raises:
        SystemExit: On validation or write errors.
    """
    err = _validate_topic(topic)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    topic_dir = output_root / topic
    created_dirs: list[Path] = []
    created_files: list[Path] = []
    skipped_files: list[Path] = []

    # Define required directories
    dirs_to_create = [
        topic_dir / "raw" / "images",
        topic_dir / "wiki" / "concepts",
        topic_dir / "wiki" / "sources",
        topic_dir / "wiki" / "queries",
    ]

    for d in dirs_to_create:
        if not d.exists():
            try:
                d.mkdir(parents=True, exist_ok=True)
                created_dirs.append(d)
            except OSError as e:
                print(f"ERROR: Failed to create {d}: {e}", file=sys.stderr)
                sys.exit(1)

    # Write kb.yaml
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kb_yaml_path = topic_dir / "kb.yaml"
    if not kb_yaml_path.exists() or force:
        try:
            kb_yaml_path.write_text(_kb_yaml(topic, description, created), encoding="utf-8")
            created_files.append(kb_yaml_path)
        except OSError as e:
            print(f"ERROR: Failed to write {kb_yaml_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        skipped_files.append(kb_yaml_path)

    # Write wiki/_index.md
    index_path = topic_dir / "wiki" / "_index.md"
    if not index_path.exists() or force:
        try:
            index_path.write_text(_index_md(topic), encoding="utf-8")
            created_files.append(index_path)
        except OSError as e:
            print(f"ERROR: Failed to write {index_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        skipped_files.append(index_path)

    return ScaffoldResult(
        topic=topic,
        topic_dir=topic_dir,
        created_dirs=created_dirs,
        created_files=created_files,
        skipped_files=skipped_files,
    )


# --- CLI ---


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize a KB topic directory scaffold under research/{topic}/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --topic llm-patterns
  %(prog)s --topic llm-patterns --description "Patterns for LLM prompt engineering"
  %(prog)s --topic agents --force   # re-initialize existing topic
        """,
    )
    parser.add_argument("--topic", required=True, help="Topic slug (lowercase, hyphenated, e.g. llm-patterns)")
    parser.add_argument(
        "--description",
        default="",
        help="Short description of the topic (written to kb.yaml)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing kb.yaml and _index.md if they already exist",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Root research directory (default: research/ relative to repo root)",
    )

    args = parser.parse_args()

    # Resolve output root
    if args.output_root:
        output_root = Path(args.output_root)
    else:
        script_dir = Path(__file__).parent
        output_root = script_dir.parent / "research"

    # Check for existing topic (non-force)
    topic_dir = output_root / args.topic
    already_exists = topic_dir.exists()

    if already_exists and not args.force:
        # Partially idempotent: create any missing dirs but don't overwrite files
        result = init_topic(args.topic, args.description, output_root, force=False)
        if result.skipped_files:
            print(
                f"Topic '{args.topic}' already exists at {result.topic_dir}",
                file=sys.stderr,
            )
            print(
                "  Skipped: " + ", ".join(str(f.name) for f in result.skipped_files),
                file=sys.stderr,
            )
            print("  Use --force to overwrite existing config files.", file=sys.stderr)

            if result.created_dirs:
                print("  Created missing dirs:", file=sys.stderr)
                for d in result.created_dirs:
                    print(f"    {d}", file=sys.stderr)
            return 2
    else:
        result = init_topic(args.topic, args.description, output_root, force=args.force)

    # Report
    print(f"Initialized KB topic: {result.topic}")
    print(f"  Location: {result.topic_dir}")
    if result.created_dirs:
        print(f"  Created {len(result.created_dirs)} director(y|ies)")
    if result.created_files:
        for f in result.created_files:
            print(f"  Created: {f.relative_to(output_root)}")
    if result.skipped_files:
        for f in result.skipped_files:
            print(f"  Skipped (exists): {f.relative_to(output_root)}")

    print(f"\nNext steps:")
    print(f"  1. Add sources: kb-clip.py --topic {result.topic} --url URL")
    print(f"  2. Compile wiki: /kb compile {result.topic}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
