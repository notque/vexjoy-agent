"""Tests for validate-artifact.py — HTML artifact validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "validate-artifact.py")

# --- Import module directly for unit tests ---
sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

validate_mod = import_module("validate-artifact")
validate_artifact = validate_mod.validate_artifact

VALID_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <!-- assembled by html-artifact v1.1 -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Artifact</title>
    <style>body { margin: 0; }</style>
</head>
<body>
    <h1>Hello</h1>
</body>
</html>"""

VALID_HTML_WITH_COPY = """<!DOCTYPE html>
<html lang="en">
<head>
    <!-- assembled by html-artifact v1.1 -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editor</title>
    <style>body { margin: 0; }</style>
</head>
<body>
    <h1>Editor</h1>
    <script>
    function copyToClipboard(text) { navigator.clipboard.writeText(text); }
    </script>
</body>
</html>"""

MINIMAL_VALID = """<!DOCTYPE html>
<html>
<head><!-- assembled by html-artifact v1.1 --><title>X</title><style>*{}</style></head>
<body><p>content</p></body>
</html>"""


def _write_tmp(content: str) -> Path:
    """Write content to a temp .html file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


def run_validate(file_path: str, compact: bool = False) -> tuple[dict, int]:
    """Run validate-artifact.py and return (parsed JSON, exit code)."""
    cmd = [sys.executable, SCRIPT, file_path]
    if compact:
        cmd.append("--json-compact")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    parsed = json.loads(result.stdout)
    return parsed, result.returncode


class TestValidateArtifactDirect:
    """Unit tests calling validate_artifact() directly."""

    def test_valid_html_passes_all(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path)
            assert result.valid
            assert all(result.checks.values())
            assert result.errors == []
            assert result.warnings == []
        finally:
            path.unlink()

    def test_missing_doctype(self) -> None:
        html = "<html><head><title>T</title><style>*{}</style></head><body><p>x</p></body></html>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["has_doctype"]
            assert not result.valid
        finally:
            path.unlink()

    def test_missing_title(self) -> None:
        html = "<!DOCTYPE html><html><head><style>*{}</style></head><body><p>x</p></body></html>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["has_title"]
            assert not result.valid
        finally:
            path.unlink()

    def test_empty_title(self) -> None:
        html = "<!DOCTYPE html><html><head><title>  </title><style>*{}</style></head><body><p>x</p></body></html>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["has_title"]
        finally:
            path.unlink()

    def test_external_css_fails_self_contained(self) -> None:
        html = (
            "<!DOCTYPE html><html><head><title>T</title>"
            '<link rel="stylesheet" href="https://cdn.example.com/style.css">'
            "<style>*{}</style></head><body><p>x</p></body></html>"
        )
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["self_contained"]
            assert any("external CSS" in e for e in result.errors)
        finally:
            path.unlink()

    def test_external_js_fails_self_contained(self) -> None:
        html = (
            "<!DOCTYPE html><html><head><title>T</title><style>*{}</style></head>"
            '<body><p>x</p><script src="https://cdn.example.com/app.js"></script></body></html>'
        )
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["self_contained"]
            assert any("external JS" in e for e in result.errors)
        finally:
            path.unlink()

    def test_no_style_is_warning(self) -> None:
        html = "<!DOCTYPE html><html><head><title>T</title></head><body><p>x</p></body></html>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["has_style"]
            # has_style is a warning, not an error — so valid can still be True
            assert any("style" in w.lower() for w in result.warnings)
        finally:
            path.unlink()

    def test_missing_viewport_is_warning(self) -> None:
        path = _write_tmp(MINIMAL_VALID)
        try:
            result = validate_artifact(path)
            assert not result.checks["has_meta_viewport"]
            assert any("viewport" in w for w in result.warnings)
            # Warnings don't cause failure
            assert result.valid
        finally:
            path.unlink()

    def test_empty_body(self) -> None:
        html = "<!DOCTYPE html><html><head><title>T</title><style>*{}</style></head><body>   </body></html>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["no_empty_body"]
            assert not result.valid
        finally:
            path.unlink()

    def test_missing_structure_tags(self) -> None:
        html = "<!DOCTYPE html><title>T</title><style>*{}</style><p>content</p>"
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["valid_structure"]
            assert any("Missing structural tags" in e for e in result.errors)
        finally:
            path.unlink()

    def test_large_file_warns(self) -> None:
        # Create a file just over 500KB
        html = VALID_HTML + ("x" * (501 * 1024))
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert not result.checks["reasonable_size"]
            assert any("500KB" in w for w in result.warnings)
        finally:
            path.unlink()

    def test_to_dict_structure(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path)
            d = result.to_dict()
            assert "valid" in d
            assert "checks" in d
            assert "warnings" in d
            assert "errors" in d
        finally:
            path.unlink()

    def test_deterministic_same_input_same_output(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            results = [validate_artifact(path).to_dict() for _ in range(5)]
            assert all(r == results[0] for r in results)
        finally:
            path.unlink()

    def test_export_button_check_skipped_without_shape(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path)
            assert "has_export_button" not in result.checks
        finally:
            path.unlink()

    def test_export_button_check_skipped_for_non_export_shape(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path, shape="spec")
            assert "has_export_button" not in result.checks
        finally:
            path.unlink()

    def test_export_button_warning_for_editor_without_copy(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path, shape="editor")
            assert not result.checks["has_export_button"]
            assert any("copy/export" in w for w in result.warnings)
            # Warning, not error — still valid
            assert result.valid
        finally:
            path.unlink()

    def test_export_button_warning_for_prototype_without_copy(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result = validate_artifact(path, shape="prototype")
            assert not result.checks["has_export_button"]
            assert any("copy/export" in w for w in result.warnings)
        finally:
            path.unlink()

    def test_export_button_passes_with_clipboard(self) -> None:
        path = _write_tmp(VALID_HTML_WITH_COPY)
        try:
            result = validate_artifact(path, shape="editor")
            assert result.checks["has_export_button"]
            assert not any("copy/export" in w for w in result.warnings)
        finally:
            path.unlink()

    def test_export_button_passes_with_copy_word(self) -> None:
        html = VALID_HTML.replace("</body>", "<script>function copy() {}</script></body>")
        path = _write_tmp(html)
        try:
            result = validate_artifact(path, shape="prototype")
            assert result.checks["has_export_button"]
        finally:
            path.unlink()


@pytest.mark.slow
class TestCLIInterface:
    """Integration tests via subprocess."""

    def test_cli_valid_file(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result, code = run_validate(str(path))
            assert code == 0
            assert result["valid"] is True
        finally:
            path.unlink()

    def test_cli_invalid_file(self) -> None:
        path = _write_tmp("<p>not valid html</p>")
        try:
            result, code = run_validate(str(path))
            assert code == 1
            assert result["valid"] is False
        finally:
            path.unlink()

    def test_cli_file_not_found(self) -> None:
        result, code = run_validate("/nonexistent/file.html")
        assert code == 2
        assert result["valid"] is False
        assert any("not found" in e.lower() for e in result["errors"])

    def test_cli_compact_json(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            cmd = [sys.executable, SCRIPT, str(path), "--json-compact"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = proc.stdout.strip()
            assert "\n" not in output.rstrip("\n")
            parsed = json.loads(output)
            assert parsed["valid"] is True
        finally:
            path.unlink()

    def test_cli_shape_flag_editor(self) -> None:
        path = _write_tmp(VALID_HTML)
        try:
            result, code = run_validate(str(path))
            assert "has_export_button" not in result["checks"]

            # Now with --shape editor
            cmd = [sys.executable, SCRIPT, str(path), "--shape", "editor"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            shaped_result = json.loads(proc.stdout)
            assert "has_export_button" in shaped_result["checks"]
            assert shaped_result["checks"]["has_export_button"] is False
        finally:
            path.unlink()

    def test_cli_shape_flag_with_copy(self) -> None:
        path = _write_tmp(VALID_HTML_WITH_COPY)
        try:
            cmd = [sys.executable, SCRIPT, str(path), "--shape", "editor"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            assert proc.returncode == 0
            result = json.loads(proc.stdout)
            assert result["checks"]["has_export_button"] is True
        finally:
            path.unlink()


class TestBrokenInternalRefs:
    """REGRESSION GUARD: validator must catch href='#id' pointing to nonexistent ids.

    SKILL.md:237 has claimed this check exists for months — until 2026-05-20 audit it
    was prose-only. This test enforces the rule in the deterministic layer.
    """

    def _wrap(self, body: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><!-- assembled by html-artifact v1.1 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T</title><style>*{{}}</style></head>
<body>{body}</body></html>"""

    def test_valid_anchor_passes(self) -> None:
        path = _write_tmp(self._wrap('<a href="#section-1">Go</a><h2 id="section-1">Section</h2>'))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is True
            assert result.valid
        finally:
            path.unlink()

    def test_broken_anchor_fails(self) -> None:
        path = _write_tmp(self._wrap('<a href="#nonexistent">Broken</a>'))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is False
            assert any("nonexistent" in e for e in result.errors)
            assert not result.valid
        finally:
            path.unlink()

    def test_top_anchor_exempt(self) -> None:
        """`href='#top'` is a browser default; should not require explicit id."""
        path = _write_tmp(self._wrap('<a href="#top">Back to top</a>'))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is True
        finally:
            path.unlink()

    def test_no_anchors_passes(self) -> None:
        path = _write_tmp(self._wrap("<p>No anchors here.</p>"))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is True
        finally:
            path.unlink()

    def test_id_in_script_string_does_not_satisfy(self) -> None:
        """A string `'foo'` inside a <script> block must not falsely satisfy `href='#foo'`."""
        body = '<a href="#foo">Click</a><script>var x = "id=\\"foo\\"";</script>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is False
        finally:
            path.unlink()

    def test_multiple_broken_refs_all_reported(self) -> None:
        body = '<a href="#a">A</a><a href="#b">B</a><a href="#c">C</a>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["no_broken_internal_refs"] is False
            err = next(e for e in result.errors if "Broken internal refs" in e)
            assert "#a" in err
            assert "#b" in err
            assert "#c" in err
        finally:
            path.unlink()


