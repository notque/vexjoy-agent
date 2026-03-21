#!/usr/bin/env python3
"""
ADR Status Report — scan adr/ directory and output a status summary.

Parses each ADR markdown file for title, status, date, and number,
then outputs a formatted table grouped by status or validates structure.

Usage:
    python3 scripts/adr-status.py status              # Table grouped by status
    python3 scripts/adr-status.py status --json        # JSON output
    python3 scripts/adr-status.py check                # Validate required sections
    python3 scripts/adr-status.py check --json         # Validation results as JSON
    python3 scripts/adr-status.py --dir /path/to/adrs  # Override ADR directory

Exit codes:
    0 = success (status), all valid (check)
    1 = validation warnings found (check)
    2 = usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class AdrRecord:
    """Parsed metadata from a single ADR file."""

    filename: str
    number: int | None
    title: str
    status: str
    date: str
    path: Path


@dataclass
class AdrWarning:
    """Validation warning for a single ADR file."""

    filename: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches numbered ADR titles like "# ADR-012: Dangerous Command Guard"
_NUMBERED_TITLE_RE = re.compile(r"^#\s+ADR-?(\d+):\s*(.+)$")

# Matches unnumbered ADR titles like "# ADR: LLM-Powered Report Classification"
_UNNUMBERED_TITLE_RE = re.compile(r"^#\s+ADR:\s*(.+)$")

# Matches a generic top-level heading as fallback
_GENERIC_TITLE_RE = re.compile(r"^#\s+(.+)$")

# Matches number prefix in filenames like "012-dangerous-command-guard.md"
_FILENAME_NUMBER_RE = re.compile(r"^(\d+)-")

# Required sections for the check subcommand
_REQUIRED_SECTIONS = ["Status", "Date", "Context"]


def _extract_section_value(content: str, heading: str) -> str | None:
    """Extract the first non-blank line after a ## heading.

    Args:
        content: Full markdown file content.
        heading: Section heading name (e.g. "Status", "Date").

    Returns:
        First non-blank line after the heading, or None if heading not found.
    """
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return None

    # Get text after the heading line
    rest = content[match.end() :]
    for line in rest.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped

    return None


def _parse_title(first_line: str) -> tuple[int | None, str]:
    """Parse the title from the first line of an ADR file.

    Args:
        first_line: First line of the ADR markdown file.

    Returns:
        Tuple of (number or None, title string).
    """
    # Try numbered: "# ADR-012: Title"
    m = _NUMBERED_TITLE_RE.match(first_line.strip())
    if m:
        return int(m.group(1)), m.group(2).strip()

    # Try unnumbered: "# ADR: Title"
    m = _UNNUMBERED_TITLE_RE.match(first_line.strip())
    if m:
        return None, m.group(1).strip()

    # Fallback: generic heading
    m = _GENERIC_TITLE_RE.match(first_line.strip())
    if m:
        return None, m.group(1).strip()

    return None, first_line.strip()


def _extract_number_from_filename(filename: str) -> int | None:
    """Extract numeric prefix from ADR filename.

    Args:
        filename: Filename like "012-dangerous-command-guard.md".

    Returns:
        Integer prefix (e.g. 12) or None for unnumbered files.
    """
    m = _FILENAME_NUMBER_RE.match(filename)
    if m:
        return int(m.group(1))
    return None


def parse_adr(path: Path) -> AdrRecord:
    """Parse an ADR markdown file into an AdrRecord.

    Args:
        path: Path to the ADR .md file.

    Returns:
        Populated AdrRecord with parsed metadata.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Title from first line
    first_line = lines[0] if lines else ""
    title_number, title = _parse_title(first_line)

    # Number: prefer filename prefix, fall back to title
    file_number = _extract_number_from_filename(path.name)
    number = file_number if file_number is not None else title_number

    # Status
    status_raw = _extract_section_value(content, "Status")
    status = status_raw if status_raw else ""

    # Date
    date_raw = _extract_section_value(content, "Date")
    date = date_raw if date_raw else ""

    return AdrRecord(
        filename=path.name,
        number=number,
        title=title,
        status=status,
        date=date,
        path=path,
    )


def validate_adr(path: Path) -> AdrWarning:
    """Validate an ADR file for required sections.

    Args:
        path: Path to the ADR .md file.

    Returns:
        AdrWarning with any issues found.
    """
    content = path.read_text(encoding="utf-8")
    result = AdrWarning(filename=path.name)

    for section in _REQUIRED_SECTIONS:
        pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
        if not pattern.search(content):
            result.warnings.append(f"Missing ## {section} heading")

    # Check if Status has a value (not just heading present)
    status_val = _extract_section_value(content, "Status")
    has_status_heading = bool(re.search(r"^##\s+Status\s*$", content, re.MULTILINE))
    if has_status_heading and not status_val:
        result.warnings.append("Status field is empty/blank")

    return result


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def _sort_key(record: AdrRecord) -> tuple[int, int, str]:
    """Sort key: numbered ADRs first (by number), then unnumbered (alphabetically).

    Returns:
        Tuple of (0 for numbered / 1 for unnumbered, number or 0, filename).
    """
    if record.number is not None:
        return (0, record.number, "")
    return (1, 0, record.filename)


def _normalize_status(raw_status: str) -> str:
    """Normalize status to a canonical display form.

    Takes the first word of the status line (before any dash or extra text)
    and title-cases it. E.g. "Implemented — details..." -> "Implemented",
    "Proposed" -> "Proposed".

    Args:
        raw_status: Raw status string from the ADR.

    Returns:
        Normalized status string for grouping.
    """
    if not raw_status:
        return "Unknown"
    # Take text before em-dash (U+2014), en-dash (U+2013), or hyphen followed by space
    first_part = re.split(r"\s*[\u2014\u2013-]\s+", raw_status, maxsplit=1)[0]
    # Take just the first word for grouping
    first_word = first_part.strip().split()[0] if first_part.strip() else "Unknown"
    # Capitalize first letter, keep rest
    return first_word[0].upper() + first_word[1:] if first_word else "Unknown"


