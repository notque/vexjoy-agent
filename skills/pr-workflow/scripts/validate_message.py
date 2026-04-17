#!/usr/bin/env python3
"""
Commit message validation script.

Validates:
- Conventional commit format
- Banned pattern detection
- Subject line length
- Body line wrapping
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Conventional commit types
CONVENTIONAL_TYPES = [
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
]

# Default banned patterns
DEFAULT_BANNED_PATTERNS = [
    "Generated with Claude Code",
    "Co-Authored-By: Claude",
    "🤖 Generated",
    "AI-generated",
    "Automated commit by AI",
]

# Conventional commit regex
# Format: type(scope): subject
CONVENTIONAL_REGEX = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9\-]+\))?: .+"


class ValidationIssue:
    """Represents a validation issue."""

    def __init__(self, issue_type: str, message: str, severity: str, line_number: int = None):
        self.type = issue_type
        self.message = message
        self.severity = severity  # 'critical', 'error', 'warning'
        self.line_number = line_number

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {"type": self.type, "message": self.message, "severity": self.severity}
        if self.line_number is not None:
            result["line_number"] = self.line_number
        return result


def load_banned_patterns() -> List[str]:
    """
    Load banned patterns from CLAUDE.md if available.

    Returns:
        List of banned pattern strings
    """
    banned_patterns = DEFAULT_BANNED_PATTERNS.copy()

    # Try to load from validate_state.py (CLAUDE.md parsing)
    try:
        # Import validate_state to use its CLAUDE.md parsing
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from validate_state import validate_claude_md

        claude_md_result = validate_claude_md()
        if claude_md_result.get("claude_md_found"):
            banned_patterns = claude_md_result["banned_patterns"]
    except ImportError:
        pass  # Use defaults

    return banned_patterns


def parse_commit_message(message: str) -> Dict[str, Any]:
    """
    Parse commit message into components.

    Args:
        message: Full commit message

    Returns:
        {
            "subject": str,
            "body": str (optional),
            "footer": str (optional),
            "type": str (if conventional commit),
            "scope": str (if conventional commit with scope),
            "breaking": bool
        }
    """
    lines = message.split("\n")

    # Subject is first line
    subject = lines[0].strip() if lines else ""

    # Find first blank line (separates subject from body)
    body_start = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "":
            body_start = i + 1
            break

    # Extract body and footer
    body = ""
    footer = ""

    if body_start:
        body_lines = []
        footer_lines = []
        in_footer = False

        for i in range(body_start, len(lines)):
            line = lines[i]

            # Footer typically starts with keywords like "BREAKING CHANGE:" or "Refs:"
            if re.match(r"^[A-Z\-]+:", line):
                in_footer = True

            if in_footer:
                footer_lines.append(line)
            else:
                body_lines.append(line)

        body = "\n".join(body_lines).strip()
        footer = "\n".join(footer_lines).strip()

    # Parse conventional commit format
    conv_match = re.match(r"^([a-z]+)(\([a-z0-9\-]+\))?: (.+)", subject)
    commit_type = None
    scope = None
    breaking = False

    if conv_match:
        commit_type = conv_match.group(1)
        scope = conv_match.group(2).strip("()") if conv_match.group(2) else None

    # Check for breaking change
    if "BREAKING CHANGE:" in footer or "!" in subject:
        breaking = True

    return {
        "subject": subject,
        "body": body,
        "footer": footer,
        "type": commit_type,
        "scope": scope,
        "breaking": breaking,
    }


def validate_conventional_commit(message: str) -> Tuple[bool, List[ValidationIssue]]:
    """
    Validate conventional commit format.

    Args:
        message: Commit message

    Returns:
        (is_valid, issues)
    """
    issues = []
    parsed = parse_commit_message(message)
    subject = parsed["subject"]

    # Check if it matches conventional format
    if not re.match(CONVENTIONAL_REGEX, subject, re.IGNORECASE):
        # Check if type is present but invalid
        type_match = re.match(r"^([a-z]+)(\([a-z0-9\-]+\))?: ", subject, re.IGNORECASE)
        if type_match:
            commit_type = type_match.group(1).lower()
            if commit_type not in CONVENTIONAL_TYPES:
                issues.append(
                    ValidationIssue(
                        "format_error",
                        f"Invalid commit type: '{commit_type}'. Valid types: {', '.join(CONVENTIONAL_TYPES)}",
                        "error",
                        line_number=1,
                    )
                )
        else:
            issues.append(
                ValidationIssue(
                    "format_error",
                    "Does not follow conventional commit format: <type>[optional scope]: <description>",
                    "error",
                    line_number=1,
                )
            )

    # Validate subject line
    if not subject:
        issues.append(ValidationIssue("format_error", "Subject line is empty", "critical", line_number=1))
    else:
        # Check length
        if len(subject) > 72:
            issues.append(
                ValidationIssue(
                    "format_error",
                    f"Subject line exceeds 72 characters ({len(subject)} chars)",
                    "warning",
                    line_number=1,
                )
            )

        # Check for period at end
        if subject.endswith("."):
            issues.append(
                ValidationIssue("format_error", "Subject line should not end with period", "warning", line_number=1)
            )

        # Check capitalization (after type:)
        if ":" in subject:
            description = subject.split(":", 1)[1].strip()
            if description and description[0].isupper():
                issues.append(
                    ValidationIssue(
                        "format_error",
                        "Subject description should start with lowercase (after 'type:')",
                        "warning",
                        line_number=1,
                    )
                )

    return len(issues) == 0, issues


def validate_banned_patterns(message: str, banned_patterns: List[str]) -> Tuple[bool, List[ValidationIssue]]:
    """
    Check for banned patterns in commit message.

    Args:
        message: Commit message
        banned_patterns: List of banned pattern strings

    Returns:
        (is_valid, issues)
    """
    issues = []
    lines = message.split("\n")

    for pattern in banned_patterns:
        for i, line in enumerate(lines, start=1):
            if pattern.lower() in line.lower():
                issues.append(
                    ValidationIssue(
                        "banned_pattern", f"Contains banned pattern: '{pattern}'", "critical", line_number=i
                    )
                )

    return len(issues) == 0, issues


def validate_body_formatting(message: str) -> Tuple[bool, List[ValidationIssue]]:
    """
    Validate body formatting (line wrapping, etc.).

    Args:
        message: Commit message

    Returns:
        (is_valid, issues)
    """
    issues = []
    parsed = parse_commit_message(message)
    body = parsed["body"]

    if body:
        body_lines = body.split("\n")
        for i, line in enumerate(body_lines, start=2):  # Body starts at line 2 (after blank line)
            if len(line) > 72 and not line.startswith("http"):  # Allow long URLs
                issues.append(
                    ValidationIssue(
                        "format_warning",
                        f"Body line exceeds 72 characters ({len(line)} chars)",
                        "warning",
                        line_number=i,
                    )
                )

    return len(issues) == 0, issues


def validate_message(
    message: str,
    check_conventional: bool = True,
    check_banned: bool = True,
    check_formatting: bool = True,
    banned_patterns: List[str] = None,
) -> Dict[str, Any]:
    """
    Validate complete commit message.

    Args:
        message: Commit message to validate
        check_conventional: Check conventional commit format
        check_banned: Check for banned patterns
        check_formatting: Check formatting (line length, etc.)
        banned_patterns: Custom banned patterns (uses defaults if None)

    Returns:
        {
            "valid": bool,
            "conventional_commit": bool,
            "issues": [{"type": str, "message": str, "severity": str, "line_number": int}],
            "parsed": {...}
        }
    """
    if banned_patterns is None:
        banned_patterns = load_banned_patterns()

    all_issues = []

    # Parse message
    parsed = parse_commit_message(message)

    # Run validations
    if check_conventional:
        _conv_valid, conv_issues = validate_conventional_commit(message)
        all_issues.extend(conv_issues)

    if check_banned:
        _banned_valid, banned_issues = validate_banned_patterns(message, banned_patterns)
        all_issues.extend(banned_issues)

    if check_formatting:
        _format_valid, format_issues = validate_body_formatting(message)
        all_issues.extend(format_issues)

    # Determine overall validity
    # Critical or error issues = invalid
    critical_or_error = any(issue.severity in ["critical", "error"] for issue in all_issues)
    valid = not critical_or_error

    return {
        "valid": valid,
        "conventional_commit": parsed["type"] is not None,
        "issues": [issue.to_dict() for issue in all_issues],
        "parsed": parsed,
    }


def format_validation_report(result: Dict[str, Any], message: str) -> str:
    """Format validation results as human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append(" COMMIT MESSAGE VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Show commit message
    lines.append("Message:")
    lines.append("-" * 60)
    for i, line in enumerate(message.split("\n"), start=1):
        lines.append(f"  {i:2d} | {line}")
    lines.append("")

    # Show parsed structure
    lines.append("Parsed Structure:")
    lines.append("-" * 60)
    parsed = result["parsed"]
    if parsed["type"]:
        lines.append(f"  Type: {parsed['type']}")
        if parsed["scope"]:
            lines.append(f"  Scope: {parsed['scope']}")
    lines.append(f"  Subject: {parsed['subject']}")
    if parsed["body"]:
        lines.append(f"  Body: {len(parsed['body'])} characters")
    if parsed["footer"]:
        lines.append("  Footer: Present")
    if parsed["breaking"]:
        lines.append("  Breaking Change: Yes")
    lines.append("")

    # Show issues
    if result["issues"]:
        lines.append("Validation Issues:")
        lines.append("-" * 60)

        # Group by severity
        critical = [i for i in result["issues"] if i["severity"] == "critical"]
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        warnings = [i for i in result["issues"] if i["severity"] == "warning"]

        for severity_name, issues in [("CRITICAL", critical), ("ERROR", errors), ("WARNING", warnings)]:
            if issues:
                lines.append(f"\n  {severity_name}:")
                for issue in issues:
                    line_info = f" (line {issue['line_number']})" if "line_number" in issue else ""
                    lines.append(f"    ✗ {issue['message']}{line_info}")
        lines.append("")
    else:
        lines.append("✓ No validation issues found")
        lines.append("")

    # Overall status
    lines.append("=" * 60)
    if result["valid"]:
        lines.append(" VALIDATION PASSED")
        if result["conventional_commit"]:
            lines.append(" ✓ Conventional commit format")
    else:
        lines.append(" VALIDATION FAILED")
        lines.append("")
        lines.append("Address critical/error issues before committing.")

    lines.append("=" * 60)

    return "\n".join(lines)


def suggest_fixes(result: Dict[str, Any], message: str) -> str:
    """Generate suggested fixes for common issues."""
    if result["valid"]:
        return None

    suggestions = []
    parsed = result["parsed"]

    # Check for banned patterns
    banned_issues = [i for i in result["issues"] if i["type"] == "banned_pattern"]
    if banned_issues:
        suggestions.append("REMOVE BANNED PATTERNS:")
        for issue in banned_issues:
            pattern = issue["message"].split("'")[1] if "'" in issue["message"] else "pattern"
            suggestions.append(f"  - Remove: {pattern}")
        suggestions.append("")

        # Suggest clean message
        clean_message = message
        for issue in banned_issues:
            if "'" in issue["message"]:
                pattern = issue["message"].split("'")[1]
                clean_message = clean_message.replace(pattern, "").strip()

        suggestions.append("Suggested revised message:")
        suggestions.append("─" * 60)
        suggestions.append(clean_message)
        suggestions.append("─" * 60)
        suggestions.append("")

    # Check for type issues
    type_issues = [i for i in result["issues"] if "Invalid commit type" in i["message"]]
    if type_issues:
        suggestions.append("FIX COMMIT TYPE:")
        suggestions.append(f"  Valid types: {', '.join(CONVENTIONAL_TYPES)}")
        suggestions.append("")

    # Check for subject length
    length_issues = [
        i for i in result["issues"] if "exceeds 72 characters" in i["message"] and i.get("line_number") == 1
    ]
    if length_issues:
        suggestions.append("SHORTEN SUBJECT LINE:")
        subject = parsed["subject"]
        if len(subject) > 72:
            # Try to suggest shortened version
            if ":" in subject:
                type_part, desc = subject.split(":", 1)
                desc = desc.strip()
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                    suggested = f"{type_part}: {desc}"
                    suggestions.append(f"  Current ({len(subject)} chars): {subject}")
                    suggestions.append(f"  Suggested ({len(suggested)} chars): {suggested}")
        suggestions.append("")

    return "\n".join(suggestions) if suggestions else None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate git commit message format and content")
    parser.add_argument("--message", type=str, help="Commit message to validate")
    parser.add_argument("--file", type=Path, help="File containing commit message")
    parser.add_argument("--stdin", action="store_true", help="Read commit message from stdin")
    parser.add_argument("--no-conventional", action="store_true", help="Skip conventional commit format check")
    parser.add_argument("--no-banned", action="store_true", help="Skip banned pattern check")
    parser.add_argument("--no-formatting", action="store_true", help="Skip formatting check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--suggest-fixes", action="store_true", help="Show suggested fixes for issues")

    args = parser.parse_args()

    # Get commit message
    message = None
    if args.message:
        message = args.message
    elif args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        with open(args.file, "r", encoding="utf-8") as f:
            message = f.read()
    elif args.stdin:
        message = sys.stdin.read()
    else:
        print("Error: Must provide --message, --file, or --stdin", file=sys.stderr)
        parser.print_help()
        sys.exit(2)

    message = message.strip()

    try:
        # Validate message
        result = validate_message(
            message,
            check_conventional=not args.no_conventional,
            check_banned=not args.no_banned,
            check_formatting=not args.no_formatting,
        )

        # Output results
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(format_validation_report(result, message))

            if args.suggest_fixes and not result["valid"]:
                print("")
                fixes = suggest_fixes(result, message)
                if fixes:
                    print(fixes)

        # Exit code
        if result["valid"]:
            sys.exit(0)
        else:
            # Check severity
            has_critical = any(i["severity"] == "critical" for i in result["issues"])
            has_error = any(i["severity"] == "error" for i in result["issues"])

            if has_critical or has_error:
                sys.exit(1)  # Must fix
            else:
                sys.exit(0)  # Only warnings, OK to proceed

    except Exception as e:
        print(
            json.dumps({"status": "error", "error_type": type(e).__name__, "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
