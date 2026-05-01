#!/usr/bin/env python3
"""Validate review output against JSON Schema.

Parses markdown review output into a structured dict, then validates against
the appropriate JSON Schema for the review type. Supports all 4 review pipeline
formats: systematic, parallel, sapcc-review, sapcc-audit.

Usage:
  python3 scripts/validate-review-output.py --type systematic review-output.md
  python3 scripts/validate-review-output.py --type parallel review-output.md
  python3 scripts/validate-review-output.py --type sapcc-review review-output.md
  python3 scripts/validate-review-output.py --type sapcc-audit review-output.md

  # Validate raw JSON (skip markdown parsing):
  python3 scripts/validate-review-output.py --type systematic --json review-output.json

  # Read from stdin:
  cat review-output.md | python3 scripts/validate-review-output.py --type systematic -

Exit codes:
  0 = valid
  1 = structural errors found
  2 = parse error (couldn't extract structure from markdown)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REVIEW_TYPES = ("systematic", "parallel", "sapcc-review", "sapcc-audit")

SCHEMA_MAP: dict[str, str] = {
    "systematic": "systematic-code-review.schema.json",
    "parallel": "parallel-code-review.schema.json",
    "sapcc-review": "sapcc-review.schema.json",
    "sapcc-audit": "sapcc-audit.schema.json",
}

# Severity heading patterns mapped to normalized keys per review type.
# Each review type uses different severity naming conventions.
SEVERITY_MAP: dict[str, dict[str, str]] = {
    "systematic": {
        "blocking": "blocking",
        "should fix": "should_fix",
        "should-fix": "should_fix",
        "suggestions": "suggestions",
        "suggestion": "suggestions",
    },
    "parallel": {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    },
    "sapcc-review": {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    },
    "sapcc-audit": {
        "must-fix": "must_fix",
        "must fix": "must_fix",
        "should-fix": "should_fix",
        "should fix": "should_fix",
        "nit": "nit",
        "nits": "nit",
    },
}

# Heading patterns that indicate the positives section
POSITIVE_HEADINGS = (
    "what was done well",
    "what's done well",
    "positive notes",
    "positives",
)

# File:line pattern — matches paths like handler.go:42, internal/api/routes.go:123
FILE_LINE_RE = re.compile(r"`?([^\s`]+:\d+)`?")

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "skills" / "shared-patterns" / "schemas"


# ---------------------------------------------------------------------------
# Markdown Parser
# ---------------------------------------------------------------------------


def _heading_level(line: str) -> tuple[int, str] | None:
    """Return (level, text) for a markdown heading line, or None."""
    match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
    if match:
        return len(match.group(1)), match.group(2).strip()
    return None


def _extract_verdict(lines: list[str]) -> str | None:
    """Extract verdict from review output lines.

    Looks for patterns like:
      ## Verdict: APPROVE
      ## VERDICT: REQUEST-CHANGES
      Verdict: BLOCK
      **VERDICT** - rationale
      **BLOCK** - rationale (parallel review)
      ## Verdict\\n<prose paragraph> (sapcc-review/sapcc-audit style)
    """
    for i, line in enumerate(lines):
        stripped = line.strip()

        # "## Verdict: VALUE" or "## VERDICT: VALUE" (with inline value)
        match = re.match(r"^#{1,3}\s+[Vv][Ee][Rr][Dd][Ii][Cc][Tt]:?\s+(.+)$", stripped)
        if match:
            return _clean_verdict(match.group(1))

        # "## Verdict" heading with NO inline value — read next non-empty line
        match = re.match(r"^#{1,3}\s+[Vv][Ee][Rr][Dd][Ii][Cc][Tt]\s*$", stripped)
        if match:
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                # Stop if we hit another heading
                if next_line.startswith("#"):
                    break
                return _clean_verdict_prose(next_line)

        # "Verdict: VALUE" (plain line)
        match = re.match(r"^[Vv]erdict:\s*(.+)$", stripped)
        if match:
            return _clean_verdict(match.group(1))

        # "**VERDICT** - rationale" (parallel review style)
        match = re.match(r"^\*\*([A-Z-]+)\*\*\s*[-—]", stripped)
        if match:
            candidate = match.group(1).strip()
            if candidate in ("BLOCK", "FIX", "APPROVE", "REQUEST-CHANGES", "NEEDS-DISCUSSION"):
                return candidate

    return None


def _clean_verdict(raw: str) -> str:
    """Clean verdict string: strip markdown formatting, extract first word/phrase."""
    # Remove markdown bold
    raw = raw.replace("**", "").strip()
    # Take first token if there's a dash or parenthesis after the verdict
    match = re.match(r"^([A-Z][-A-Z]*)", raw)
    if match:
        return match.group(1)
    return raw.strip()


def _clean_verdict_prose(raw: str) -> str:
    """Extract verdict from a prose paragraph under a ## Verdict heading.

    For SAPCC reviews/audits, the verdict is a full sentence like:
      "Mostly clean codebase with a few type-safety issues..."
      "Needs work before review - 3 must-fix issues found."

    We return the full first sentence as the verdict string, since these
    review types use free-form verdict text (no enum constraint in schema).
    """
    raw = raw.replace("**", "").strip()
    # If it starts with an all-caps keyword, extract that
    match = re.match(r"^(APPROVE|BLOCK|FIX|REQUEST-CHANGES|NEEDS-DISCUSSION)\b", raw)
    if match:
        return match.group(1)
    # Otherwise return the full first sentence (up to period, em-dash, or end)
    match = re.match(r"^(.+?)[.!]\s", raw)
    if match:
        return match.group(1).strip() + "."
    return raw.strip()


def _extract_risk_level(lines: list[str]) -> str | None:
    """Extract risk level for systematic reviews."""
    for line in lines:
        match = re.match(r"^.*[Rr]isk\s+[Ll]evel:\s*(LOW|MEDIUM|HIGH|CRITICAL)", line.strip())
        if match:
            return match.group(1)
    return None


def _extract_summary(lines: list[str]) -> str | None:
    """Extract summary from ## Summary section."""
    in_summary = False
    summary_lines: list[str] = []
    for line in lines:
        heading = _heading_level(line)
        if heading:
            level, text = heading
            if level <= 2 and text.lower().startswith("summary"):
                in_summary = True
                continue
            if in_summary and level <= 2:
                break
        elif in_summary:
            stripped = line.strip()
            if stripped:
                summary_lines.append(stripped)
    return " ".join(summary_lines) if summary_lines else None