# ---------------------------------------------------------------------------
# Status group ordering
# ---------------------------------------------------------------------------

# Display order for status groups; unlisted statuses sort after these
_STATUS_ORDER = ["Proposed", "Accepted", "Implemented", "Superseded", "Deprecated", "Rejected"]


def _status_sort_key(status: str) -> tuple[int, str]:
    """Sort key for status groups, following conventional ADR lifecycle order."""
    try:
        return (0, str(_STATUS_ORDER.index(status)).zfill(3))
    except ValueError:
        return (1, status.lower())


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------


def cmd_status(adr_dir: Path, *, as_json: bool) -> int:
    """Scan ADR directory and output a status report.

    Args:
        adr_dir: Path to the ADR directory.
        as_json: If True, output JSON instead of formatted table.

    Returns:
        Exit code (always 0).
    """
    if not adr_dir.is_dir():
        print(f"error: ADR directory not found: {adr_dir}", file=sys.stderr)
        return 2

    md_files = sorted(adr_dir.glob("*.md"))
    records = [parse_adr(f) for f in md_files]

    if as_json:
        output = [
            {
                "filename": r.filename,
                "number": r.number,
                "title": r.title,
                "status": r.status,
                "status_group": _normalize_status(r.status),
                "date": r.date if r.date else None,
            }
            for r in records
        ]
        print(json.dumps(output, indent=2))
        return 0

    # Group by normalized status
    groups: dict[str, list[AdrRecord]] = defaultdict(list)
    for record in records:
        normalized = _normalize_status(record.status)
        groups[normalized].append(record)

    # Sort within each group
    for group_records in groups.values():
        group_records.sort(key=_sort_key)

    # Print header
    print("ADR Status Report")
    print("=================")

    if not groups:
        print("\nNo ADRs found.")
        return 0

    # Print groups in lifecycle order
    sorted_statuses = sorted(groups.keys(), key=_status_sort_key)
    for status in sorted_statuses:
        group_records = groups[status]
        print(f"\n{status} ({len(group_records)})")
        for record in group_records:
            num_str = f"{record.number:03d}" if record.number is not None else "---"
            date_str = record.date if record.date else "(no date)"
            print(f"  {num_str}  {record.title:<45s} {date_str}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: check
# ---------------------------------------------------------------------------


def cmd_check(adr_dir: Path, *, as_json: bool) -> int:
    """Validate all ADR files for required sections.

    Args:
        adr_dir: Path to the ADR directory.
        as_json: If True, output JSON instead of human-readable warnings.

    Returns:
        Exit code 0 if all pass, 1 if any warnings.
    """
    if not adr_dir.is_dir():
        print(f"error: ADR directory not found: {adr_dir}", file=sys.stderr)
        return 2

    md_files = sorted(adr_dir.glob("*.md"))
    results = [validate_adr(f) for f in md_files]
    has_warnings = any(r.warnings for r in results)

    if as_json:
        output = [{"filename": r.filename, "warnings": r.warnings, "valid": len(r.warnings) == 0} for r in results]
        print(json.dumps(output, indent=2))
        return 1 if has_warnings else 0

    if not results:
        print("No ADRs found.")
        return 0

    warn_count = 0
    for result in results:
        if result.warnings:
            for warning in result.warnings:
                print(f"  WARN  {result.filename}: {warning}")
                warn_count += 1

    if warn_count:
        print(f"\n{warn_count} warning(s) in {sum(1 for r in results if r.warnings)} file(s)")
        return 1

    print(f"All {len(results)} ADRs pass validation.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="adr-status.py",
        description="Scan adr/ directory and output a status report of Architecture Decision Records.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="ADR directory path (default: adr/ relative to repo root)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON instead of formatted table",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Add shared flags to each subparser so they work in both positions
    # (e.g. both "adr-status.py --json status" and "adr-status.py status --json").
    # Use store_const with default=None so subparser defaults don't clobber
    # values already set by the parent parser.
    for p in [
        subparsers.add_parser("status", help="Show ADR status report grouped by status (default)"),
        subparsers.add_parser("check", help="Validate ADR files for required sections"),
    ]:
        p.add_argument(
            "--json", action="store_const", const=True, default=None, dest="sub_json", help=argparse.SUPPRESS
        )
        p.add_argument("--dir", type=Path, default=None, dest="sub_dir", metavar="PATH", help=argparse.SUPPRESS)

    return parser


def main() -> int:
    """Entry point -- parse args and dispatch to subcommand handler."""
    parser = _build_parser()
    args = parser.parse_args()

    # Default subcommand is 'status'
    command = args.command or "status"

    # Merge flags: subparser value wins if set, otherwise parent value
    as_json = getattr(args, "sub_json", None) or args.as_json
    dir_override = getattr(args, "sub_dir", None) or args.dir

    # Resolve ADR directory
    if dir_override is not None:
        adr_dir = dir_override.resolve()
    else:
        adr_dir = Path(__file__).resolve().parent.parent / "adr"

    dispatch = {
        "status": lambda: cmd_status(adr_dir, as_json=as_json),
        "check": lambda: cmd_check(adr_dir, as_json=as_json),
    }

    handler = dispatch.get(command)
    if handler is None:
        parser.print_help(sys.stderr)
        return 2

    return handler()


if __name__ == "__main__":
    sys.exit(main())
