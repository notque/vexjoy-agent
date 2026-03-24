#!/usr/bin/env python3
"""Check ADR decision point coverage in git diff.

Extracts decision points from an ADR's ## Decision section and verifies
each has corresponding implementation evidence in the git diff (staged
changes or branch diff against a base).

Usage:
    python3 scripts/adr-decision-coverage.py --adr adr/093-parallel-agent-branch-convergence.md
    python3 scripts/adr-decision-coverage.py --adr adr/093-parallel-agent-branch-convergence.md --diff-base main
    python3 scripts/adr-decision-coverage.py --adr adr/093-parallel-agent-branch-convergence.md --json

Exit codes:
    0 = all decision points covered (PASS)
    1 = some or no decision points covered (PARTIAL or FAIL)
    2 = input error (bad ADR path, no decision section, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPT_NAME = "adr-decision-coverage"

# Words too common to be meaningful as keyword matches.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "must",
        "not",
        "no",
        "nor",
        "so",
        "if",
        "then",
        "else",
        "when",
        "where",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "all",
        "each",
        "every",
        "any",
        "some",
        "such",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "also",
        "into",
        "out",
        "up",
        "about",
        "after",
        "before",
        "between",
        "under",
        "over",
        "through",
        "during",
        "above",
        "below",
        "e",
        "g",
        "i",
    }
)

# Minimum keyword match count for coverage.
_MIN_KEYWORD_MATCHES = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DecisionPoint:
    """A single decision point extracted from an ADR."""

    index: int
    label: str
    description: str
    keywords: list[str] = field(default_factory=list)
    code_refs: list[str] = field(default_factory=list)


@dataclass
class CoverageResult:
    """Coverage status for a single decision point."""

    index: int
    label: str
    status: str  # "COVERED" or "NOT_COVERED"
    evidence: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    """Full coverage report for an ADR."""

    adr: str
    decision_points: list[CoverageResult] = field(default_factory=list)
    covered: int = 0
    total: int = 0
    percentage: int = 0
    verdict: str = "FAIL"  # "PASS", "PARTIAL", or "FAIL"


# ---------------------------------------------------------------------------
# ADR parsing
# ---------------------------------------------------------------------------


def extract_decision_section(content: str) -> str | None:
    """Extract the ## Decision section from ADR content.

    Returns the text between ``## Decision`` and the next ``## `` heading,
    or None if no Decision section exists.
    """
    lines = content.split("\n")
    start = None
    end = None

    for i, line in enumerate(lines):
        if re.match(r"^##\s+Decision\s*$", line):
            start = i + 1
        elif start is not None and re.match(r"^##\s+", line) and not re.match(r"^###", line):
            end = i
            break

    if start is None:
        return None

    return "\n".join(lines[start:end])


def parse_decision_points(section: str) -> list[DecisionPoint]:
    """Parse numbered decision points from the Decision section.

    Matches patterns like:
        1. **Before dispatch**: Orchestrator creates...
        1. **`scripts/adr-intake.py`** — CLI that scans...
    """
    points: list[DecisionPoint] = []
    pattern = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(?:[:\u2014\-\u2013]\s*)?(.*)$")

    for line in section.split("\n"):
        stripped = line.strip()
        match = pattern.match(stripped)
        if match:
            index = int(match.group(1))
            label = match.group(2).strip().strip("`")
            description = match.group(3).strip()
            point = DecisionPoint(index=index, label=label, description=description)
            points.append(point)

    return points


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting from text."""
    # Remove bold
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove backticks (but capture content separately via extract_code_refs)
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove links [text](url) -> text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text


def extract_code_refs(text: str) -> list[str]:
    """Extract backtick-enclosed code references from text."""
    return re.findall(r"`([^`]+)`", text)


