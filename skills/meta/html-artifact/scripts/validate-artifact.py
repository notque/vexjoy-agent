#!/usr/bin/env python3
"""Post-generation HTML artifact validator.

Deterministic quality checker for generated .html files. Validates structure,
self-containment, and minimum quality requirements.

Exit codes:
    0: all checks pass (warnings OK)
    1: one or more errors
    2: file not found or not readable

Usage:
    python3 skills/meta/html-artifact/scripts/validate-artifact.py path/to/artifact.html
    python3 skills/meta/html-artifact/scripts/validate-artifact.py artifact.html --json-compact
    python3 skills/meta/html-artifact/scripts/validate-artifact.py artifact.html --shape editor
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

MAX_FILE_SIZE_BYTES = 500 * 1024  # 500KB


@dataclass
class ValidationResult:
    """Aggregate validation result."""

    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """True if no errors (warnings are acceptable)."""
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, object]:
        """Serialize to output dict."""
        return {
            "valid": self.valid,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _check_doctype(content: str, result: ValidationResult) -> None:
    """File must start with <!DOCTYPE html> (case-insensitive)."""
    stripped = content.lstrip()
    passed = stripped.lower().startswith("<!doctype html>")
    result.checks["has_doctype"] = passed
    if not passed:
        result.errors.append("Missing <!DOCTYPE html> at start of file.")


def _check_title(content: str, result: ValidationResult) -> None:
    """Must contain <title> tag with non-empty content."""
    match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
    passed = match is not None and match.group(1).strip() != ""
    result.checks["has_title"] = passed
    if not passed:
        result.errors.append("Missing or empty <title> tag.")


def _check_self_contained(content: str, result: ValidationResult) -> None:
    """No external stylesheet links or script sources via http(s)."""
    has_external_css = bool(
        re.search(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?://', content, re.IGNORECASE)
    )
    has_external_js = bool(re.search(r'<script[^>]+src=["\']https?://', content, re.IGNORECASE))
    passed = not has_external_css and not has_external_js
    result.checks["self_contained"] = passed
    if not passed:
        externals = []
        if has_external_css:
            externals.append("external CSS")
        if has_external_js:
            externals.append("external JS")
        result.errors.append(f"Not self-contained: found {', '.join(externals)}.")


def _check_has_style(content: str, result: ValidationResult) -> None:
    """Must contain <style> tag (inline CSS required)."""
    passed = bool(re.search(r"<style[\s>]", content, re.IGNORECASE))
    result.checks["has_style"] = passed
    if not passed:
        result.warnings.append("No <style> tag found. Inline CSS is recommended.")


def _check_meta_viewport(content: str, result: ValidationResult) -> None:
    """Should contain <meta name="viewport" ...>."""
    passed = bool(re.search(r'<meta\s+name=["\']viewport["\']', content, re.IGNORECASE))
    result.checks["has_meta_viewport"] = passed
    if not passed:
        result.warnings.append('Missing <meta name="viewport"> tag.')


def _check_reasonable_size(file_path: Path, result: ValidationResult) -> None:
    """File size must be under 500KB."""
    size = file_path.stat().st_size
    passed = size < MAX_FILE_SIZE_BYTES
    result.checks["reasonable_size"] = passed
    if not passed:
        size_kb = size / 1024
        result.warnings.append(f"File size {size_kb:.0f}KB exceeds 500KB limit.")


def _check_no_empty_body(content: str, result: ValidationResult) -> None:
    """<body> must contain more than whitespace."""
    match = re.search(r"<body[^>]*>(.*?)</body>", content, re.IGNORECASE | re.DOTALL)
    if match is None:
        # No body tag at all — valid_structure will catch this
        passed = False
    else:
        passed = match.group(1).strip() != ""
    result.checks["no_empty_body"] = passed
    if not passed:
        result.errors.append("Empty <body> — no visible content.")


def _check_valid_structure(content: str, result: ValidationResult) -> None:
    """Must have <html>, <head>, <body> tags."""
    has_html = bool(re.search(r"<html[\s>]", content, re.IGNORECASE))
    has_head = bool(re.search(r"<head[\s>]", content, re.IGNORECASE))
    has_body = bool(re.search(r"<body[\s>]", content, re.IGNORECASE))
    passed = has_html and has_head and has_body
    result.checks["valid_structure"] = passed
    if not passed:
        missing = []
        if not has_html:
            missing.append("<html>")
        if not has_head:
            missing.append("<head>")
        if not has_body:
            missing.append("<body>")
        result.errors.append(f"Missing structural tags: {', '.join(missing)}.")


def _check_emitted_css_slop(content: str, result: ValidationResult) -> None:
    """Scan emitted CSS/markup for slop patterns via the vendored slop rules.

    Findings are reported as warnings — they do not fail the build (matches the
    non-blocking choice in distinctive-frontend-design). Promote-to-error path:
    raise a finding's rule_id to a build error here once a rule graduates from
    "warning" to "error" in css_slop_rules.py.

    Shape-agnostic: the rules check CSS/markup, not page structure, so they apply
    to every artifact shape (including hero-less shapes like report or data-viz).

    Skip when content exceeds the size limit: an oversized file is already flagged
    by the size check, and the slop regexes can backtrack pathologically over a
    multi-hundred-KB single line. Bounding by size keeps the scan deterministic.
    """
    if len(content.encode("utf-8")) >= MAX_FILE_SIZE_BYTES:
        result.checks["css_slop_clean"] = True
        return

    sys.path.insert(0, str(Path(__file__).parent))
    slop = import_module("css_slop_rules")
    findings = slop.scan_css(content)
    result.checks["css_slop_clean"] = not findings
    for f in findings:
        result.warnings.append(f"CSS slop [{f.rule_id}] line {f.line}: {f.message}")


EXPORT_SHAPES = frozenset({"editor", "prototype"})


def _check_export_button(content: str, shape: str, result: ValidationResult) -> None:
    """For editor/prototype shapes, check for copy/export functionality in scripts.

    This is a warning, not an error — the shape context isn't always available.
    """
    if shape not in EXPORT_SHAPES:
        return

    # Look for export/copy patterns in <script> blocks
    script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", content, re.IGNORECASE | re.DOTALL)
    script_content = " ".join(script_blocks)

    has_clipboard = "navigator.clipboard" in script_content
    has_copy_func = "copyToClipboard" in script_content
    has_copy = bool(re.search(r"\bcopy\b", script_content, re.IGNORECASE))

    passed = has_clipboard or has_copy_func or has_copy
    result.checks["has_export_button"] = passed
    if not passed:
        result.warnings.append(
            f"Shape '{shape}' should include copy/export functionality "
            "(navigator.clipboard, copyToClipboard, or copy function)."
        )


def validate_artifact(file_path: Path, shape: str | None = None) -> ValidationResult:
    """Run all validation checks on an HTML artifact file.

    Args:
        file_path: Path to the .html file to validate.
        shape: Optional artifact shape. When provided, enables shape-specific checks.

    Returns:
        ValidationResult with all check outcomes.
    """
    result = ValidationResult()
    content = file_path.read_text(encoding="utf-8")

    _check_doctype(content, result)
    _check_title(content, result)
    _check_self_contained(content, result)
    _check_has_style(content, result)
    _check_meta_viewport(content, result)
    _check_reasonable_size(file_path, result)
    _check_no_empty_body(content, result)
    _check_valid_structure(content, result)
    _check_emitted_css_slop(content, result)

    if shape is not None:
        _check_export_button(content, shape, result)

    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate a generated HTML artifact.")
    parser.add_argument("file", help="Path to the .html file to validate.")
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON (no indentation).")
    parser.add_argument(
        "--shape", default=None, help="Artifact shape for shape-specific checks (e.g., editor, prototype)."
    )
    args = parser.parse_args()

    file_path = Path(args.file)

    if not file_path.is_file():
        error_result = {"valid": False, "checks": {}, "warnings": [], "errors": [f"File not found: {args.file}"]}
        indent = None if args.json_compact else 2
        json.dump(error_result, sys.stdout, indent=indent)
        sys.stdout.write("\n")
        sys.exit(2)

    try:
        result = validate_artifact(file_path, shape=args.shape)
    except (OSError, UnicodeDecodeError) as e:
        error_result = {"valid": False, "checks": {}, "warnings": [], "errors": [f"Cannot read file: {e}"]}
        indent = None if args.json_compact else 2
        json.dump(error_result, sys.stdout, indent=indent)
        sys.stdout.write("\n")
        sys.exit(2)

    indent = None if args.json_compact else 2
    json.dump(result.to_dict(), sys.stdout, indent=indent)
    sys.stdout.write("\n")

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
