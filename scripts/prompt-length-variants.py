#!/usr/bin/env python3
"""
Prompt length variant generator for ADR-177.

Creates shortened variants of skill SKILL.md files for A/B testing
prompt length impact on quality and token cost.

Variants:
  full    — original SKILL.md unchanged
  half    — strip example blocks, collapse tables, remove anti-pattern sections
  quarter — headings + first paragraph after each heading only

Usage:
    python3 scripts/prompt-length-variants.py --skill go-patterns --variant half
    python3 scripts/prompt-length-variants.py --skill voice-writer --variant quarter
    python3 scripts/prompt-length-variants.py --skill do --variant full --skills-dir skills/
"""

import argparse
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return repository root (two levels up from this script).

    Returns:
        Path to repository root.
    """
    return Path(__file__).resolve().parent.parent


def _load_skill(skill_name: str, skills_dir: Path) -> str:
    """Read SKILL.md for the given skill name.

    Args:
        skill_name: Name of the skill directory under skills_dir.
        skills_dir: Base skills directory.

    Returns:
        Raw SKILL.md content.

    Raises:
        FileNotFoundError: If SKILL.md does not exist.
    """
    skill_file = skills_dir / skill_name / "SKILL.md"
    if not skill_file.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_file}")
    return skill_file.read_text(encoding="utf-8")


def _strip_example_blocks(text: str) -> str:
    """Remove fenced code blocks that follow 'Example:' or 'EXAMPLE:' lines.

    Removes the 'Example:' / 'EXAMPLE:' label line and the code block that
    immediately follows it (including the block itself).

    Args:
        text: Input markdown text.

    Returns:
        Text with example blocks removed.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line is an Example: label
        stripped = line.strip()
        if re.match(r"^(Example|EXAMPLE)\s*:", stripped):
            # Skip the label line itself
            i += 1
            # Skip any blank lines between label and code fence
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            # If next non-blank line is a code fence, consume the whole block
            if i < len(lines) and lines[i].strip().startswith("```"):
                fence_marker = lines[i].strip()[:3]  # ``` or ```python etc.
                i += 1  # skip opening fence
                while i < len(lines):
                    if lines[i].strip().startswith(fence_marker) and lines[i].strip() in (
                        fence_marker,
                        "```",
                    ):
                        i += 1  # skip closing fence
                        break
                    i += 1
            # else: label had no code block; we already skipped the label
        else:
            result.append(line)
            i += 1
    return "".join(result)


def _collapse_tables(text: str) -> str:
    """Collapse markdown tables to inline key: value lists.

    Converts:
        | Header1 | Header2 |
        |---------|---------|
        | val1    | val2    |

    To:
        - Header1: val1 | Header2: val2

    Args:
        text: Input markdown text.

    Returns:
        Text with tables collapsed to inline lists.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # Detect start of a table (line with at least one |)
        if _is_table_row(line):
            # Collect all consecutive table lines
            table_lines = []
            while i < len(lines) and _is_table_row(lines[i]):
                table_lines.append(lines[i])
                i += 1

            headers: list[str] = []
            data_rows: list[list[str]] = []

            for tline in table_lines:
                cells = [c.strip() for c in tline.strip().strip("|").split("|")]
                # Skip separator rows (e.g., |---|---|)
                if all(re.match(r"^[-:]+$", c) for c in cells if c):
                    continue
                if not headers:
                    headers = cells
                else:
                    data_rows.append(cells)

            for row in data_rows:
                parts = []
                for j, cell in enumerate(row):
                    header = headers[j] if j < len(headers) else f"col{j + 1}"
                    if cell:
                        parts.append(f"{header}: {cell}")
                if parts:
                    result.append("- " + " | ".join(parts) + "\n")
        else:
            result.append(line)
            i += 1

    return "".join(result)


def _is_table_row(line: str) -> bool:
    """Return True if line looks like a markdown table row.

    Args:
        line: A single line of text.

    Returns:
        True if line contains at least two pipe characters.
    """
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _remove_antipattern_sections(text: str) -> str:
    """Remove markdown sections whose heading contains 'Anti-Pattern' or 'anti-pattern'.

    A section extends from its heading to (but not including) the next heading
    of equal or lesser depth.

    Args:
        text: Input markdown text.

    Returns:
        Text with anti-pattern sections removed.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    skip_until_depth: int | None = None

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_match:
            depth = len(heading_match.group(1))
            title = heading_match.group(2)
            if skip_until_depth is not None:
                if depth <= skip_until_depth:
                    # Leaving the anti-pattern section; stop skipping
                    skip_until_depth = None
                    # Check if this new heading is itself an anti-pattern
                    if re.search(r"anti.?pattern", title, re.IGNORECASE):
                        skip_until_depth = depth
                        continue
                    result.append(line)
                    continue
                else:
                    # Still inside; skip sub-headings too
                    continue
            # Not currently skipping — check if this heading triggers skip
            if re.search(r"anti.?pattern", title, re.IGNORECASE):
                skip_until_depth = depth
                continue
            result.append(line)
        else:
            if skip_until_depth is not None:
                continue
            result.append(line)

    return "".join(result)