def _extract_positives(lines: list[str]) -> list[str]:
    """Extract positives from well-known positive-notes sections."""
    positives: list[str] = []
    in_positives = False
    for line in lines:
        heading = _heading_level(line)
        if heading:
            level, text = heading
            if any(ph in text.lower() for ph in POSITIVE_HEADINGS):
                in_positives = True
                continue
            if in_positives and level <= 2:
                break
        elif in_positives:
            stripped = line.strip()
            # Collect bullet/numbered items
            match = re.match(r"^[-*]\s+(.+)$", stripped)
            if match:
                positives.append(match.group(1).strip())
                continue
            match = re.match(r"^\d+\.\s+(.+)$", stripped)
            if match:
                positives.append(match.group(1).strip())
    return positives


def _parse_finding_block(block_lines: list[str], reviewer: str | None = None) -> dict[str, Any]:
    """Parse a finding from a block of lines into a structured dict.

    Looks for: title (first line), location (file:line pattern),
    description, recommendation.
    """
    finding: dict[str, Any] = {}

    if not block_lines:
        return finding

    # Title: first non-empty line, cleaned of markdown formatting
    first_line = block_lines[0].strip()
    # Remove leading bullet/number markers
    first_line = re.sub(r"^[-*]\s+", "", first_line)
    first_line = re.sub(r"^\d+\.\s+", "", first_line)
    # Remove bold markers from issue title
    first_line = re.sub(r"\*\*(.+?)\*\*", r"\1", first_line)
    # Extract [Reviewer] prefix if present (parallel review format)
    reviewer_prefix = re.match(r"^\[([A-Za-z\s]+)\]\s*", first_line)
    if reviewer_prefix:
        finding["reviewer"] = reviewer_prefix.group(1).strip()
        first_line = first_line[reviewer_prefix.end() :]
    # If title has " - file:line" pattern, split
    loc_match = FILE_LINE_RE.search(first_line)
    if loc_match and ":" in loc_match.group(1) and re.search(r"\d+$", loc_match.group(1)):
        finding["location"] = loc_match.group(1)
        # Title is everything before the location reference
        title_part = first_line[: loc_match.start()].rstrip(" -—\t")
        if title_part:
            finding["title"] = title_part
        else:
            finding["title"] = first_line
    else:
        finding["title"] = first_line

    # Scan remaining lines for location, description, recommendation
    desc_lines: list[str] = []
    for line in block_lines[1:]:
        stripped = line.strip()

        # Location: "File: path:line" or "- file:line" or "**File**: ..."
        if "location" not in finding:
            loc_match = FILE_LINE_RE.search(stripped)
            if loc_match:
                finding["location"] = loc_match.group(1)
                continue

        # Recommendation pattern
        rec_match = re.match(r"^[-*]?\s*[Rr]ecommendation:\s*(.+)$", stripped)
        if rec_match:
            finding["recommendation"] = rec_match.group(1).strip()
            continue

        # File pattern (explicit labeled)
        file_match = re.match(r"^[-*]?\s*\*?\*?[Ff]ile\*?\*?:\s*(.+)$", stripped)
        if file_match and "location" not in finding:
            loc_match = FILE_LINE_RE.search(file_match.group(1))
            if loc_match:
                finding["location"] = loc_match.group(1)
                continue

        # Issue/Description pattern
        issue_match = re.match(r"^[-*]?\s*[Ii]ssue:\s*(.+)$", stripped)
        if issue_match:
            desc_lines.append(issue_match.group(1).strip())
            continue

        # Convention pattern (sapcc-audit)
        conv_match = re.match(r"^[-*]?\s*\*?\*?[Cc]onvention\*?\*?:\s*(.+)$", stripped)
        if conv_match:
            finding["convention"] = conv_match.group(1).strip().strip('"')
            continue

        # Reviewer tag (parallel review)
        rev_match = re.match(r"^\[([A-Za-z\s]+)\]", stripped)
        if rev_match and "reviewer" not in finding:
            finding["reviewer"] = rev_match.group(1).strip()

        # Generic content line -> description
        if stripped and not stripped.startswith("#"):
            desc_lines.append(stripped)

    if desc_lines:
        finding["description"] = " ".join(desc_lines)

    if reviewer and "reviewer" not in finding:
        finding["reviewer"] = reviewer

    return finding


