#!/usr/bin/env python3
"""Validate that a reference decomposition preserved all content from the original SKILL.md.

Usage:
    python3 scripts/validate-decomposition.py \\
        --before /tmp/original-skill.md \\
        --after skills/foo/SKILL.md \\
        --refs skills/foo/references/

Optional flags:
    --json              Machine-readable JSON output
    --verbose           Detailed per-check reporting
    --new-refs f1,f2    Comma-separated list of new reference filenames (for route
                        completeness check). If omitted, all files in --refs are
                        treated as potentially new.

Exit codes:
    0  PASS — all checks passed
    1  FAIL — one or more checks failed
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class CheckFailure:
    """A single check failure with location details."""

    category: str
    check: str
    detail: str
    location: str = ""


@dataclass
class ValidationResult:
    """Aggregated result from all validation categories."""

    failures: list[CheckFailure] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0

    @property
    def ok(self) -> bool:
        return len(self.failures) == 0


# ---------------------------------------------------------------------------
# Content extraction helpers
# ---------------------------------------------------------------------------


def extract_code_blocks(content: str) -> list[str]:
    """Extract all fenced code block contents (between ``` delimiters)."""
    blocks: list[str] = []
    in_block = False
    current: list[str] = []
    for line in content.split("\n"):
        if line.strip().startswith("```"):
            if in_block:
                blocks.append("\n".join(current))
                current = []
            in_block = not in_block
            continue
        if in_block:
            current.append(line)
    return blocks


def extract_tables(content: str) -> list[str]:
    """Extract all markdown tables (header + separator + rows).

    A table is identified by:
    1. A header row containing pipe characters
    2. A separator row with dashes (|---|)
    3. One or more data rows
    """
    tables: list[str] = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for a line that looks like a table header row
        if "|" in line and line.strip().startswith("|"):
            # Check if next line is a separator
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if "|" in next_line and re.match(r"\|[\s\-:|]+\|", next_line.strip()):
                    # Found a table — collect all consecutive pipe rows
                    table_lines = [line, next_line]
                    j = i + 2
                    while j < len(lines) and "|" in lines[j] and lines[j].strip().startswith("|"):
                        table_lines.append(lines[j])
                        j += 1
                    tables.append("\n".join(table_lines))
                    i = j
                    continue
        i += 1
    return tables


def extract_headings(content: str) -> list[tuple[int, str]]:
    """Extract all markdown headings as (level, text) tuples."""
    headings: list[tuple[int, str]] = []
    for line in content.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append((level, text))
    return headings


def extract_section_content(content: str, heading_text: str) -> str:
    """Return the body text beneath a given heading (until the next same-or-higher heading)."""
    lines = content.split("\n")
    in_section = False
    heading_level = 0
    body: list[str] = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if text == heading_text:
                in_section = True
                heading_level = level
                continue
            if in_section and level <= heading_level:
                break
        if in_section:
            body.append(line)

    return "\n".join(body)


# ---------------------------------------------------------------------------
# Fuzzy normalization
# ---------------------------------------------------------------------------


def normalize_block(text: str) -> str:
    """Normalize a content block for fuzzy comparison.

    Strips leading/trailing whitespace from each line, collapses multiple
    spaces to single space, and removes empty lines at start/end.
    """
    lines = [re.sub(r"  +", " ", line.strip()) for line in text.split("\n")]
    # Drop leading and trailing empty lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def block_exists_in(block: str, haystack: str) -> bool:
    """Return True if normalized block appears anywhere in normalized haystack."""
    norm_block = normalize_block(block)
    if not norm_block:
        return True  # empty block is trivially present
    norm_haystack = normalize_block(haystack)
    return norm_block in norm_haystack


# ---------------------------------------------------------------------------
# Category 1: Content Preservation
# ---------------------------------------------------------------------------


def check_content_preservation(
    before_content: str,
    combined_after: str,
    verbose: bool,
) -> list[CheckFailure]:
    """Verify all code blocks, tables, and headings from the original are present after."""
    failures: list[CheckFailure] = []

    # --- Code blocks ---
    original_blocks = extract_code_blocks(before_content)
    missing_blocks: list[tuple[int, str]] = []
    for idx, block in enumerate(original_blocks):
        if not block_exists_in(block, combined_after):
            missing_blocks.append((idx + 1, block))

    if verbose:
        print(f"  [code-blocks] {len(original_blocks) - len(missing_blocks)}/{len(original_blocks)} code blocks found")

    for idx, block in missing_blocks:
        preview = block.strip()[:80].replace("\n", " ")
        failures.append(
            CheckFailure(
                category="content-preservation",
                check="code-block-missing",
                detail=f"Code block #{idx} not found in after-state: {preview!r}...",
            )
        )

    # --- Tables ---
    original_tables = extract_tables(before_content)
    missing_tables: list[tuple[int, str]] = []
    for idx, table in enumerate(original_tables):
        # For tables we check just the header + separator to allow minor cell reflows
        header_rows = "\n".join(table.split("\n")[:2])
        if not block_exists_in(header_rows, combined_after):
            missing_tables.append((idx + 1, table))

    if verbose:
        print(f"  [tables] {len(original_tables) - len(missing_tables)}/{len(original_tables)} tables found")

    for idx, table in missing_tables:
        preview = table.split("\n")[0][:80]
        failures.append(
            CheckFailure(
                category="content-preservation",
                check="table-missing",
                detail=f"Table #{idx} header not found in after-state: {preview!r}",
            )
        )

    # --- Headings ---
    original_headings = extract_headings(before_content)
    # Skip frontmatter-style headings and very short/generic ones
    SKIP_HEADINGS = {"Instructions", "Overview", "Notes"}
    substantive_headings = [(lvl, text) for lvl, text in original_headings if text not in SKIP_HEADINGS]
    missing_headings: list[tuple[int, str]] = []

    for level, heading_text in substantive_headings:
        # A heading is preserved if its text appears anywhere in the after-state
        # OR if the content beneath it appears (restructuring allowed)
        heading_in_after = f"{'#' * level} {heading_text}" in combined_after or heading_text in combined_after
        if not heading_in_after:
            # Check if content under the heading was migrated
            section_body = extract_section_content(before_content, heading_text)
            if section_body.strip() and not block_exists_in(section_body[:200], combined_after):
                missing_headings.append((level, heading_text))

    if verbose:
        print(
            f"  [headings] {len(substantive_headings) - len(missing_headings)}/{len(substantive_headings)} headings found"
        )

    for level, heading_text in missing_headings:
        failures.append(
            CheckFailure(
                category="content-preservation",
                check="heading-missing",
                detail=f"Heading {'#' * level} {heading_text!r} not found and section content not in after-state",
            )
        )

    return failures


# ---------------------------------------------------------------------------
# Category 2: Route Completeness
# ---------------------------------------------------------------------------

# Matches any pipe-table row that contains a references/*.md path (2 or 3 column).
# We don't require a specific column count — any row with a non-empty first cell
# and a references/ path in any cell qualifies.
_PIPE_ROW_PATTERN = re.compile(r"^\|(.+)\|$")
_REF_PATH_PATTERN = re.compile(r"references/([^)\s|`>]+\.md)")


def find_loading_table_entries(skill_content: str) -> dict[str, str]:
    """Return {filename: row_text} for every loading table entry in SKILL.md.

    Accepts 2-column format (| Signal | references/file.md |) and
    3-column format (| Signal | Description | references/file.md |).
    Skips separator rows (---|---) and header rows with no reference path.
    """
    entries: dict[str, str] = {}
    for line in skill_content.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip separator rows
        if re.match(r"\|[\s\-:|]+\|", stripped):
            continue
        # Look for a references/ path anywhere in this row
        ref_match = _REF_PATH_PATTERN.search(stripped)
        if not ref_match:
            continue
        # Extract first cell as signal — must be non-empty
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        # Skip header rows that say "Signal" / "Load" / "Query" etc.
        if cells[0].lower() in {"signal", "query", "trigger", "keyword", "when", "condition"}:
            continue
        fname = ref_match.group(1)
        entries[fname] = stripped
    return entries


def check_route_completeness(
    new_skill_content: str,
    refs_dir: Path,
    new_ref_names: list[str] | None,
    verbose: bool,
) -> list[CheckFailure]:
    """Verify every new reference file has a loading table entry in the new SKILL.md."""
    failures: list[CheckFailure] = []

    if new_ref_names is not None:
        candidate_names = new_ref_names
    else:
        candidate_names = [f.name for f in refs_dir.glob("*.md")]

    loading_entries = find_loading_table_entries(new_skill_content)

    if verbose:
        print(f"  [route-completeness] Loading table entries found: {sorted(loading_entries.keys())}")
        print(f"  [route-completeness] New reference files to check: {sorted(candidate_names)}")

    for ref_name in sorted(candidate_names):
        if ref_name not in loading_entries:
            failures.append(
                CheckFailure(
                    category="route-completeness",
                    check="missing-loading-table-entry",
                    detail=f"No loading table row found for references/{ref_name} in new SKILL.md",
                    location=str(refs_dir / ref_name),
                )
            )
        else:
            # Verify signal cell is non-empty (already checked above in find_loading_table_entries)
            if verbose:
                print(f"    OK: {ref_name} -> {loading_entries[ref_name][:60]}")

    return failures


# ---------------------------------------------------------------------------
# Category 3: Structure Preservation
# ---------------------------------------------------------------------------


def check_structure_preservation(
    new_skill_content: str,
    new_skill_path: Path,
    verbose: bool,
) -> list[CheckFailure]:
    """Verify the new SKILL.md retains required structural elements."""
    failures: list[CheckFailure] = []

    # --- YAML frontmatter ---
    lines = new_skill_content.split("\n")
    has_frontmatter = False
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                has_frontmatter = True
                break

    if verbose:
        print(f"  [structure] frontmatter: {'present' if has_frontmatter else 'MISSING'}")

    if not has_frontmatter:
        failures.append(
            CheckFailure(
                category="structure-preservation",
                check="missing-frontmatter",
                detail="YAML frontmatter (--- delimiters) not found in new SKILL.md",
                location=str(new_skill_path),
            )
        )

    # --- Phase headings ---
    phase_headings = [line for line in lines if re.match(r"^#{1,4}\s+Phase\s+\d+", line, re.IGNORECASE)]

    if verbose:
        print(f"  [structure] phase headings found: {len(phase_headings)}")

    if not phase_headings:
        failures.append(
            CheckFailure(
                category="structure-preservation",
                check="missing-phase-headings",
                detail="No '### Phase N' style headings found in new SKILL.md",
                location=str(new_skill_path),
            )
        )

    # --- Error handling section ---
    error_heading = any(re.search(r"error", line, re.IGNORECASE) for line in lines if re.match(r"^#{1,6}\s+", line))

    if verbose:
        print(f"  [structure] error handling section: {'present' if error_heading else 'MISSING'}")

    if not error_heading:
        failures.append(
            CheckFailure(
                category="structure-preservation",
                check="missing-error-section",
                detail="No heading containing 'error' (case-insensitive) found in new SKILL.md",
                location=str(new_skill_path),
            )
        )

    return failures


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_text_results(result: ValidationResult, verbose: bool) -> None:
    """Print human-readable validation output."""
    if result.ok:
        print(f"PASS: {result.checks_passed}/{result.checks_run} checks passed, 0 failures")
    else:
        print(f"FAIL: {len(result.failures)} failure(s) across {result.checks_run} checks")
        print()

        by_category: dict[str, list[CheckFailure]] = {}
        for f in result.failures:
            by_category.setdefault(f.category, []).append(f)

        for category, failures in sorted(by_category.items()):
            print(f"  [{category}] {len(failures)} failure(s):")
            for failure in failures:
                loc = f" ({failure.location})" if failure.location else ""
                print(f"    FAIL [{failure.check}]{loc}")
                print(f"         {failure.detail}")


def build_json_results(result: ValidationResult) -> dict:
    """Build JSON-serializable result dict."""
    return {
        "ok": result.ok,
        "checks_run": result.checks_run,
        "checks_passed": result.checks_passed,
        "failures": [
            {
                "category": f.category,
                "check": f.check,
                "detail": f.detail,
                "location": f.location,
            }
            for f in result.failures
        ],
        "exit_code": 0 if result.ok else 1,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for decomposition validation CLI."""
    parser = argparse.ArgumentParser(
        description="Validate that a SKILL.md decomposition preserved all content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--before",
        required=True,
        metavar="FILE",
        help="Path to the original SKILL.md (before decomposition)",
    )
    parser.add_argument(
        "--after",
        required=True,
        metavar="FILE",
        help="Path to the new SKILL.md (after decomposition)",
    )
    parser.add_argument(
        "--refs",
        required=True,
        metavar="DIR",
        help="Path to the references/ directory containing extracted reference files",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Machine-readable JSON output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Detailed per-check reporting",
    )
    parser.add_argument(
        "--new-refs",
        metavar="FILE1,FILE2,...",
        help=(
            "Comma-separated list of new reference filenames (e.g. patterns.md,errors.md). "
            "If omitted, all .md files in --refs are checked for loading table entries."
        ),
    )
    args = parser.parse_args()

    before_path = Path(args.before)
    after_path = Path(args.after)
    refs_dir = Path(args.refs)

    # Validate inputs
    if not before_path.is_file():
        print(f"ERROR: --before file not found: {before_path}", file=sys.stderr)
        sys.exit(1)
    if not after_path.is_file():
        print(f"ERROR: --after file not found: {after_path}", file=sys.stderr)
        sys.exit(1)
    if not refs_dir.is_dir():
        print(f"ERROR: --refs directory not found: {refs_dir}", file=sys.stderr)
        sys.exit(1)

    new_ref_names: list[str] | None = None
    if args.new_refs:
        new_ref_names = [n.strip() for n in args.new_refs.split(",") if n.strip()]

    # Read files
    before_content = before_path.read_text(encoding="utf-8")
    after_content = after_path.read_text(encoding="utf-8")

    ref_contents: dict[str, str] = {}
    for ref_file in sorted(refs_dir.glob("*.md")):
        ref_contents[ref_file.name] = ref_file.read_text(encoding="utf-8")

    # Build combined after-state for content presence checks
    combined_after = after_content + "\n" + "\n".join(ref_contents.values())

    result = ValidationResult()

    # Category 1: Content Preservation
    if args.verbose:
        print("Category 1: Content Preservation")
    cat1_checks = 3  # code blocks, tables, headings
    cat1_failures = check_content_preservation(before_content, combined_after, args.verbose)
    result.checks_run += cat1_checks
    result.checks_passed += cat1_checks - len({f.check for f in cat1_failures})
    result.failures.extend(cat1_failures)

    # Category 2: Route Completeness
    if args.verbose:
        print("Category 2: Route Completeness")
    candidate_count = len(new_ref_names) if new_ref_names is not None else len(ref_contents)
    cat2_failures = check_route_completeness(after_content, refs_dir, new_ref_names, args.verbose)
    result.checks_run += max(candidate_count, 1)
    result.checks_passed += max(candidate_count, 1) - len(cat2_failures)
    result.failures.extend(cat2_failures)

    # Category 3: Structure Preservation
    if args.verbose:
        print("Category 3: Structure Preservation")
    cat3_checks = 3  # frontmatter, phase headings, error section
    cat3_failures = check_structure_preservation(after_content, after_path, args.verbose)
    result.checks_run += cat3_checks
    result.checks_passed += cat3_checks - len(cat3_failures)
    result.failures.extend(cat3_failures)

    # Output
    if args.json_output:
        output = build_json_results(result)
        print(json.dumps(output, indent=2))
        sys.exit(output["exit_code"])
    else:
        print_text_results(result, args.verbose)
        sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