class TestSvgAccessibility:
    """REGRESSION GUARD: every visible <svg> needs role='img' + aria-label.

    Captured 2026-05-20 audit: design-system.md required this for months but
    no validator enforced it. Decorative SVGs inside <button> are exempt
    because the button's aria-label provides the accessibility hook.
    """

    def _wrap(self, body: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><!-- assembled by html-artifact v1.1 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T</title><style>*{{}}</style></head>
<body>{body}</body></html>"""

    def test_svg_with_role_and_aria_label_passes(self) -> None:
        body = '<svg role="img" aria-label="Architecture diagram" viewBox="0 0 100 100"></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
            assert result.valid
        finally:
            path.unlink()

    def test_svg_missing_role_fails(self) -> None:
        body = '<svg aria-label="Diagram" viewBox="0 0 100 100"></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is False
            assert not result.valid
        finally:
            path.unlink()

    def test_svg_missing_aria_label_fails(self) -> None:
        body = '<svg role="img" viewBox="0 0 100 100"></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is False
        finally:
            path.unlink()

    def test_svg_in_button_exempt(self) -> None:
        """SVGs nested in <button> are decorative; the button carries accessibility."""
        body = (
            '<button class="theme-toggle" aria-label="Toggle theme">'
            '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="6"/></svg>'
            "</button>"
        )
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
        finally:
            path.unlink()

    def test_svg_with_role_presentation_exempt(self) -> None:
        body = '<svg role="presentation" viewBox="0 0 100 100"></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
        finally:
            path.unlink()

    def test_svg_with_aria_hidden_exempt(self) -> None:
        body = '<svg aria-hidden="true" viewBox="0 0 100 100"></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
        finally:
            path.unlink()

    def test_svg_with_aria_labelledby_passes(self) -> None:
        body = (
            '<svg role="img" aria-labelledby="caption-1" viewBox="0 0 100 100"></svg>'
            '<span id="caption-1">Architecture</span>'
        )
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
        finally:
            path.unlink()

    def test_no_svg_passes_trivially(self) -> None:
        path = _write_tmp(self._wrap("<p>No SVG here.</p>"))
        try:
            result = validate_artifact(path)
            assert result.checks["svg_accessibility"] is True
        finally:
            path.unlink()


class TestExternalSvgRefs:
    """REGRESSION GUARD: <image href='http...'> and <use href='http...'> must fail self-containment.

    SKILL.md:81 says diagrams are inline-SVG-only. Pre-fix, _check_self_contained
    only looked at <link> stylesheets and <script src>, missing the SVG vectors.
    """

    def _wrap(self, body: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><!-- assembled by html-artifact v1.1 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T</title><style>*{{}}</style></head>
<body>{body}</body></html>"""

    def test_external_image_href_fails(self) -> None:
        body = '<svg role="img" aria-label="x"><image href="https://example.com/x.png"/></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["self_contained"] is False
            assert any("<image href>" in e for e in result.errors)
        finally:
            path.unlink()

    def test_external_use_href_fails(self) -> None:
        body = '<svg role="img" aria-label="x"><use href="https://example.com/sprite.svg#icon"/></svg>'
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["self_contained"] is False
            assert any("<use href>" in e for e in result.errors)
        finally:
            path.unlink()

    def test_local_use_href_passes(self) -> None:
        """`<use href='#local-id'>` is the canonical inline-SVG sprite pattern; must pass."""
        body = (
            '<svg role="img" aria-label="x"><defs><circle id="dot" r="3"/></defs><use href="#dot" x="10" y="10"/></svg>'
        )
        path = _write_tmp(self._wrap(body))
        try:
            result = validate_artifact(path)
            assert result.checks["self_contained"] is True
        finally:
            path.unlink()


class TestNoImportantDisplayOverride:
    """REGRESSION GUARD: artifact `<style>` must not override `display` with !important.

    Captured 2026-05-20: deck artifact inlined `.slide-split { display: grid !important; }`
    which silently defeated `.slide { display: none }` and rendered every split slide
    simultaneously, producing a stacked-pages broken deck.
    """

    def _wrap_with_style(self, style_body: str, body: str = "<p>x</p>") -> str:
        return f"""<!DOCTYPE html>
<html><head><!-- assembled by html-artifact v1.1 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T</title><style>{style_body}</style></head>
<body>{body}</body></html>"""

    def test_clean_style_passes(self) -> None:
        css = ".foo { color: red; } .bar { display: grid; gap: 8px; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
            assert result.valid
        finally:
            path.unlink()

    def test_no_style_block_passes_trivially(self) -> None:
        # Build a minimal HTML with no <style> block at all.
        html = """<!DOCTYPE html>
<html><head><!-- assembled by html-artifact v1.1 -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>T</title></head><body><p>content</p></body></html>"""
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_display_grid_important_fails(self) -> None:
        css = ".slide-split { display: grid !important; grid-template-columns: 1fr 1fr; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is False
            assert any("slide-split" in e for e in result.errors)
            assert not result.valid
        finally:
            path.unlink()

    def test_display_block_important_fails(self) -> None:
        css = ".my-thing { display: block !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is False
            assert any("my-thing" in e for e in result.errors)
        finally:
            path.unlink()

    def test_no_print_allowlisted(self) -> None:
        """`.no-print { display: none !important; }` is base CSS — must NOT fire."""
        css = ".no-print { display: none !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_hidden_class_allowlisted(self) -> None:
        css = ".hidden { display: none !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_deck_not_active_defense_allowlisted(self) -> None:
        """`.slide-deck > .slide:not(.active) { display: none !important; }` is the
        deck shape's defense-in-depth rule — must NOT fire."""
        css = ".slide-deck > .slide:not(.active) { display: none !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_at_media_print_exempt(self) -> None:
        """!important inside `@media print` is structurally required — must NOT fire."""
        css = "@media print { .slide { display: flex !important; } .slide-nav { display: none !important; } }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_at_media_print_then_offender_outside(self) -> None:
        """An @media print block must not provide cover for a top-level offender."""
        css = "@media print { .slide { display: flex !important; } } .rogue { display: grid !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is False
            assert any("rogue" in e for e in result.errors)
        finally:
            path.unlink()

    def test_other_important_declarations_ok(self) -> None:
        """Only `display: <x> !important` is policed. `color: red !important` is allowed."""
        css = ".thing { color: red !important; background: blue !important; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()

    def test_commented_out_example_does_not_fire(self) -> None:
        """A CSS-commented example inside a docs-style artifact must not fire."""
        css = "/* example: .foo { display: grid !important; } */ .real { color: red; }"
        path = _write_tmp(self._wrap_with_style(css))
        try:
            result = validate_artifact(path)
            assert result.checks["no_important_display_override"] is True
        finally:
            path.unlink()
