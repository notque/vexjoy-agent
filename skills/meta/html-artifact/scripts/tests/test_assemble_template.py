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

    def test_birchline_theme_tokens(self) -> None:
        html = assemble_template("spec", "Test")
        # Birchline theme should inject its tokens
        assert "--color-primary: #D97757" in html

    def test_dark_focus_theme(self) -> None:
        html = assemble_template("code-review", "Test")
        assert "Dark Focus Theme" in html
        assert "--color-primary: #64B5F6" in html

    def test_interactive_warm_theme(self) -> None:
        html = assemble_template("prototype", "Test")
        assert "Interactive Warm Theme" in html
        assert "--color-primary: #5B8DEF" in html

    def test_minimal_document_theme(self) -> None:
        html = assemble_template("spec", "Test", theme="minimal-document")
        assert "Minimal Document Theme" in html
        assert "Georgia" in html

    def test_theme_override(self) -> None:
        # spec defaults to birchline, override to dark-focus
        html = assemble_template("spec", "Test", theme="dark-focus")
        assert "Dark Focus Theme" in html
        assert "--color-primary: #64B5F6" in html

    def test_shape_default_themes(self) -> None:
        expected = {
            "spec": "birchline",
            "code-review": "dark-focus",
            "prototype": "interactive-warm",
            "report": "birchline",
            "editor": "interactive-warm",
            "data-viz": "dark-focus",
            "diagram": "dark-focus",
            "deck": "dark-focus",
        }
        for shape, theme in expected.items():
            html = assemble_template(shape, "Test")
            if theme == "birchline":
                assert "--color-primary: #D97757" in html, f"{shape} should use birchline"
            elif theme == "dark-focus":
                assert "--color-primary: #64B5F6" in html, f"{shape} should use dark-focus"
            elif theme == "interactive-warm":
                assert "--color-primary: #5B8DEF" in html, f"{shape} should use interactive-warm"

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

    # --- New shape tests ---

    def test_diagram_shape_valid(self) -> None:
        html = assemble_template("diagram", "Architecture")
        assert "<title>Architecture</title>" in html
        assert "Diagram Shape" in html

    def test_deck_shape_valid(self) -> None:
        html = assemble_template("deck", "Presentation")
        assert "<title>Presentation</title>" in html
        assert "Slide Deck Shape" in html

    # --- Component injection tests ---

    def test_components_tabs(self) -> None:
        html = assemble_template("spec", "Test", components=["tabs"])
        assert "Tabs Component" in html
        assert ".tab-bar" in html
        assert "classList.add('active')" in html  # JS injected

    def test_components_collapsible(self) -> None:
        html = assemble_template("report", "Test", components=["collapsible"])
        assert "Collapsible Component" in html
        assert ".accordion-trigger" in html
        assert "aria-expanded" in html  # JS injected

    def test_components_multiple(self) -> None:
        html = assemble_template("spec", "Test", components=["tabs", "collapsible"])
        assert "Tabs Component" in html
        assert "Collapsible Component" in html

    def test_components_none(self) -> None:
        """No components = no component CSS/JS injected."""
        html = assemble_template("spec", "Test")
        assert "Tabs Component" not in html
        assert "Drag and Drop Component" not in html

    def test_components_empty_list(self) -> None:
        html = assemble_template("spec", "Test", components=[])
        assert "Tabs Component" not in html

    def test_invalid_component_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid component"):
            assemble_template("spec", "Test", components=["nonexistent"])

    def test_components_drag_drop(self) -> None:
        html = assemble_template("editor", "Test", components=["drag-drop"])
        assert "Drag and Drop Component" in html
        assert ".drag-item" in html

    def test_components_copy_button(self) -> None:
        html = assemble_template("spec", "Test", components=["copy-button"])
        assert "Copy Button Component" in html
        assert "copyToClipboard" in html

    def test_components_theme_toggle(self) -> None:
        html = assemble_template("report", "Test", components=["theme-toggle"])
        assert "Theme Toggle Component" in html
        assert "toggleTheme" in html

    def test_components_filter(self) -> None:
        html = assemble_template("data-viz", "Test", components=["filter"])
        assert "Filter Component" in html
        assert "setupFilter" in html

    def test_components_slider(self) -> None:
        html = assemble_template("prototype", "Test", components=["slider"])
        assert "Slider Component" in html
        assert 'input[type="range"]' in html

    def test_components_keyboard_nav(self) -> None:
        html = assemble_template("deck", "Test", components=["keyboard-nav"])
        assert "Keyboard Navigation Component" in html
        assert "setupKeyNav" in html

    # --- Shape CSS injection tests ---

    def test_shape_css_spec(self) -> None:
        html = assemble_template("spec", "Test")
        assert ".comparison-grid" in html
        assert ".approach-card" in html

    def test_shape_css_code_review(self) -> None:
        html = assemble_template("code-review", "Test")
        assert ".review-layout" in html
        assert ".diff-file" in html

    def test_shape_css_prototype(self) -> None:
        html = assemble_template("prototype", "Test")
        assert ".prototype-layout" in html
        assert ".controls-panel" in html

    def test_shape_css_report(self) -> None:
        html = assemble_template("report", "Test")
        assert ".tldr" in html
        assert ".metric-row" in html

    def test_shape_css_editor(self) -> None:
        html = assemble_template("editor", "Test")
        assert ".export-bar" in html
        assert ".kanban" in html

    def test_shape_css_data_viz(self) -> None:
        html = assemble_template("data-viz", "Test")
        assert ".chart" in html
        assert ".legend" in html

    def test_shape_css_diagram(self) -> None:
        html = assemble_template("diagram", "Test")
        assert ".diagram-container" in html
        assert ".figure-grid" in html

    def test_shape_css_deck(self) -> None:
        html = assemble_template("deck", "Test")
        assert ".slide-deck" in html
        assert ".progress-bar" in html

    # --- Base reset injection test ---

    def test_base_reset_always_included(self) -> None:
        html = assemble_template("spec", "Test")
        assert "box-sizing: border-box" in html
        assert "prefers-reduced-motion" in html


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
        assert "Dark Focus Theme" in proc.stdout

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

    def test_cli_with_components(self) -> None:
        cmd = [
            sys.executable,
            SCRIPT,
            "--shape",
            "spec",
            "--title",
            "Test",
            "--components",
            "tabs,collapsible",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert "Tabs Component" in proc.stdout
        assert "Collapsible Component" in proc.stdout

    def test_cli_invalid_component_exits_1(self) -> None:
        cmd = [
            sys.executable,
            SCRIPT,
            "--shape",
            "spec",
            "--title",
            "Test",
            "--components",
            "nonexistent",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1

    def test_cli_diagram_shape(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "diagram", "--title", "Architecture"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert ".diagram-container" in proc.stdout

    def test_cli_deck_shape(self) -> None:
        cmd = [sys.executable, SCRIPT, "--shape", "deck", "--title", "Slides"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert ".slide-deck" in proc.stdout