def _generate_half(original: str) -> str:
    """Generate the 'half' variant of a SKILL.md.

    Strips example blocks, collapses tables, and removes anti-pattern sections.

    Args:
        original: Raw SKILL.md content.

    Returns:
        Reduced markdown content.
    """
    text = _strip_example_blocks(original)
    text = _collapse_tables(text)
    text = _remove_antipattern_sections(text)
    return text


def _generate_quarter(original: str) -> str:
    """Generate the 'quarter' variant of a SKILL.md.

    Keeps only headings and the first paragraph (text until first blank line
    that follows at least one content line) after each heading. Lines
    containing 'Output:', 'Format:', or 'Phase' are always kept regardless
    of position.

    Args:
        original: Raw SKILL.md content.

    Returns:
        Sparse markdown with headings and first paragraphs only.
    """
    lines = original.splitlines(keepends=True)
    result: list[str] = []
    # in_first_paragraph: True while we are consuming the first paragraph
    # after a heading (blank lines before any content are skipped).
    in_first_paragraph = False
    # saw_content: True once we have emitted at least one non-blank content
    # line in the current paragraph block.  A blank line only terminates the
    # paragraph once content has been seen.
    saw_content = False

    for line in lines:
        stripped = line.strip()

        # Always keep lines with key output/format/phase markers.
        # Do NOT short-circuit heading detection — check headings first.
        is_heading = bool(re.match(r"^#{1,6}\s+", line))
        is_key_marker = bool(re.search(r"\b(Output:|Format:|Phase)", line))

        # Headings: always keep, (re)start first-paragraph mode.
        if is_heading:
            result.append(line)
            in_first_paragraph = True
            saw_content = False
            continue

        # Key markers are always emitted.
        if is_key_marker:
            result.append(line)
            # If we are in first-paragraph mode, count this as content seen
            # so a subsequent blank line will terminate the paragraph.
            if in_first_paragraph:
                saw_content = True
            continue

        if in_first_paragraph:
            if stripped == "":
                if saw_content:
                    # Blank line after content → end of first paragraph.
                    result.append(line)
                    in_first_paragraph = False
                # Blank line before any content (between heading and paragraph)
                # is emitted once to preserve spacing, but paragraph mode stays on.
                else:
                    result.append(line)
            else:
                # Non-blank content: first paragraph material.
                result.append(line)
                saw_content = True
        # else: outside paragraph mode — skip unless heading or key marker.

    return "".join(result)


def _token_count(text: str) -> int:
    """Approximate token count using word splitting.

    Args:
        text: Input text.

    Returns:
        Word count as token approximation.
    """
    return len(text.split())


def main(argv: list[str] | None = None) -> int:
    """Run the prompt length variant generator.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(description="Generate shortened variants of SKILL.md files.")
    parser.add_argument(
        "--skill",
        required=True,
        metavar="NAME",
        help="Skill name (reads skills/{NAME}/SKILL.md).",
    )
    parser.add_argument(
        "--variant",
        choices=["full", "half", "quarter"],
        required=True,
        help="Variant to generate: full, half, or quarter.",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Override skills directory (default: skills/ in repo root).",
    )
    args = parser.parse_args(argv)

    skills_dir: Path = args.skills_dir if args.skills_dir is not None else _repo_root() / "skills"

    try:
        original = _load_skill(args.skill, skills_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.variant == "full":
        variant_text = original
    elif args.variant == "half":
        variant_text = _generate_half(original)
    else:  # quarter
        variant_text = _generate_quarter(original)

    original_tokens = _token_count(original)
    variant_tokens = _token_count(variant_text)
    reduction_pct = round((1 - variant_tokens / original_tokens) * 100, 1) if original_tokens > 0 else 0.0

    print(variant_text, end="")
    print(
        f"Variant: {args.variant} | Original: {original_tokens} tokens "
        f"| Variant: {variant_tokens} tokens | Reduction: {reduction_pct}%",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