def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from text.

    Strips markdown formatting, splits on non-alphanumeric characters,
    lowercases, and removes stopwords and short tokens.
    """
    clean = _strip_markdown(text)
    # Split on non-alphanumeric (keep hyphens and underscores within words)
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]*", clean)
    keywords: list[str] = []
    for token in tokens:
        lower = token.lower()
        if lower not in _STOPWORDS and len(lower) > 2:
            keywords.append(lower)
    return keywords


def enrich_decision_points(points: list[DecisionPoint]) -> None:
    """Populate keywords and code_refs on each decision point."""
    for point in points:
        full_text = f"{point.label} {point.description}"
        point.code_refs = extract_code_refs(full_text)
        point.keywords = extract_keywords(full_text)


# ---------------------------------------------------------------------------
# Git diff
# ---------------------------------------------------------------------------


def get_staged_diff() -> str:
    """Get the staged (cached) git diff.

    Raises SystemExit on git failure.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(f"{_SCRIPT_NAME}: git is not installed or not on PATH", file=sys.stderr)
        raise SystemExit(2)
    if result.returncode != 0:
        print(
            f"{_SCRIPT_NAME}: git diff --cached failed: {result.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return result.stdout


def get_branch_diff(base: str) -> str:
    """Get the diff between a base branch and HEAD.

    Raises SystemExit on git failure.
    """
    try:
        result = subprocess.run(
            ["git", "diff", f"{base}...HEAD"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(f"{_SCRIPT_NAME}: git is not installed or not on PATH", file=sys.stderr)
        raise SystemExit(2)
    if result.returncode != 0:
        print(
            f"{_SCRIPT_NAME}: git diff {base}...HEAD failed: {result.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return result.stdout


def extract_added_lines(diff: str) -> str:
    """Extract only added lines (starting with +) from a diff.

    Strips the leading ``+`` and excludes diff header lines (``+++``).
    """
    lines: list[str] = []
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Coverage matching
# ---------------------------------------------------------------------------


def check_coverage(points: list[DecisionPoint], added_text: str) -> list[CoverageResult]:
    """Check each decision point for coverage in the added text.

    A decision point is COVERED if:
    - 3+ significant keywords appear in the added text, OR
    - Any backtick-enclosed code reference appears verbatim, OR
    - The decision point label appears in the added text
    """
    added_lower = added_text.lower()
    results: list[CoverageResult] = []

    for point in points:
        evidence: list[str] = []

        # Check label match
        if point.label.lower() in added_lower:
            evidence.append(f"label: {point.label}")

        # Check code references
        for ref in point.code_refs:
            if ref.lower() in added_lower:
                evidence.append(f"code ref: {ref}")

        # Check keyword matches (word-boundary matching to avoid substring false positives)
        matched_keywords: list[str] = []
        for kw in point.keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", added_lower):
                matched_keywords.append(kw)
        if len(matched_keywords) >= _MIN_KEYWORD_MATCHES:
            evidence.append(f"keywords: {', '.join(matched_keywords[:5])}")

        status = "COVERED" if evidence else "NOT_COVERED"
        results.append(CoverageResult(index=point.index, label=point.label, status=status, evidence=evidence))

    return results


def build_report(adr_path: str, results: list[CoverageResult]) -> CoverageReport:
    """Build a coverage report from individual results."""
    covered = sum(1 for r in results if r.status == "COVERED")
    total = len(results)
    percentage = round(covered / total * 100) if total > 0 else 0

    if percentage == 100:
        verdict = "PASS"
    elif percentage > 0:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return CoverageReport(
        adr=adr_path,
        decision_points=results,
        covered=covered,
        total=total,
        percentage=percentage,
        verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_json(report: CoverageReport) -> str:
    """Format report as JSON."""
    data = {
        "adr": report.adr,
        "decision_points": [
            {
                "index": dp.index,
                "label": dp.label,
                "status": dp.status,
                "evidence": dp.evidence,
            }
            for dp in report.decision_points
        ],
        "coverage": {
            "covered": report.covered,
            "total": report.total,
            "percentage": report.percentage,
        },
        "verdict": report.verdict,
    }
    return json.dumps(data, indent=2)


def format_human(report: CoverageReport) -> str:
    """Format report as human-readable text."""
    lines: list[str] = []

    header = f"ADR Decision Coverage: {report.adr}"
    lines.append(header)
    lines.append("\u2550" * len(header))
    lines.append("")
    lines.append("Decision Points:")

    for dp in report.decision_points:
        tag = "[COVERED]    " if dp.status == "COVERED" else "[NOT COVERED]"
        lines.append(f"  {tag} {dp.index}. {dp.label}")

    lines.append("")
    lines.append(f"Coverage: {report.covered}/{report.total} ({report.percentage}%)")
    lines.append(f"Verdict: {report.verdict}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _die(message: str) -> int:
    """Print error and return exit code 2."""
    print(f"{_SCRIPT_NAME}: {message}", file=sys.stderr)
    return 2


def main() -> int:
    """Entry point for ADR decision coverage checker."""
    parser = argparse.ArgumentParser(
        prog=_SCRIPT_NAME,
        description="Check ADR decision point coverage in git diff.",
    )

    parser.add_argument("--adr", type=str, required=True, help="Path to ADR file")
    parser.add_argument(
        "--diff-base", type=str, default=None, help="Base branch for diff (default: use staged changes)"
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    output_group.add_argument("--human", action="store_true", help="Human-readable summary (default)")

    args = parser.parse_args()

    # Read ADR file
    try:
        with open(args.adr) as f:
            content = f.read()
    except FileNotFoundError:
        return _die(f"ADR file not found: {args.adr}")
    except OSError as exc:
        return _die(f"cannot read ADR file: {exc}")

    # Extract decision section
    section = extract_decision_section(content)
    if section is None:
        return _die(f"no ## Decision section found in {args.adr}")

    # Parse decision points
    points = parse_decision_points(section)
    if not points:
        return _die(f"no decision points found in {args.adr}")

    # Enrich with keywords
    enrich_decision_points(points)

    # Get diff
    if args.diff_base:
        diff = get_branch_diff(args.diff_base)
    else:
        diff = get_staged_diff()

    added_text = extract_added_lines(diff)

    if not added_text.strip():
        if args.diff_base:
            print(
                f"{_SCRIPT_NAME}: warning: no added lines in diff against {args.diff_base} (is the branch up to date?)",
                file=sys.stderr,
            )
        else:
            print(
                f"{_SCRIPT_NAME}: warning: no staged changes found (did you forget to 'git add'?)",
                file=sys.stderr,
            )

    # Check coverage
    results = check_coverage(points, added_text)
    report = build_report(args.adr, results)

    # Output
    if args.json:
        print(format_json(report))
    else:
        print(format_human(report))

    # Exit code
    if report.verdict == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
