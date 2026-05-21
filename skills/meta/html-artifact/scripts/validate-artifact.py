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
from pathlib import Path

MAX_FILE_SIZE_BYTES = 500 * 1024  # 500KB

HTML_ARTIFACT_VERSION = "1.1"
ASSEMBLER_MARKER_RE = re.compile(r"<!--\s*assembled by html-artifact v[\w.\-]+\s*-->", re.IGNORECASE)

# Shapes that require a theme toggle in the rendered HTML.
THEME_TOGGLE_REQUIRED_SHAPES = frozenset({"deck", "spec", "code-review", "prototype", "report", "diagram"})


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
    """No external stylesheet links, script sources, or SVG image refs via http(s)."""
    has_external_css = bool(
        re.search(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?://', content, re.IGNORECASE)
    )
    has_external_js = bool(re.search(r'<script[^>]+src=["\']https?://', content, re.IGNORECASE))
    # SVG <image href="http..."> and <use href="http..."> bypass the inline-SVG-only contract.
    has_external_svg_image = bool(re.search(r'<image\b[^>]+href=["\']https?://', content, re.IGNORECASE))
    has_external_svg_use = bool(re.search(r'<use\b[^>]+href=["\']https?://', content, re.IGNORECASE))
    passed = not (has_external_css or has_external_js or has_external_svg_image or has_external_svg_use)
    result.checks["self_contained"] = passed
    if not passed:
        externals = []
        if has_external_css:
            externals.append("external CSS")
        if has_external_js:
            externals.append("external JS")
        if has_external_svg_image:
            externals.append("external <image href>")
        if has_external_svg_use:
            externals.append("external <use href>")
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


EXPORT_SHAPES = frozenset({"editor", "prototype"})


def _check_assembler_marker(content: str, result: ValidationResult) -> None:
    """HTML must contain the assembler marker comment.

    Hand-authored HTML that bypasses assemble-template.py is rejected.
    """
    passed = bool(ASSEMBLER_MARKER_RE.search(content))
    result.checks["has_assembler_marker"] = passed
    if not passed:
        result.errors.append("Hand-authored HTML rejected. Run assemble-template.py first.")


def _detect_shape_attribute(content: str) -> str | None:
    """Return the value of <body data-shape="..."> if present, else None."""
    match = re.search(
        r"<body\b[^>]*\bdata-shape\s*=\s*[\"']([^\"']+)[\"']",
        content,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _check_theme_toggle(content: str, shape: str | None, result: ValidationResult) -> None:
    """Shapes in THEME_TOGGLE_REQUIRED_SHAPES must contain a theme toggle.

    Acceptable forms:
      - any element with attribute [data-theme-toggle]
      - <button class="theme-toggle"> (class may include other tokens)
    """
    detected_shape = _detect_shape_attribute(content) or shape
    if detected_shape is None or detected_shape not in THEME_TOGGLE_REQUIRED_SHAPES:
        return

    has_data_attr = bool(re.search(r"\bdata-theme-toggle\b", content, re.IGNORECASE))
    has_button_class = bool(
        re.search(
            r"<button\b[^>]*\bclass\s*=\s*[\"'][^\"']*\btheme-toggle\b",
            content,
            re.IGNORECASE,
        )
    )
    passed = has_data_attr or has_button_class
    result.checks["has_theme_toggle"] = passed
    if not passed:
        result.errors.append(f"Theme toggle missing — required for shape {detected_shape}.")


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


_INTERNAL_REF_RE = re.compile(r'href=["\']#([^"\']+)["\']', re.IGNORECASE)
_ID_ATTR_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)


def _check_no_broken_internal_refs(content: str, result: ValidationResult) -> None:
    """Every `href="#id"` must point to an element with matching `id`.

    Mirrors the SKILL.md "No broken internal refs" claim. Skips empty `href="#"`
    (deliberate placeholder) and `href="#top"` (browser default for top-of-page).
    """
    # Strip <script> and <style> blocks before scanning ids — JS string literals and
    # CSS selectors can produce false ids that don't actually exist as DOM ids.
    scrubbed = re.sub(r"<script\b[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
    scrubbed = re.sub(r"<style\b[^>]*>.*?</style>", "", scrubbed, flags=re.IGNORECASE | re.DOTALL)

    refs = {m.group(1) for m in _INTERNAL_REF_RE.finditer(scrubbed)}
    refs.discard("top")  # browser default
    ids = {m.group(1) for m in _ID_ATTR_RE.finditer(scrubbed)}

    broken = sorted(refs - ids)
    passed = not broken
    result.checks["no_broken_internal_refs"] = passed
    if not passed:
        # Cap the message length so a runaway template doesn't blow up output.
        shown = ", ".join(f"#{r}" for r in broken[:5])
        suffix = f" (+{len(broken) - 5} more)" if len(broken) > 5 else ""
        result.errors.append(f"Broken internal refs: {shown}{suffix}.")


_SVG_OPEN_RE = re.compile(r"<svg\b([^>]*)>", re.IGNORECASE)
_BUTTON_BLOCK_RE = re.compile(r"<button\b[^>]*>.*?</button>", re.IGNORECASE | re.DOTALL)


def _check_svg_accessibility(content: str, result: ValidationResult) -> None:
    """Every visible <svg> needs role="img" + aria-label OR explicit role="presentation".

    Mirrors design-system.md accessibility checklist. SVGs nested inside <button>
    are exempt because the button's aria-label provides the accessibility hook.
    Empty/no-svg artifacts pass trivially.
    """
    # Strip <button>...</button> blocks first — their inner <svg>s are decorative.
    scrubbed = _BUTTON_BLOCK_RE.sub("", content)
    matches = list(_SVG_OPEN_RE.finditer(scrubbed))
    if not matches:
        result.checks["svg_accessibility"] = True
        return

    bad = []
    for m in matches:
        attrs = m.group(1)
        has_role_img = bool(re.search(r'\brole=["\']img["\']', attrs, re.IGNORECASE))
        has_aria_label = bool(re.search(r'\baria-label=["\'][^"\']+["\']', attrs, re.IGNORECASE))
        has_aria_labelledby = bool(re.search(r"\baria-labelledby=", attrs, re.IGNORECASE))
        has_role_presentation = bool(re.search(r'\brole=["\'](presentation|none)["\']', attrs, re.IGNORECASE))
        has_aria_hidden = bool(re.search(r'\baria-hidden=["\']true["\']', attrs, re.IGNORECASE))
        if has_role_presentation or has_aria_hidden:
            continue
        if has_role_img and (has_aria_label or has_aria_labelledby):
            continue
        # Snip the offending tag opening for the error message.
        snippet = (m.group(0)[:80] + "…") if len(m.group(0)) > 80 else m.group(0)
        bad.append(snippet)

    passed = not bad
    result.checks["svg_accessibility"] = passed
    if not passed:
        shown = "; ".join(bad[:3])
        suffix = f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""
        result.errors.append(
            f"SVG accessibility: {len(bad)} <svg> missing role='img'+aria-label "
            f"(or role='presentation'/aria-hidden='true'): {shown}{suffix}."
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
    _check_assembler_marker(content, result)
    _check_theme_toggle(content, shape, result)
    _check_no_broken_internal_refs(content, result)
    _check_svg_accessibility(content, result)

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
