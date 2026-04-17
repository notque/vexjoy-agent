#!/usr/bin/env python3
"""Detect unpaired anti-pattern blocks across skills and agents.

An anti-pattern block is "unpaired" when it contains a negative description
(What it looks like / Why wrong) but has no matching positive counterpart
("Do instead" / "Correct approach" / "Instead" variant).

An annotated exception `<!-- no-pair-required: reason -->` suppresses the finding
for that block.

Usage:
    python3 scripts/detect-unpaired-antipatterns.py
    python3 scripts/detect-unpaired-antipatterns.py --json
    python3 scripts/detect-unpaired-antipatterns.py --output artifacts/joy-check-sweep-backlog.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_PATTERNS = [
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
    "agents/**/*.md",
    "agents/**/references/*.md",
]

# Files that are known non-content (index, template metadata)
SKIP_FILES = {"INDEX.json", "README.md"}

# Headings or bold markers that signal the start of an anti-pattern block
ANTIPATTERN_START = re.compile(
    r"(?:^#{1,4}\s+.*(?:anti.?pattern|bad\s+practice|wrong\s+way|avoid|don.t\s+do).*$"
    r"|^\*\*(?:Anti.?[Pp]attern|What it looks like|Why wrong)\*\*"
    r"|^##\s+.*(?:Anti.?[Pp]attern).*$"
    r"|^-\s+\*\*(?:Anti.?[Pp]attern|What it looks like|Why wrong)\*\*)",
    re.IGNORECASE | re.MULTILINE,
)

# Markers that indicate a positive counterpart is present
DO_INSTEAD_MARKERS = re.compile(
    r"(?:\*\*(?:do\s+instead|correct\s+approach|instead|do\s+this|right\s+way"
    r"|preferred|recommended|use\s+instead|better\s+approach|solution|right)\*\*"
    r"|^###?\s+.*(?:correct|preferred|instead|do\s+instead).*$"
    r"|\u2705\s+(?:do\s+instead|correct|instead|right)"
    r"|Do\s+instead:"
    r"|Correct\s+approach:"
    r"|Instead:"
    r"|\*\*Right\*\*:"
    r"|Right:)",
    re.IGNORECASE | re.MULTILINE,
)

# Annotated exception suppresses the finding
EXCEPTION_ANNOTATION = re.compile(r"<!--\s*no-pair-required\s*:", re.IGNORECASE)

# Frontmatter name field for domain hint
FRONTMATTER_NAME = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


def extract_domain_hint(file_path: Path, content: str) -> str:
    """Infer domain hint from frontmatter name or file path."""
    name_match = FRONTMATTER_NAME.search(content[:500])
    if name_match:
        name = name_match.group(1).strip().strip('"').strip("'")
        parts = name.split("-")
        if parts:
            return parts[0]

    parts = file_path.parts
    for i, part in enumerate(parts):
        if part in ("skills", "agents") and i + 1 < len(parts):
            return parts[i + 1]

    return file_path.stem


def split_into_blocks(content: str) -> list[tuple[int, str]]:
    """Split content into heading-delimited blocks. Returns (start_line, block_text) pairs.

    Tracks fenced code block state so that `#` comment lines inside code fences
    are never treated as heading boundaries (Issue 2 fix).
    """
    lines = content.splitlines()
    blocks: list[tuple[int, str]] = []
    current_start = 0
    current_lines: list[str] = []
    in_fence = False

    for i, line in enumerate(lines):
        # Toggle fence state on triple-backtick lines; do NOT split inside a fence.
        if line.startswith("```"):
            in_fence = not in_fence

        if not in_fence and re.match(r"^#{1,4}\s+", line) and current_lines:
            blocks.append((current_start + 1, "\n".join(current_lines)))
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append((current_start + 1, "\n".join(current_lines)))

    return blocks


def block_is_antipattern(block_text: str) -> bool:
    """Return True if this block describes an anti-pattern."""
    return bool(ANTIPATTERN_START.search(block_text))


def block_has_do_instead(block_text: str) -> bool:
    """Return True if this block contains a positive counterpart."""
    return bool(DO_INSTEAD_MARKERS.search(block_text))


def block_has_exception(block_text: str) -> bool:
    """Return True if this block has a no-pair-required annotation."""
    return bool(EXCEPTION_ANNOTATION.search(block_text))


@dataclass
class UnpairedFinding:
    file: str
    line_range: list[int]
    block_text: str
    domain_hint: str


def scan_file(file_path: Path) -> list[UnpairedFinding]:
    """Scan a single file for unpaired anti-pattern blocks."""
    if file_path.name in SKIP_FILES:
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    # Skip pure YAML/JSON files
    if not content.strip().startswith("#") and not content.strip().startswith("---"):
        stripped = content.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return []

    domain_hint = extract_domain_hint(file_path, content)
    findings: list[UnpairedFinding] = []

    # Determine the start line of the first non-frontmatter block for Issue 3.
    # Frontmatter is a leading `---` fence; skip past it and any blank lines
    # to find the first real content line.
    raw_lines = content.splitlines()
    first_content_line = 1
    if raw_lines and raw_lines[0].strip() == "---":
        for idx in range(1, len(raw_lines)):
            if raw_lines[idx].strip() == "---":
                # Advance past the closing --- and any blank lines that follow.
                close_idx = idx
                skip = close_idx + 1
                while skip < len(raw_lines) and not raw_lines[skip].strip():
                    skip += 1
                first_content_line = skip + 1  # convert to 1-indexed
                break

    blocks = split_into_blocks(content)
    lines = content.splitlines()

    # Marker for Issue 3: secondary anti-pattern indicators inside a block body
    SECONDARY_AP_MARKER = re.compile(
        r"(?:what it looks like|why wrong|anti.?pattern)",
        re.IGNORECASE,
    )

    for block_index, (start_line, block_text) in enumerate(blocks):
        if not block_is_antipattern(block_text):
            continue
        if block_has_do_instead(block_text):
            continue
        if block_has_exception(block_text):
            continue

        block_lines = block_text.splitlines()

        # Issue 1: skip blocks that are a heading with no substantive body content.
        # A block whose body (lines after the first) has zero non-blank, non-heading
        # lines is a structural TOC header, not an actual anti-pattern description.
        body_lines = [ln for ln in block_lines[1:] if ln.strip()]
        if len(body_lines) == 0:
            continue

        # Issue 3: skip first-block H1 document intro headers.
        # An H1 heading (single `#`) at the top of the file that lacks secondary
        # anti-pattern markers is a document title, not a pattern description.
        is_first_block = start_line <= first_content_line
        heading_line = block_lines[0] if block_lines else ""
        is_h1 = bool(re.match(r"^#\s+", heading_line)) and not re.match(r"^#{2,}", heading_line)
        if is_first_block and is_h1:
            body_text = "\n".join(block_lines[1:])
            if not SECONDARY_AP_MARKER.search(body_text):
                continue

        end_line = start_line + len(block_lines) - 1

        # Truncate block text for JSON output (avoid huge entries)
        truncated = block_text[:500] + ("..." if len(block_text) > 500 else "")

        findings.append(
            UnpairedFinding(
                file=str(file_path.relative_to(REPO_ROOT)),
                line_range=[start_line, end_line],
                block_text=truncated,
                domain_hint=domain_hint,
            )
        )

    return findings


def collect_scan_targets() -> list[Path]:
    """Expand glob patterns to file paths, deduplicating."""
    seen: set[Path] = set()
    targets: list[Path] = []

    for pattern in SCAN_PATTERNS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                targets.append(path)

    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect unpaired anti-pattern blocks across skills and agents")
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output JSON to stdout",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write JSON output to this file (implies --json)",
    )
    args = parser.parse_args()

    targets = collect_scan_targets()
    all_findings: list[UnpairedFinding] = []

    for path in targets:
        all_findings.extend(scan_file(path))

    output_data = {
        "total": len(all_findings),
        "findings": [asdict(f) for f in all_findings],
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output_data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(all_findings)} finding(s) to {args.output}", file=sys.stderr)
    elif args.json_output:
        print(json.dumps(output_data, indent=2))
    else:
        # Human-readable summary
        if not all_findings:
            print("No unpaired anti-patterns found.")
            return

        print(f"Found {len(all_findings)} unpaired anti-pattern block(s):\n")
        for f in all_findings:
            print(f"  {f.file}:{f.line_range[0]}-{f.line_range[1]}  domain={f.domain_hint}")

        domains: dict[str, int] = {}
        for f in all_findings:
            domains[f.domain_hint] = domains.get(f.domain_hint, 0) + 1
        print("\nBy domain:")
        for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
            print(f"  {domain}: {count}")


if __name__ == "__main__":
    main()
