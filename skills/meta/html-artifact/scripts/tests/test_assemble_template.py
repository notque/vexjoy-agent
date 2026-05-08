"""Tests for assemble-template.py — deterministic HTML template assembler."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "assemble-template.py")

# --- Import module directly for unit tests ---
sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

assemble_mod = import_module("assemble-template")
assemble_template = assemble_mod.assemble_template


class TestAssembleTemplateDirect:
    """Unit tests calling assemble_template() directly."""

    def test_title_injected(self) -> None:
        html = assemble_template("spec", "My Title")
        assert "<title>My Title</title>" in html

    def test_birchline_no_extra_css(self) -> None:
        html = assemble_template("spec", "Test")
        # Birchline is the default in base template — no theme override block
        assert "Dark Focus Theme Override" not in html
        assert "Interactive Warm Theme Override" not in html

    def test_dark_focus_theme(self) -> None:
        html = assemble_template("code-review", "Test")
        assert "Dark Focus Theme Override" in html
        assert "--color-ivory: #1a1a2e" in html

    def test_interactive_warm_theme(self) -> None:
        html = assemble_template("prototype", "Test")
        assert "Interactive Warm Theme Override" in html
        assert "--color-primary: #5B8DEF" in html

    def test_minimal_document_theme(self) -> None:
        html = assemble_template("spec", "Test", theme="minimal-document")
        assert "Minimal Document Theme Override" in html
        assert "Georgia" in html

    def test_theme_override(self) -> None:
        # spec defaults to birchline, override to dark-focus
        html = assemble_template("spec", "Test", theme="dark-focus")
        assert "Dark Focus Theme Override" in html

    def test_shape_default_themes(self) -> None:
        expected = {
            "spec": "birchline",
            "code-review": "dark-focus",
            "prototype": "interactive-warm",
            "report": "birchline",
            "editor": "interactive-warm",
            "data-viz": "dark-focus",
        }
        for shape, theme in expected.items():
            html = assemble_template(shape, "Test")
            if theme == "birchline":
                assert "Theme Override" not in html, f"{shape} should use birchline (no override)"
            elif theme == "dark-focus":
                assert "Dark Focus Theme Override" in html, f"{shape} should use dark-focus"
            elif theme == "interactive-warm":
                assert "Interactive Warm Theme Override" in html, f"{shape} should use interactive-warm"

    def test_invalid_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid shape"):
            assemble_template("invalid", "Test")

    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid theme"):
            assemble_template("spec", "Test", theme="neon")

    def test_output_is_valid_html_structure(self) -> None:
        html = assemble_template("report", "Report Title")
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_html_entities_in_title(self) -> None:
        html = assemble_template("spec", "A & B <comparison>")
        assert "<title>A & B <comparison></title>" in html

    def test_deterministic_same_input_same_output(self) -> None:
        results = [assemble_template("data-viz", "Dashboard") for _ in range(5)]
        assert all(r == results[0] for r in results)


@pytest.mark.slow
class TestCLIInterface:
    """Integration tests via subprocess."""

    def test_cli_basic(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "spec", "--title", "Auth Comparison"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert "<title>Auth Comparison</title>" in proc.stdout

    def test_cli_with_theme(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "spec", "--title", "Test", "--theme", "dark-focus"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert "Dark Focus Theme Override" in proc.stdout

    def test_cli_invalid_shape_exits_1(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "banana", "--title", "Test"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1

    def test_cli_invalid_theme_exits_1(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "spec", "--title", "Test", "--theme", "neon"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1

    def test_cli_output_is_complete_html(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "report", "--title", "Weekly Report"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert "<!DOCTYPE html>" in proc.stdout
        assert "</html>" in proc.stdout
