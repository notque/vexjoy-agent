#!/usr/bin/env python3
"""ADR Compliance Checker.

Deterministic post-creation validator that checks whether step names, schema types,
and family names in a pipeline component file appear verbatim in authoritative sources.

Usage:
    python3 scripts/adr-compliance.py check \\
        --file skills/prometheus-metrics/SKILL.md \\
        --step-menu pipelines/pipeline-scaffolder/references/step-menu.md \\
        --spec-format pipelines/pipeline-scaffolder/references/pipeline-spec-format.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STOPWORDS = {
    "BANNED",
    "NOTE",
    "REQUIRED",
    "TODO",
    "MUST",
    "SHOULD",
    "NEVER",
    "ALWAYS",
    "VALID",
    "FAIL",
    "PASS",
    "BLOCK",
    "NEEDS_CHANGES",
    "CRITICAL",
    "PHASE",
    "GATE",
    "RULE",
    "STEP",
    "WHEN",
    "USE",
    "YES",
    "NO",
    "AND",
    "OR",
    "NOT",
    "IF",
    "THE",
    "FOR",
    "ANY",
    "ALL",
    "ADR",
    "JSON",
    "YAML",
    "API",
    "CLI",
    "SKILL",
    "AGENT",
    "HOOK",
    "SCRIPT",
    "NULL",
    "TRUE",
    "FALSE",
    "NEW",
    "OLD",
    "EACH",
    "THIS",
    "THAT",
    "FROM",
    "INTO",
    "WITH",
    "UPON",
    "THEN",
    "ELSE",
    "ALSO",
    "ONLY",
    "BOTH",
    "NONE",
    "MORE",
    "LESS",
    "SOME",
    "MANY",
    "HASH",
    "PATH",
    "FILE",
    "NAME",
    "TYPE",
    "LIST",
    "READ",
    "WRITE",
    "CALL",
    "RUN",
    "GET",
    "SET",
    "ROLE",
    "MODE",
    "CODE",
    "TEST",
    "EXIT",
    "NEXT",
    "PREV",
    "LAST",
    "FIRST",
    "FINAL",
    "STOP",
    "SKIP",
    "FULL",
    "CLAUDE",
    "CANNOT",
    "LOAD",
    "COMPOSE",
    "PRODUCE",
    "INVALID",
    "INDEX",
    "SCAFFOLD",
    "SKILLS",
    "INTEGRATE",
    "HTML",
    "PRODUCTION",
    "EMIT",
    "INJECT",
    "CHECK",
    "RETURN",
    "CREATE",
    "BUILD",
    "DETECT",
    "MATCH",
    "PARSE",
    "SCAN",
    "CHAIN",
    "MERGE",
    "SPLIT",
    "WRAP",
    "BIND",
    "REGISTER",
    "QUERY",
    "EXTRACT",
    "VERIFY",
    # Prose words that are not step names (false positive suppressions)
    "BEFORE",
    "DOMAIN",
    "COMPOSITION",
    "ACCEPTED",
    "IMPLEMENTED",
    "RETRO",
    "DISCOVER",
    "ERROR",
    "VALUE",
    "TASK",
    "CLASSIFY",
    "ROUTE",
    "MANDATORY",
    "README",
    "OWASP",
    "ENHANCE",
    "DEFAULT",
    "ANYWAY",
    "AUTO",
    # Common structural/config words
    "LAYER",
    "SOURCE",
    "PATTERN",
    "OPTION",
    "FORMAT",
    "TEMPLATE",
    "CONFIG",
    "SERVICE",
    "SYSTEM",
    "PROCESS",
    "ACTION",
    "OUTPUT",
    "INPUT",
    "RESULT",
    "STATUS",
    "FACTOR",
    "TRIGGER",
    "CONTEXT",
    "TARGET",
    "METHOD",
    "CLASS",
    "OBJECT",
    "STYLE",
    "LEVEL",
    "SCOPE",
    "STACK",
    # ADR status words
    "PROPOSED",
    "REJECTED",
    "DEPRECATED",
    "SUPERSEDED",
    # Internal script identifiers that appear in this file's own source
    "STOPWORDS",
    "STEP_NAME",
    "STEPNAME",
    "STEPS",
}

# Pattern for candidate step names: uppercase letters and underscores, 4+ chars total
_STEP_TOKEN_RE = re.compile(r"\b([A-Z][A-Z_]{3,})\b")

# Patterns for schema values
_SCHEMA_YAML_RE = re.compile(r'schema:\s*["\']?([a-z][a-z0-9\-]+)["\']?')
_SCHEMA_JSON_RE = re.compile(r'"schema"\s*:\s*"([a-z][a-z0-9\-]+)"')

# Patterns for family values
_FAMILY_YAML_RE = re.compile(r'family:\s*["\']?([a-z][a-z0-9\-]+)["\']?')
_FAMILY_JSON_RE = re.compile(r'"family"\s*:\s*"([a-z][a-z0-9\-]+)"')


@dataclass
class Violation:
    """A single compliance violation found in the checked file."""

    type: str
    value: str
    line: int
    authoritative_source: str
    suggestion: str


@dataclass
class CheckStats:
    """Counts of items checked during a compliance run."""

    step_names_checked: int = 0
    schema_types_checked: int = 0
    family_names_checked: int = 0
    violations_found: int = 0


@dataclass
class CheckResult:
    """Complete result of a compliance check."""

    verdict: str
    file: str
    violations: list[Violation] = field(default_factory=list)
    stats: CheckStats = field(default_factory=CheckStats)


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[len(b)]


def _closest_match(value: str, candidates: set[str], max_dist: int = 3) -> str | None:
    """Return the closest candidate string by Levenshtein distance, or None if too far."""
    if not candidates:
        return None
    best: str | None = None
    best_dist = max_dist + 1
    for candidate in sorted(candidates):
        d = _levenshtein(value.lower(), candidate.lower())
        if d < best_dist:
            best_dist = d
            best = candidate
    return best if best_dist <= max_dist else None


def _strip_code_fences(lines: list[str]) -> list[str | None]:
    """Return a parallel list where lines inside fenced code blocks are replaced with None.

    Lines marked None are still included (preserving line numbers) but should be
    skipped for step-name extraction. Schema/family patterns inside JSON code blocks
    ARE still checked because they represent actual pipeline spec content.
    """
    result: list[str | None] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            result.append(None)  # fence delimiter itself: skip
        elif in_fence:
            # Inside a code block — mark for skip (step names only)
            result.append(None)
        else:
            result.append(line)
    return result


def _parse_known_steps(step_menu_path: Path) -> dict[str, str]:
    """Extract known step names from step-menu.md.

    Returns a dict mapping STEP_NAME -> family_name.
    Looks for table rows like: | STEPNAME | ... |
    Also parses the Step Name enum table in pipeline-spec-format.md style.
    """
    text = step_menu_path.read_text(encoding="utf-8")
    steps: dict[str, str] = {}

    current_family = "unknown"
    family_header_re = re.compile(r"^###\s+(.+)$")

    # Map step-menu.md section headings to canonical family names
    family_name_map = {
        "Research & Gathering": "research-gathering",
        "Structuring": "structuring",
        "Generation": "generation",
        "Validation": "validation",
        "Review": "review",
        "Git & Release": "git-release",
        "Learning & Retro": "learning-retro",
        "Decision & Planning": "decision-planning",
        "Synthesis & Reporting": "synthesis-reporting",
        "Safety & Guarding": "safety-guarding",
        "Comparison & Evaluation": "comparison-evaluation",
        "Transformation": "transformation",
        "Observation": "observation",
        "Domain Extension": "domain-extension",
        "Interaction": "interaction",
        "Orchestration": "orchestration",
        "State Management": "state-management",
        "Experimentation": "experimentation",
        "Invariant": "invariant",
    }

    # Table row pattern: | STEPNAME | ... |
    table_row_re = re.compile(r"^\|\s*([A-Z][A-Z_0-9]{1,})\s*\|")

    for line in text.splitlines():
        m = family_header_re.match(line)
        if m:
            heading = m.group(1).strip()
            fallback = heading.lower().replace(" ", "-").replace("&", "").replace("  ", "-")
            current_family = family_name_map.get(heading, fallback)

        m2 = table_row_re.match(line)
        if m2:
            name = m2.group(1).strip()
            # Skip table header rows like "Step" itself
            if name not in {"STEP", "STEPS"}:
                steps[name] = current_family

    return steps


def _parse_known_schema_types(spec_format_path: Path) -> set[str]:
    """Extract valid output schema type values from pipeline-spec-format.md.

    Looks for the Output Schema section and pulls values from the table.
    """
    text = spec_format_path.read_text(encoding="utf-8")
    schema_types: set[str] = set()

    in_output_schema = False
    # Table row: | `value` | description | producers |
    table_value_re = re.compile(r"^\|\s*`?([a-z][a-z0-9\-]+)`?\s*\|")

    for line in text.splitlines():
        if re.search(r"^###\s+Output Schema", line):
            in_output_schema = True
            continue
        if in_output_schema and line.startswith("###"):
            # Next section — stop
            break
        if in_output_schema:
            m = table_value_re.match(line)
            if m:
                val = m.group(1).strip()
                if val not in {"value", "values"}:
                    schema_types.add(val)

    return schema_types


def _parse_known_families(spec_format_path: Path) -> set[str]:
    """Extract valid step family names from pipeline-spec-format.md.

    Looks for the Step Family section table.
    """
    text = spec_format_path.read_text(encoding="utf-8")
    families: set[str] = set()

    in_step_family = False
    table_value_re = re.compile(r"^\|\s*`?([a-z][a-z0-9\-]+)`?\s*\|")

    for line in text.splitlines():
        if re.search(r"^###\s+Step Family", line):
            in_step_family = True
            continue
        if in_step_family and line.startswith("###"):
            break
        if in_step_family:
            m = table_value_re.match(line)
            if m:
                val = m.group(1).strip()
                if val not in {"family", "families"}:
                    families.add(val)

    return families


def _extract_step_candidates(lines: list[str]) -> list[tuple[str, int]]:
    """Extract candidate step name tokens from non-code-block lines.

    Returns list of (token, 1-based line number) tuples.
    Skips stopwords and tokens already known to be non-step contexts.
    """
    masked = _strip_code_fences(lines)
    candidates: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for lineno, masked_line in enumerate(masked, start=1):
        if masked_line is None:
            continue
        for m in _STEP_TOKEN_RE.finditer(masked_line):
            token = m.group(1)
            if token in STOPWORDS:
                continue
            key = (token, lineno)
            if key not in seen:
                seen.add(key)
                candidates.append((token, lineno))

    return candidates


def _extract_schema_values(lines: list[str]) -> list[tuple[str, int]]:
    """Extract output-schema values from both YAML and JSON representations in all lines."""
    results: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for lineno, line in enumerate(lines, start=1):
        for pattern in (_SCHEMA_YAML_RE, _SCHEMA_JSON_RE):
            for m in pattern.finditer(line):
                val = m.group(1)
                key = (val, lineno)
                if key not in seen:
                    seen.add(key)
                    results.append((val, lineno))

    return results


def _extract_family_values(lines: list[str]) -> list[tuple[str, int]]:
    """Extract step-family values from both YAML and JSON representations in all lines."""
    results: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for lineno, line in enumerate(lines, start=1):
        for pattern in (_FAMILY_YAML_RE, _FAMILY_JSON_RE):
            for m in pattern.finditer(line):
                val = m.group(1)
                key = (val, lineno)
                if key not in seen:
                    seen.add(key)
                    results.append((val, lineno))

    return results


def check_file(
    target_path: Path,
    step_menu_path: Path,
    spec_format_path: Path,
) -> CheckResult:
    """Run all compliance checks on target_path against the authoritative sources.

    Args:
        target_path: The pipeline component file to validate.
        step_menu_path: Path to step-menu.md (authoritative step names + families).
        spec_format_path: Path to pipeline-spec-format.md (authoritative schema types + families).

    Returns:
        CheckResult with verdict, violations, and stats.
    """
    known_steps = _parse_known_steps(step_menu_path)
    known_schema_types = _parse_known_schema_types(spec_format_path)
    known_families = _parse_known_families(spec_format_path)

    text = target_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    violations: list[Violation] = []
    stats = CheckStats()

    # --- Check 1: Step name grounding ---
    step_candidates = _extract_step_candidates(lines)
    # Deduplicate by value (only report first occurrence per unique token)
    seen_step_tokens: set[str] = set()
    for token, lineno in step_candidates:
        if token in seen_step_tokens:
            continue
        seen_step_tokens.add(token)
        stats.step_names_checked += 1

        if token not in known_steps:
            suggestion = _build_step_suggestion(token, known_steps)
            violations.append(
                Violation(
                    type="unknown_step_name",
                    value=token,
                    line=lineno,
                    authoritative_source=step_menu_path.name,
                    suggestion=suggestion,
                )
            )

    # --- Check 2: Schema type grounding ---
    schema_values = _extract_schema_values(lines)
    seen_schema_values: set[str] = set()
    for val, lineno in schema_values:
        if val in seen_schema_values:
            continue
        seen_schema_values.add(val)
        stats.schema_types_checked += 1

        if val not in known_schema_types:
            suggestion = _build_schema_suggestion(val, known_schema_types)
            violations.append(
                Violation(
                    type="unknown_schema_type",
                    value=val,
                    line=lineno,
                    authoritative_source=spec_format_path.name,
                    suggestion=suggestion,
                )
            )

    # --- Check 3: Family name grounding ---
    family_values = _extract_family_values(lines)
    seen_family_values: set[str] = set()
    for val, lineno in family_values:
        if val in seen_family_values:
            continue
        seen_family_values.add(val)
        stats.family_names_checked += 1

        if val not in known_families:
            suggestion = _build_family_suggestion(val, known_families)
            violations.append(
                Violation(
                    type="unknown_family_name",
                    value=val,
                    line=lineno,
                    authoritative_source=spec_format_path.name,
                    suggestion=suggestion,
                )
            )

    stats.violations_found = len(violations)
    verdict = "PASS" if not violations else "FAIL"

    return CheckResult(
        verdict=verdict,
        file=str(target_path),
        violations=violations,
        stats=stats,
    )


def _build_step_suggestion(token: str, known_steps: dict[str, str]) -> str:
    """Build a human-readable suggestion for an unknown step name."""
    closest = _closest_match(token, set(known_steps.keys()))
    if closest:
        family = known_steps[closest]
        return f"Did you mean {closest}? ({family} family)"
    return "No close match found in step-menu.md"


def _build_schema_suggestion(val: str, known_schema_types: set[str]) -> str:
    """Build a human-readable suggestion for an unknown schema type."""
    closest = _closest_match(val, known_schema_types)
    if closest:
        return f"Did you mean '{closest}'?"
    return "No close match found in pipeline-spec-format.md Output Schema"


def _build_family_suggestion(val: str, known_families: set[str]) -> str:
    """Build a human-readable suggestion for an unknown family name."""
    closest = _closest_match(val, known_families)
    if closest:
        return f"Did you mean '{closest}'?"
    return "No close match found in pipeline-spec-format.md Step Family"


def _serialize_result(result: CheckResult) -> dict:
    """Convert CheckResult to a JSON-serialisable dict."""
    return {
        "verdict": result.verdict,
        "file": result.file,
        "violations": [
            {
                "type": v.type,
                "value": v.value,
                "line": v.line,
                "authoritative_source": v.authoritative_source,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ],
        "stats": {
            "step_names_checked": result.stats.step_names_checked,
            "schema_types_checked": result.stats.schema_types_checked,
            "family_names_checked": result.stats.family_names_checked,
            "violations_found": result.stats.violations_found,
        },
    }


def cmd_check(args: argparse.Namespace) -> int:
    """Execute the check subcommand.

    Args:
        args: Parsed CLI arguments with file, step_menu, spec_format attributes.

    Returns:
        Exit code: 0 = PASS, 1 = FAIL, 2 = usage error.
    """
    file_path = Path(args.file)
    step_menu_path = Path(args.step_menu)
    spec_format_path = Path(args.spec_format)

    for p, label in [
        (file_path, "--file"),
        (step_menu_path, "--step-menu"),
        (spec_format_path, "--spec-format"),
    ]:
        if not p.exists():
            error = {"error": f"{label} not found: {p}", "exit_code": 2}
            print(json.dumps(error, indent=2))
            return 2

    try:
        result = check_file(file_path, step_menu_path, spec_format_path)
    except OSError as exc:
        error = {"error": f"Failed to read file: {exc}", "exit_code": 2}
        print(json.dumps(error, indent=2))
        return 2

    print(json.dumps(_serialize_result(result), indent=2))
    return 0 if result.verdict == "PASS" else 1


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="ADR Compliance Checker — deterministic post-creation validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Check a file for compliance against authoritative step and schema sources",
    )
    check_parser.add_argument("--file", required=True, help="Path to the file to check")
    check_parser.add_argument(
        "--step-menu",
        required=True,
        dest="step_menu",
        help="Path to step-menu.md (authoritative step names)",
    )
    check_parser.add_argument(
        "--spec-format",
        required=True,
        dest="spec_format",
        help="Path to pipeline-spec-format.md (authoritative schema/family types)",
    )

    # Subcommand: check-adr (lightweight component-ADR alignment check)
    adr_parser = subparsers.add_parser(
        "check-adr",
        help="Check if a component file aligns with the active ADR session",
    )
    adr_parser.add_argument("--file", required=True, help="Path to the component file to check")
    adr_parser.add_argument("--adr", help="Path to ADR file (default: from .adr-session.json)")

    return parser


def cmd_check_adr(args) -> int:
    """Lightweight check: does a component file align with the active ADR?

    Checks:
    1. ADR session exists (or --adr provided)
    2. ADR file exists and is readable
    3. Component file's name: field matches an ADR-listed component
    4. Component file contains an ADR reference comment or section
    """
    import json as _json

    # Find ADR path
    adr_path = None
    session_parse_error = None
    if args.adr:
        adr_path = Path(args.adr)
    else:
        session_file = Path(".adr-session.json")
        if session_file.exists():
            try:
                session = _json.loads(session_file.read_text())
                adr_path = Path(session.get("adr_path", ""))
            except (json.JSONDecodeError, OSError) as e:
                session_parse_error = e
                print(f"[adr-compliance] WARNING: .adr-session.json exists but could not be read: {e}", file=sys.stderr)

    if not adr_path or not adr_path.exists():
        reason = f"Session file corrupt: {session_parse_error}" if session_parse_error else "No active ADR session"
        print(_json.dumps({"verdict": "SKIP", "reason": reason}))
        return 0

    component_path = Path(args.file)
    if not component_path.exists():
        print(_json.dumps({"verdict": "FAIL", "reason": f"File not found: {args.file}"}))
        return 1

    adr_text = adr_path.read_text(encoding="utf-8").lower()
    component_text = component_path.read_text(encoding="utf-8")

    # Extract name from frontmatter
    name_match = re.search(r"^name:\s*(.+)$", component_text, re.MULTILINE)
    component_name = name_match.group(1).strip().strip("'\"") if name_match else component_path.stem

    # Check if ADR mentions this component
    mentioned = component_name.lower() in adr_text or component_path.stem.lower() in adr_text

    result = {
        "verdict": "PASS" if mentioned else "INFO",
        "file": str(component_path),
        "adr": str(adr_path),
        "component_name": component_name,
        "mentioned_in_adr": mentioned,
        "note": "Component referenced in ADR" if mentioned else "Component not mentioned in ADR (may be new addition)",
    }

    print(_json.dumps(result, indent=2))
    return 0


def main() -> int:
    """Entry point for the ADR compliance checker CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "check-adr":
        return cmd_check_adr(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
