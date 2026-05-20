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
