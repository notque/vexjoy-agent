#!/usr/bin/env python3
"""Validate that all reference file links in agent markdown files exist on disk.

Parses all agents/*.md files, extracts markdown links pointing to references/
paths, and checks that the target files actually exist.  Exits 0 if all
references resolve; exits 1 if any are missing.

Uses only Python stdlib -- no external dependencies.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Matches full markdown links: [label](target)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Matches bare reference paths after markdown link syntax has been removed.
# Captures paths containing "references/" that end in .md
_BARE_REF_RE = re.compile(r"(\S*references/\S+\.md)")


def extract_reference_links(text: str) -> list[str]:
    """Return deduplicated list of reference paths found in *text*.

    Extracts from both ``[text](path)`` markdown links and bare
    ``references/foo.md`` occurrences.  Skips lines that are clearly
    comments (e.g. ``(planned)`` markers) or inline code references
    that aren't actual file links.
    """
    seen: set[str] = set()
    links: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        # Skip lines that mention "(planned)" -- these are aspirational, not real links
        if "(planned)" in stripped:
            continue

        # 1) Extract targets from markdown links [text](target)
        for _label, target in _MD_LINK_RE.findall(line):
            target = target.strip()
            if "references/" not in target:
                continue
            if target not in seen:
                seen.add(target)
                links.append(target)

        # 2) Strip all markdown link syntax to find bare references.
        #    Replace [label](target) with whitespace so bare regex
        #    does not match fragments from inside links.
        bare_line = _MD_LINK_RE.sub(" ", line)

        for bare in _BARE_REF_RE.findall(bare_line):
            bare = bare.strip()
            if bare in seen:
                continue
            # Skip backtick-quoted code references
            if f"`{bare}" in line or f"{bare}`" in line:
                continue
            seen.add(bare)
            links.append(bare)

    return links


def validate_references(
    agents_dir: Path,
) -> tuple[list[tuple[str, str, str]], int]:
    """Validate all reference links in agent markdown files.

    Returns (rows, total_checked) where rows is a list of
    (agent_file, reference_link, status) tuples and total_checked
    is the number of links inspected.
    """
    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        sys.exit(2)

    rows: list[tuple[str, str, str]] = []
    total_checked = 0

    for agent_file in sorted(agents_dir.iterdir()):
        if not agent_file.is_file() or agent_file.suffix != ".md":
            continue
        if agent_file.name in ("README.md", "INDEX.json"):
            continue

        text = agent_file.read_text(encoding="utf-8")
        links = extract_reference_links(text)

        if not links:
            continue

        for link in links:
            total_checked += 1
            # Resolve the link relative to the agent file's parent directory
            resolved = (agent_file.parent / link).resolve()
            status = "OK" if resolved.exists() else "MISSING"
            rows.append((agent_file.name, link, status))

    return rows, total_checked


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate reference file links in agent markdown files"
    )
    parser.add_argument(
        "--agents-dir",
        default="agents",
        help="Path to the agents directory (default: agents/)",
    )
    args = parser.parse_args()

    agents_dir = Path(args.agents_dir).resolve()
    rows, total_checked = validate_references(agents_dir)

    if not rows:
        print("No reference links found in agent files.")
        sys.exit(0)

    missing = [r for r in rows if r[2] == "MISSING"]

    # Print results table
    col_agent = max(len(r[0]) for r in rows)
    col_link = max(len(r[1]) for r in rows)
    col_status = 7  # len("MISSING")

    header = (
        f"{'Agent File':<{col_agent}}  "
        f"{'Reference Link':<{col_link}}  "
        f"{'Status':<{col_status}}"
    )
    print(header)
    print("-" * len(header))

    for agent_file, link, status in rows:
        print(f"{agent_file:<{col_agent}}  {link:<{col_link}}  {status:<{col_status}}")

    print(f"\nChecked {total_checked} reference(s) across {len(set(r[0] for r in rows))} agent(s).")

    if missing:
        print(f"MISSING: {len(missing)} reference(s) not found on disk.")
        sys.exit(1)
    else:
        print("All references exist.")
        sys.exit(0)


if __name__ == "__main__":
    main()
