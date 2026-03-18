#!/usr/bin/env python3
"""
Universal Quality Gate - Core Library

Language-agnostic code quality checking system.
Shared between skill and hook for maximum reuse.

Inspired by GitHub Copilot's flexible, multi-language approach.
See: https://docs.github.com/en/copilot/concepts/agents/code-review
"""

import json
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Registry location - relative to this file
REGISTRY_PATH = Path(__file__).parent / "language_registry.json"

# Display limits for output formatting
MAX_OUTPUT_LINES = 10  # Maximum lines of tool output to show
MAX_PATTERN_DISPLAY = 10  # Maximum pattern matches to display
MAX_OUTPUT_PREVIEW = 500  # Characters to include in report dict


@dataclass
class ToolResult:
    """Result from running a single tool."""

    tool_name: str
    language: str
    passed: bool
    output: str
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class QualityReport:
    """Complete quality gate report."""

    passed: bool
    languages_detected: list[str] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    pattern_matches: list[dict] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "languages_detected": self.languages_detected,
            "files_checked": self.files_checked,
            "tool_results": [
                {
                    "tool": r.tool_name,
                    "language": r.language,
                    "passed": r.passed,
                    "output": r.output[:MAX_OUTPUT_PREVIEW] if r.output else "",
                    "skipped": r.skipped,
                }
                for r in self.tool_results
            ],
            "pattern_matches": self.pattern_matches,
            "summary": self.summary,
        }


def load_registry() -> dict:
    """Load language registry configuration."""
    if not REGISTRY_PATH.exists():
        return {"languages": {}, "fallback": {"tools": {}}, "global_patterns": {}}
    return json.loads(REGISTRY_PATH.read_text())


def detect_languages(project_path: Path) -> list[str]:
    """Detect languages in project from marker files and extensions.

    Args:
        project_path: Path to project root

    Returns:
        List of detected language names
    """
    registry = load_registry()
    detected = set()

    for lang, config in registry.get("languages", {}).items():
        # Check for marker files (go.mod, package.json, etc.)
        for marker in config.get("markers", []):
            if (project_path / marker).exists():
                detected.add(lang)
                break

    return list(detected) if detected else ["unknown"]


def detect_language_from_file(file_path: Path) -> Optional[str]:
    """Detect language from a single file's extension.

    Args:
        file_path: Path to file

    Returns:
        Language name or None
    """
    registry = load_registry()
    suffix = file_path.suffix.lower()

    for lang, config in registry.get("languages", {}).items():
        if suffix in config.get("extensions", []):
            return lang

    return None


def get_files_by_language(
    files: list[Path],
) -> dict[str, list[Path]]:
    """Group files by their detected language.

    Args:
        files: List of file paths

    Returns:
        Dict mapping language name to list of files
    """
    by_language: dict[str, list[Path]] = {}

    for f in files:
        lang = detect_language_from_file(f)
        if lang:
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(f)

    return by_language


def get_changed_files(project_path: Path, staged_only: bool = False) -> list[Path]:
    """Get list of changed files from git.

    Args:
        project_path: Path to git repository
        staged_only: If True, only return staged files

    Returns:
        List of changed file paths
    """
    try:
        if staged_only:
            cmd = ["git", "diff", "--cached", "--name-only"]
        else:
            cmd = ["git", "diff", "--name-only", "HEAD"]

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                file_path = project_path / line
                if file_path.exists():
                    files.append(file_path)

        return files

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_tool_available(cmd: str) -> bool:
    """Check if a tool is available in PATH.

    Args:
        cmd: Command to check (first word of command string)

    Returns:
        True if tool is available
    """
    tool = cmd.split()[0]
    # Handle npx specially
    if tool == "npx":
        return shutil.which("npx") is not None
    return shutil.which(tool) is not None