def _extract_findings_section(
    lines: list[str],
    severity_map: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Extract findings grouped by severity from markdown lines.

    Walks through the document looking for severity headings, then parses
    findings within each severity section.
    """
    findings: dict[str, list[dict[str, Any]]] = {v: [] for v in set(severity_map.values())}

    current_severity: str | None = None
    current_block: list[str] = []
    current_reviewer: str | None = None

    def _flush_block() -> None:
        if current_block and current_severity:
            finding = _parse_finding_block(current_block, reviewer=current_reviewer)
            if finding.get("title"):
                findings[current_severity].append(finding)

    for line in lines:
        heading = _heading_level(line)
        if heading:
            level, text = heading
            text_lower = text.lower().strip()

            # Remove count annotations like "CRITICAL (0)" or "HIGH (N)"
            text_clean = re.sub(r"\s*\(.*?\)\s*$", "", text_lower)
            # Remove markdown suffixes like "(Block Merge)"
            text_clean = re.sub(r"\s*\(.*$", "", text_clean)
            text_clean = text_clean.strip()

            if text_clean in severity_map:
                _flush_block()
                current_severity = severity_map[text_clean]
                current_block = []
                continue

            # Any non-severity heading ends the current severity section.
            # This handles "## Summary by Reviewer", "### Summary by Reviewer",
            # "### Recommendation", etc. that appear after findings.
            if current_severity is not None and text_clean not in severity_map:
                _flush_block()
                current_severity = None
                current_block = []

        elif current_severity is not None:
            stripped = line.strip()
            if not stripped:
                # Blank line — flush current block if non-empty, start new
                _flush_block()
                current_block = []
            else:
                # Detect new finding start: numbered list item or sub-heading-like
                is_new_item = bool(re.match(r"^\d+\.\s+", stripped))
                if is_new_item and current_block:
                    _flush_block()
                    current_block = [stripped]
                else:
                    current_block.append(stripped)

    # Flush the last block
    _flush_block()
    return findings


def _extract_scorecard(lines: list[str]) -> list[dict[str, Any]]:
    """Extract SAPCC review scorecard from markdown table."""
    scorecard: list[dict[str, Any]] = []
    in_table = False
    header_found = False

    for line in lines:
        heading = _heading_level(line)
        if heading:
            _, text = heading
            if "score" in text.lower() and "card" in text.lower():
                in_table = True
                continue
            if in_table and heading[0] <= 2:
                break

        if in_table and "|" in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            # Skip separator rows
            if all(re.match(r"^[-:]+$", c) for c in cells):
                header_found = True
                continue
            # Skip header row (usually "Domain | Agent | ...")
            if not header_found and any(c.lower() in ("domain", "agent") for c in cells):
                continue
            # Skip total row
            if cells and "total" in cells[0].lower():
                continue
            # Parse data row: Domain | Agent# | Findings | Critical | High | Medium | Low
            if len(cells) >= 7:
                try:
                    entry = {
                        "domain": cells[0].replace("**", ""),
                        "agent": int(re.sub(r"[^\d]", "", cells[1]) or "0"),
                        "findings": int(re.sub(r"[^\d]", "", cells[2]) or "0"),
                        "critical": int(re.sub(r"[^\d]", "", cells[3]) or "0"),
                        "high": int(re.sub(r"[^\d]", "", cells[4]) or "0"),
                        "medium": int(re.sub(r"[^\d]", "", cells[5]) or "0"),
                        "low": int(re.sub(r"[^\d]", "", cells[6]) or "0"),
                    }
                    scorecard.append(entry)
                except (ValueError, IndexError):
                    continue
    return scorecard


def _extract_quick_wins(lines: list[str]) -> list[dict[str, Any]]:
    """Extract quick wins section from SAPCC review output."""
    quick_wins: list[dict[str, Any]] = []
    in_section = False
    current_block: list[str] = []

    def _flush() -> None:
        if current_block:
            finding = _parse_finding_block(current_block)
            if finding.get("title"):
                quick_wins.append(finding)

    for line in lines:
        heading = _heading_level(line)
        if heading:
            level, text = heading
            if "quick win" in text.lower():
                in_section = True
                continue
            if in_section and level <= 2:
                _flush()
                break

        elif in_section:
            stripped = line.strip()
            if not stripped:
                _flush()
                current_block = []
            else:
                is_new_item = bool(re.match(r"^\d+\.\s+", stripped))
                if is_new_item and current_block:
                    _flush()
                    current_block = [stripped]
                else:
                    current_block.append(stripped)

    _flush()
    return quick_wins


def _extract_package_summary(lines: list[str]) -> list[dict[str, Any]]:
    """Extract package-by-package summary table from SAPCC audit output."""
    packages: list[dict[str, Any]] = []
    in_table = False
    header_found = False

    for line in lines:
        heading = _heading_level(line)
        if heading:
            _, text = heading
            if "package" in text.lower() and "summary" in text.lower():
                in_table = True
                continue
            if in_table and heading[0] <= 2:
                break

        if in_table and "|" in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            if all(re.match(r"^[-:]+$", c) for c in cells):
                header_found = True
                continue
            if not header_found and any(c.lower() in ("package", "files") for c in cells):
                continue
            # Parse: Package | Files | Must-Fix | Should-Fix | Nit | Verdict
            if len(cells) >= 6:
                try:
                    entry = {
                        "package": cells[0].replace("**", ""),
                        "files": int(re.sub(r"[^\d]", "", cells[1]) or "0"),
                        "must_fix": int(re.sub(r"[^\d]", "", cells[2]) or "0"),
                        "should_fix": int(re.sub(r"[^\d]", "", cells[3]) or "0"),
                        "nit": int(re.sub(r"[^\d]", "", cells[4]) or "0"),
                        "verdict": cells[5],
                    }
                    packages.append(entry)
                except (ValueError, IndexError):
                    continue
    return packages


def _extract_severity_matrix(lines: list[str]) -> dict[str, int] | None:
    """Extract severity matrix counts from parallel review output.

    Looks for the severity summary table:
      | Severity | Count | Summary |
      |----------|-------|---------|
      | Critical | 2     | ...     |
    """
    in_table = False
    header_found = False
    matrix: dict[str, int] = {}

    for line in lines:
        heading = _heading_level(line)
        if heading:
            _, text = heading
            if "severity matrix" in text.lower() or ("severity" in text.lower() and "matrix" in text.lower()):
                in_table = True
                continue
            if in_table and heading[0] <= 3:
                if matrix:
                    break

        if in_table and "|" in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            if all(re.match(r"^[-:]+$", c) for c in cells):
                header_found = True
                continue
            if not header_found:
                continue
            if len(cells) >= 2:
                sev = cells[0].lower().replace("**", "").strip()
                count_str = re.sub(r"[^\d]", "", cells[1])
                if sev in ("critical", "high", "medium", "low") and count_str:
                    matrix[sev] = int(count_str)

    if len(matrix) == 4:
        return matrix
    return None


def _extract_reviewer_summary(lines: list[str]) -> list[dict[str, Any]]:
    """Extract reviewer summary matrix from parallel review output.

    Looks for the reviewer breakdown table:
      | Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
      |----------------|----------|------|--------|-----|
      | Security       | 1        | 2    | 0      | 1   |
    """
    summaries: list[dict[str, Any]] = []
    in_table = False
    header_found = False

    for line in lines:
        heading = _heading_level(line)
        if heading:
            _, text = heading
            text_lower = text.lower()
            if ("summary" in text_lower and "reviewer" in text_lower) or "reviewer" in text_lower:
                in_table = True
                continue
            if in_table and heading[0] <= 3:
                if summaries:
                    break

        if in_table and "|" in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells:
                continue
            if all(re.match(r"^[-:]+$", c) for c in cells):
                header_found = True
                continue
            if not header_found:
                continue
            # Skip total row
            if cells and "total" in cells[0].lower():
                continue
            if len(cells) >= 5:
                reviewer_name = cells[0].replace("**", "").strip()
                if not reviewer_name:
                    continue
                try:
                    entry = {
                        "reviewer": reviewer_name,
                        "critical": int(re.sub(r"[^\d]", "", cells[1]) or "0"),
                        "high": int(re.sub(r"[^\d]", "", cells[2]) or "0"),
                        "medium": int(re.sub(r"[^\d]", "", cells[3]) or "0"),
                        "low": int(re.sub(r"[^\d]", "", cells[4]) or "0"),
                    }
                    summaries.append(entry)
                except (ValueError, IndexError):
                    continue
    return summaries


def parse_markdown(content: str, review_type: str) -> dict[str, Any]:
    """Parse markdown review output into a structured dict.

    Args:
        content: Raw markdown text of the review output.
        review_type: One of the REVIEW_TYPES values.

    Returns:
        Dict matching the structure expected by the JSON Schema for this type.
    """
    lines = content.splitlines()
    result: dict[str, Any] = {}

    # Verdict
    verdict = _extract_verdict(lines)
    if verdict:
        result["verdict"] = verdict

    # Summary
    summary = _extract_summary(lines)
    if summary:
        result["summary"] = summary

    # Risk level (systematic only)
    if review_type == "systematic":
        risk_level = _extract_risk_level(lines)
        if risk_level:
            result["risk_level"] = risk_level

    # Findings
    sev_map = SEVERITY_MAP.get(review_type, {})
    findings = _extract_findings_section(lines, sev_map)
    result["findings"] = findings

    # Positives
    positives = _extract_positives(lines)
    if positives:
        result["positives"] = positives

    # Type-specific fields
    if review_type == "parallel":
        matrix = _extract_severity_matrix(lines)
        if matrix:
            result["severity_matrix"] = matrix

        reviewer_summary = _extract_reviewer_summary(lines)
        if reviewer_summary:
            result["reviewer_summary"] = reviewer_summary

    elif review_type == "sapcc-review":
        scorecard = _extract_scorecard(lines)
        if scorecard:
            result["scorecard"] = scorecard

        quick_wins = _extract_quick_wins(lines)
        if quick_wins:
            result["quick_wins"] = quick_wins
        else:
            result["quick_wins"] = []

    elif review_type == "sapcc-audit":
        package_summary = _extract_package_summary(lines)
        if package_summary:
            result["package_summary"] = package_summary

    return result


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def load_schema(review_type: str) -> dict[str, Any]:
    """Load the JSON Schema file for the given review type.

    Args:
        review_type: One of the REVIEW_TYPES values.

    Returns:
        Parsed JSON Schema dict.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
    """
    schema_file = SCHEMAS_DIR / SCHEMA_MAP[review_type]
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    return json.loads(schema_file.read_text())


def validate_structure(data: dict[str, Any], review_type: str) -> list[str]:
    """Validate parsed review data against its JSON Schema.

    Args:
        data: Parsed review output dict.
        review_type: One of the REVIEW_TYPES values.

    Returns:
        List of human-readable error messages. Empty list means valid.
    """
    schema = load_schema(review_type)
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []

    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"

        if error.validator == "required":
            # Extract missing field name from the message
            match = re.search(r"'([^']+)'", error.message)
            field_name = match.group(1) if match else error.message
            errors.append(f"MISSING: {field_name} — required field not found in review output")

        elif error.validator == "enum":
            errors.append(
                f"VALUE: {path} — {json.dumps(error.instance)} is not one of {json.dumps(error.validator_value)}"
            )

        elif error.validator == "pattern":
            errors.append(
                f"FORMAT: {path} — {json.dumps(error.instance)} does not match "
                f'pattern "{error.validator_value}" (expected file:line format)'
            )

        elif error.validator == "type":
            errors.append(f"TYPE: {path} — expected {error.validator_value}, got {type(error.instance).__name__}")

        elif error.validator == "minLength":
            errors.append(f"LENGTH: {path} — value is too short (minimum {error.validator_value} characters)")

        elif error.validator in ("minItems", "maxItems"):
            expected = error.validator_value
            actual = len(error.instance) if isinstance(error.instance, list) else "unknown"
            constraint = "at least" if error.validator == "minItems" else "at most"
            errors.append(f"COUNT: {path} — expected {constraint} {expected} items, got {actual}")

        elif error.validator == "minimum":
            errors.append(f"VALUE: {path} — {error.instance} is below minimum {error.validator_value}")

        elif error.validator == "maximum":
            errors.append(f"VALUE: {path} — {error.instance} is above maximum {error.validator_value}")

        else:
            errors.append(f"SCHEMA: {path} — {error.message}")

    return errors


def _format_structure_summary(data: dict[str, Any], review_type: str) -> str:
    """Format a human-readable summary of the parsed structure."""
    lines: list[str] = []

    verdict = data.get("verdict", "(missing)")
    lines.append(f"  verdict: {verdict}")

    findings = data.get("findings", {})
    if findings:
        counts = []
        for key, items in findings.items():
            if isinstance(items, list):
                counts.append(f"{key}={len(items)}")
        if counts:
            lines.append(f"  findings: {', '.join(counts)}")
    else:
        lines.append("  findings: (missing)")

    positives = data.get("positives", [])
    if positives:
        lines.append(f"  positives: {len(positives)} items")
    else:
        lines.append("  positives: (missing)")

    if review_type == "systematic":
        risk = data.get("risk_level", "(missing)")
        lines.append(f"  risk_level: {risk}")

    elif review_type == "parallel":
        matrix = data.get("severity_matrix")
        if matrix:
            lines.append(f"  severity_matrix: {json.dumps(matrix)}")
        else:
            lines.append("  severity_matrix: (missing)")
        reviewers = data.get("reviewer_summary", [])
        lines.append(f"  reviewer_summary: {len(reviewers)} reviewers")

    elif review_type == "sapcc-review":
        scorecard = data.get("scorecard", [])
        lines.append(f"  scorecard: {len(scorecard)} entries")
        quick_wins = data.get("quick_wins", [])
        lines.append(f"  quick_wins: {len(quick_wins)} items")

    elif review_type == "sapcc-audit":
        packages = data.get("package_summary", [])
        lines.append(f"  package_summary: {len(packages)} packages")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the validator CLI.

    Returns:
        Exit code: 0=valid, 1=structural errors, 2=parse error.
    """
    parser = argparse.ArgumentParser(
        description="Validate review output against JSON Schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=REVIEW_TYPES,
        dest="review_type",
        help="Review type to validate against.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="is_json",
        help="Input is raw JSON (skip markdown parsing).",
    )
    parser.add_argument(
        "input",
        help="Path to review output file, or '-' for stdin.",
    )
    args = parser.parse_args()

    # Read input
    if args.input == "-":
        content = sys.stdin.read()
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"ERROR: File not found: {args.input}", file=sys.stderr)
            return 2
        content = input_path.read_text()

    if not content.strip():
        print("ERROR: Input is empty", file=sys.stderr)
        return 2

    # Parse
    if args.is_json:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            print(f"ERROR: Invalid JSON: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            data = parse_markdown(content, args.review_type)
        except Exception as exc:
            print(f"ERROR: Failed to parse markdown: {exc}", file=sys.stderr)
            return 2

    if not data:
        print("ERROR: Parser returned empty structure — could not extract any review data", file=sys.stderr)
        return 2

    # Validate
    try:
        errors = validate_structure(data, args.review_type)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} structural issues\n")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        print(f"\nParsed structure:\n{_format_structure_summary(data, args.review_type)}")
        return 1

    schema_name = SCHEMA_MAP[args.review_type].replace(".schema.json", "")
    print(f"VALIDATION PASSED: {schema_name} output is structurally valid\n")
    print(f"Structure:\n{_format_structure_summary(data, args.review_type)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
