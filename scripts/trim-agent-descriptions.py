#!/usr/bin/env python3
"""
Trim agent description fields for progressive disclosure.

Strips verbose <example> blocks from agent YAML frontmatter descriptions,
keeping at most 1 short inline example. The /do router uses INDEX.json and
routing-tables.md for routing decisions, making the 3-4 full examples
redundant in every conversation's system prompt.

Usage:
    python3 scripts/trim-agent-descriptions.py [--dry-run] [--agent NAME]

Options:
    --dry-run   Show changes without modifying files
    --agent     Process only the named agent (e.g., --agent golang-general-engineer)
"""

import argparse
import re
import sys
from pathlib import Path


def trim_description(description: str) -> tuple[str, dict]:
    """Trim a description field, removing <example> blocks.

    Returns (trimmed_description, stats_dict).
    """
    stats = {
        "examples_found": 0,
        "examples_removed": 0,
        "lines_before": len(description.splitlines()),
        "lines_after": 0,
    }

    # Count examples
    examples = list(re.finditer(
        r"<example>\s*\n(.*?)</example>",
        description,
        re.DOTALL,
    ))
    stats["examples_found"] = len(examples)

    if not examples:
        stats["lines_after"] = stats["lines_before"]
        return description, stats

    # Extract the first example's user/assistant lines for the short inline example
    first_example = examples[0].group(1)
    user_match = re.search(r'user:\s*"([^"]+)"', first_example)
    assistant_match = re.search(r'assistant:\s*"([^"]+)"', first_example)

    # Build inline example from first example
    inline_example = ""
    if user_match:
        user_text = user_match.group(1)
        # Truncate very long user quotes
        if len(user_text) > 120:
            user_text = user_text[:117] + "..."
        inline_example = f'Example: "{user_text}"'
        if assistant_match:
            assistant_text = assistant_match.group(1)
            # Truncate long assistant text
            if len(assistant_text) > 120:
                assistant_text = assistant_text[:117] + "..."

    # Find where the examples section starts (the "Examples:" line or first <example>)
    examples_header_match = re.search(r"\n\s*Examples:\s*\n", description)
    if examples_header_match:
        # Cut from "Examples:" header onward
        before_examples = description[: examples_header_match.start()]
    else:
        # Cut from first <example> tag
        before_examples = description[: examples[0].start()]

    # Clean up trailing whitespace
    before_examples = before_examples.rstrip()

    # Build trimmed description
    if inline_example:
        trimmed = f"{before_examples}\n\n  {inline_example}\n"
    else:
        trimmed = f"{before_examples}\n"

    stats["examples_removed"] = len(examples)
    stats["lines_after"] = len(trimmed.splitlines())

    return trimmed, stats


def process_agent_file(filepath: Path, dry_run: bool = False) -> dict | None:
    """Process a single agent file, trimming its description field.

    Returns stats dict or None if no changes needed.
    """
    content = filepath.read_text(encoding="utf-8")

    # Extract frontmatter
    fm_match = re.match(r"^(---\n)(.*?)(\n---)", content, re.DOTALL)
    if not fm_match:
        return None

    frontmatter = fm_match.group(2)
    after_frontmatter = content[fm_match.end():]

    # Find description field in frontmatter
    # Description starts with "description: |" or "description:" and continues
    # with indented lines until the next non-indented field
    desc_match = re.search(
        r"(description:\s*\|?\n)((?:\s{2,}.+\n?)*)",
        frontmatter,
    )
    if not desc_match:
        return None

    desc_header = desc_match.group(1)
    desc_body = desc_match.group(2)

    # Check if there are examples to trim
    if "<example>" not in desc_body:
        return None

    trimmed_body, stats = trim_description(desc_body)

    if stats["examples_removed"] == 0:
        return None

    # Rebuild frontmatter with trimmed description
    new_frontmatter = (
        frontmatter[: desc_match.start()]
        + desc_header
        + trimmed_body
        + frontmatter[desc_match.end():]
    )

    new_content = f"---\n{new_frontmatter}\n---{after_frontmatter}"

    stats["file"] = filepath.name
    stats["saved_lines"] = stats["lines_before"] - stats["lines_after"]

    if not dry_run:
        filepath.write_text(new_content, encoding="utf-8")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Trim agent description <example> blocks")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying files")
    parser.add_argument("--agent", type=str, help="Process only this agent name")
    args = parser.parse_args()

    agents_dir = Path(__file__).parent.parent / "agents"
    if not agents_dir.exists():
        print(f"Error: agents directory not found at {agents_dir}", file=sys.stderr)
        sys.exit(1)

    if args.agent:
        files = [agents_dir / f"{args.agent}.md"]
        if not files[0].exists():
            print(f"Error: agent file not found: {files[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        files = sorted(agents_dir.glob("*.md"))
        # Exclude INDEX files
        files = [f for f in files if not f.name.startswith("INDEX")]

    total_saved = 0
    total_trimmed = 0
    results = []

    for filepath in files:
        stats = process_agent_file(filepath, dry_run=args.dry_run)
        if stats:
            results.append(stats)
            total_saved += stats["saved_lines"]
            total_trimmed += 1

    # Report
    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{mode}Agent Description Trimming Report")
    print("=" * 60)

    for r in results:
        print(f"  {r['file']}: {r['lines_before']} → {r['lines_after']} lines "
              f"(-{r['saved_lines']}) [{r['examples_found']} examples → 1 inline]")

    print(f"\n{mode}Summary:")
    print(f"  Agents processed: {len(files)}")
    print(f"  Agents trimmed:   {total_trimmed}")
    print(f"  Agents skipped:   {len(files) - total_trimmed}")
    print(f"  Total lines saved: {total_saved}")
    print(f"  Estimated token savings: ~{total_saved * 4} tokens per conversation")

    if args.dry_run and total_trimmed > 0:
        print(f"\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