def run_tool(
    tool_name: str,
    tool_config: dict,
    files: list[Path],
    language: str,
    fix: bool = False,
    timeout: int = 60,
) -> ToolResult:
    """Run a single quality tool.

    Args:
        tool_name: Name of the tool
        tool_config: Tool configuration from registry
        files: List of files to check
        language: Language name
        fix: Whether to run fix command instead of check
        timeout: Command timeout in seconds

    Returns:
        ToolResult with outcome
    """
    # Check if tool is optional and should be skipped
    if tool_config.get("optional", False):
        cmd_str = tool_config.get("fix_cmd" if fix else "cmd", "")
        if not check_tool_available(cmd_str):
            return ToolResult(
                tool_name=tool_name,
                language=language,
                passed=True,
                output="",
                skipped=True,
                skip_reason="Optional tool not installed",
            )

    # Get appropriate command
    if fix and "fix_cmd" in tool_config:
        cmd_template = tool_config["fix_cmd"]
    else:
        cmd_template = tool_config.get("cmd", "")

    if not cmd_template:
        return ToolResult(
            tool_name=tool_name,
            language=language,
            passed=True,
            output="",
            skipped=True,
            skip_reason="No command configured",
        )

    # Build command with files - quote paths to prevent shell injection
    # SECURITY NOTE: shell=True is used because cmd_template comes from language_registry.json
    # (a trusted, version-controlled config file). File paths are protected by shlex.quote().
    # This is an accepted risk for the flexibility of supporting arbitrary tool commands.
    file_str = " ".join(shlex.quote(str(f)) for f in files)
    cmd = cmd_template.replace("{files}", file_str)

    try:
        result = subprocess.run(
            cmd,
            shell=True,  # Required for command templates; see security note above
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return ToolResult(
            tool_name=tool_name,
            language=language,
            passed=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
        )

    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name=tool_name,
            language=language,
            passed=False,
            output="",
            error=f"Command timed out after {timeout}s",
        )
    except Exception as e:
        return ToolResult(
            tool_name=tool_name,
            language=language,
            passed=False,
            output="",
            error=str(e),
        )


def _run_builtin_checks(language: str, files: list[Path]) -> Optional[ToolResult]:
    """Run built-in checks when external tools aren't available.

    Args:
        language: Language name
        files: Files to check

    Returns:
        ToolResult or None if no built-in checker available
    """
    try:
        from builtin_checks import format_issues, run_builtin_checks

        issues = run_builtin_checks(files, language)

        if issues:
            output = format_issues(issues)
            # Count by severity
            error_count = sum(1 for i in issues if i.severity == "error")
            warning_count = sum(1 for i in issues if i.severity == "warning")
            # Only fail on errors, not warnings/info
            has_errors = error_count > 0
            return ToolResult(
                tool_name="builtin",
                language=language,
                passed=not has_errors,
                output=f"{len(issues)} issues ({error_count} errors, {warning_count} warnings)\n{output}",
            )
        else:
            return ToolResult(
                tool_name="builtin",
                language=language,
                passed=True,
                output="No issues found",
            )

    except ImportError:
        return None
    except Exception:
        return None


def check_patterns(files: list[Path], languages: list[str]) -> list[dict]:
    """Check files against global patterns.

    Args:
        files: List of files to check
        languages: Languages to check patterns for

    Returns:
        List of pattern match dicts
    """
    registry = load_registry()
    global_patterns = registry.get("global_patterns", {})
    matches = []

    for file_path in files:
        try:
            content = file_path.read_text()
            file_lang = detect_language_from_file(file_path)

            for pattern_name, pattern_config in global_patterns.items():
                # Check if pattern applies to this file's language
                applicable_langs = pattern_config.get("languages", [])
                if "*" not in applicable_langs and file_lang not in applicable_langs:
                    continue

                regex = pattern_config.get("pattern", "")
                if not regex:
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    if re.search(regex, line):
                        matches.append(
                            {
                                "file": str(file_path),
                                "line": i,
                                "pattern": pattern_name,
                                "severity": pattern_config.get("severity", "info"),
                                "message": pattern_config.get("message", pattern_name),
                                "content": line.strip()[:100],
                            }
                        )

        except Exception:
            continue

    return matches


def run_quality_gate(
    project_path: Optional[Path] = None,
    files: Optional[list[Path]] = None,
    languages: Optional[list[str]] = None,
    fix: bool = False,
    staged_only: bool = False,
    include_patterns: bool = True,
    tools_filter: Optional[list[str]] = None,
) -> QualityReport:
    """Run the universal quality gate.

    Args:
        project_path: Path to project (defaults to cwd)
        files: Specific files to check (auto-detects if None)
        languages: Specific languages to check (auto-detects if None)
        fix: Run fix commands instead of check
        staged_only: Only check staged files
        include_patterns: Check global patterns
        tools_filter: Only run these tools (e.g., ["lint", "format"])

    Returns:
        QualityReport with all results
    """
    project_path = project_path or Path.cwd()
    registry = load_registry()

    # Get files to check
    if files is None:
        files = get_changed_files(project_path, staged_only=staged_only)

    if not files:
        return QualityReport(
            passed=True,
            summary="No files to check",
        )

    # Group files by language
    files_by_lang = get_files_by_language(files)

    if not files_by_lang:
        return QualityReport(
            passed=True,
            files_checked=[str(f) for f in files],
            summary="No recognized file types to check",
        )

    # Filter languages if specified
    if languages:
        files_by_lang = {k: v for k, v in files_by_lang.items() if k in languages}

    report = QualityReport(
        passed=True,
        languages_detected=list(files_by_lang.keys()),
        files_checked=[str(f) for f in files],
    )

    # Run tools for each language
    for lang, lang_files in files_by_lang.items():
        lang_config = registry.get("languages", {}).get(lang, {})
        tools = lang_config.get("tools", {})

        external_tool_ran = False
        for tool_name, tool_config in tools.items():
            # Filter tools if specified
            if tools_filter and tool_name not in tools_filter:
                continue

            result = run_tool(tool_name, tool_config, lang_files, lang, fix=fix)
            report.tool_results.append(result)

            if not result.skipped:
                external_tool_ran = True

            if not result.passed and not result.skipped:
                report.passed = False

        # If no external tools ran, use built-in checks
        if not external_tool_ran and not fix:
            builtin_result = _run_builtin_checks(lang, lang_files)
            if builtin_result:
                report.tool_results.append(builtin_result)
                if not builtin_result.passed:
                    report.passed = False

    # Check global patterns
    if include_patterns:
        pattern_matches = check_patterns(files, list(files_by_lang.keys()))
        report.pattern_matches = pattern_matches

        # Patterns with severity "error" should fail the gate
        for match in pattern_matches:
            if match.get("severity") == "error":
                report.passed = False

    # Build summary
    total_tools = len(report.tool_results)
    passed_tools = sum(1 for r in report.tool_results if r.passed)
    skipped_tools = sum(1 for r in report.tool_results if r.skipped)
    failed_tools = total_tools - passed_tools - skipped_tools

    pattern_count = len(report.pattern_matches)
    error_patterns = sum(1 for p in report.pattern_matches if p.get("severity") == "error")

    if report.passed:
        report.summary = f"Quality gate passed: {passed_tools}/{total_tools} tools OK"
        if skipped_tools:
            report.summary += f" ({skipped_tools} skipped)"
        if pattern_count:
            report.summary += f", {pattern_count} pattern notes"
    else:
        report.summary = f"Quality gate failed: {failed_tools} tool(s) reported issues"
        if error_patterns:
            report.summary += f", {error_patterns} error pattern(s)"

    return report


def format_report(report: QualityReport, verbose: bool = False) -> str:
    """Format quality report for display.

    Args:
        report: QualityReport to format
        verbose: Include full tool output

    Returns:
        Formatted string
    """
    lines = []

    # Header
    status = "PASSED" if report.passed else "FAILED"
    lines.append(f"{'=' * 60}")
    lines.append(f" Quality Gate: {status}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    # Languages
    if report.languages_detected:
        lines.append(f"Languages: {', '.join(report.languages_detected)}")
        lines.append(f"Files: {len(report.files_checked)}")
        lines.append("")

    # Tool results
    if report.tool_results:
        lines.append("Tool Results:")
        for result in report.tool_results:
            if result.skipped:
                status_icon = "-"
                status_text = f"skipped ({result.skip_reason})"
            elif result.passed:
                status_icon = "+"
                status_text = "passed"
            else:
                status_icon = "X"
                status_text = "FAILED"

            lines.append(f"  [{status_icon}] {result.language}/{result.tool_name}: {status_text}")

            # Show output in verbose mode for any tool with output
            if verbose and result.output and result.tool_name == "builtin":
                # For builtin, show summary line
                output_lines = result.output.split("\n")
                if output_lines and output_lines[0].strip():
                    lines.append(f"      {output_lines[0]}")
            elif verbose and result.output and not result.passed:
                for line in result.output.split("\n")[:MAX_OUTPUT_LINES]:
                    if line.strip():
                        lines.append(f"      {line}")

            if result.error and not result.passed:
                lines.append(f"      Error: {result.error[:100]}")

        lines.append("")

    # Pattern matches
    if report.pattern_matches:
        lines.append("Pattern Matches:")
        for match in report.pattern_matches[:MAX_PATTERN_DISPLAY]:
            severity = match.get("severity", "info").upper()
            lines.append(f"  [{severity}] {match['file']}:{match['line']}: {match['message']}")
        if len(report.pattern_matches) > MAX_PATTERN_DISPLAY:
            lines.append(f"  ... and {len(report.pattern_matches) - MAX_PATTERN_DISPLAY} more")
        lines.append("")

    # Summary
    lines.append(report.summary)

    return "\n".join(lines)


# CLI interface for direct testing
if __name__ == "__main__":
    import sys

    # Parse simple args
    fix_mode = "--fix" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    staged = "--staged" in sys.argv

    # Run quality gate
    report = run_quality_gate(fix=fix_mode, staged_only=staged)

    # Output
    print(format_report(report, verbose=verbose))

    # Exit code
    sys.exit(0 if report.passed else 1)
