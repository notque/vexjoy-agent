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
        assert "--color-primary: #3D6FD9" in html

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
                assert "--color-primary: #3D6FD9" in html, f"{shape} should use interactive-warm"

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
        assert "<body" in html
        assert "</body>" in html

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

    def test_components_scrollytelling(self) -> None:
        html = assemble_template("report", "Test", components=["scrollytelling"])
        assert "Scrollytelling Component" in html
        assert ".reveal" in html
        assert "IntersectionObserver" in html  # JS injected

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

    # --- data-shape attribute tests ---

    def test_body_has_data_shape_attribute(self) -> None:
        for shape in ("spec", "code-review", "prototype", "report", "editor", "data-viz", "diagram", "deck"):
            html = assemble_template(shape, "Test")
            assert f'<body data-shape="{shape}">' in html, shape

    def test_data_shape_appears_exactly_once(self) -> None:
        html = assemble_template("report", "Test")
        # The literal <body> tag should be replaced; <body data-shape=...> appears once.
        assert html.count('<body data-shape="report">') == 1
        # Nothing should leave a bare <body> in place.
        assert "<body>" not in html

    # --- Per-shape print CSS injection tests ---

    def test_shape_print_css_injected(self) -> None:
        """Every shape ships its own print stylesheet (a missing file would silently fall back)."""
        for shape, marker in (
            ("deck", "Deck Print Stylesheet"),
            ("spec", "Spec Print Stylesheet"),
            ("report", "Report Print Stylesheet"),
            ("editor", "Editor Print Stylesheet"),
            ("code-review", "Code Review Print Stylesheet"),
            ("prototype", "Prototype Print Stylesheet"),
            ("data-viz", "Data-Viz Print Stylesheet"),
            ("diagram", "Diagram Print Stylesheet"),
        ):
            html = assemble_template(shape, "Test")
            assert marker in html, shape
            assert "@media print" in html

    def test_print_css_fallback_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no shape-specific print CSS exists, fall back to default-print.css.

        Implementation detail: simulate by pointing _read_template at a fake
        shape that is otherwise valid. We accept a real shape but stub out
        the per-shape print read so the assembler must fall back.
        """
        # Save the real reader and stub it so the per-shape print read returns
        # nothing while every other read passes through.
        real_reader = assemble_mod._read_template

        def fake_reader(relpath: str) -> str:
            if relpath.startswith("print/") and relpath != "print/default-print.css":
                return ""  # force fallback
            return real_reader(relpath)

        monkeypatch.setattr(assemble_mod, "_read_template", fake_reader)
        html = assemble_template("spec", "Test")
        assert "Default Print Stylesheet" in html
        # Sanity: the spec-print marker should NOT be present because we suppressed it.
        assert "Spec Print Stylesheet" not in html


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


TEMPLATES = Path(__file__).parent.parent.parent / "templates"
slop = import_module("css_slop_rules")


def _tokens(css: str) -> dict[str, str]:
    """Map custom properties in a CSS file to their values, resolving var() chains."""
    import re

    raw = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css))

    def resolve(value: str, depth: int = 0) -> str:
        m = re.fullmatch(r"var\((--[\w-]+)(?:,[^)]*)?\)", value.strip())
        if m and depth < 10 and m.group(1) in raw:
            return resolve(raw[m.group(1)], depth + 1)
        return value.strip()

    return {k: resolve(v) for k, v in raw.items()}


class TestThemeAccentContrast:
    """--accent-text colors small text, so it must clear 4.5:1 on every theme surface."""

    @pytest.mark.parametrize("theme", ["birchline", "dark-focus", "interactive-warm", "minimal-document"])
    def test_accent_text_passes_aa(self, theme: str) -> None:
        tokens = _tokens((TEMPLATES / "themes" / f"{theme}.css").read_text(encoding="utf-8"))
        fg = tokens["--accent-text"]
        for bg in ("--bg-page", "--bg-surface", "--bg-muted", "--bg-card"):
            ratio = slop.contrast_ratio(fg, tokens[bg])
            assert ratio is not None and ratio >= 4.5, f"{theme} {fg} on {bg} {tokens[bg]}: {ratio}"

    def test_toggle_dark_accent_text_passes_aa(self) -> None:
        # The dark block must reset --accent-text; birchline's dark clay fails on dark surfaces.
        tokens = _tokens((TEMPLATES / "components" / "theme-toggle.css").read_text(encoding="utf-8"))
        for bg in ("--bg-page", "--bg-surface", "--bg-muted", "--bg-card"):
            assert slop.contrast_ratio(tokens["--accent-text"], tokens[bg]) >= 4.5

    def test_birchline_brand_accent_kept_for_fills(self) -> None:
        tokens = _tokens((TEMPLATES / "themes" / "birchline.css").read_text(encoding="utf-8"))
        assert tokens["--accent"] == "#D97757"
        assert slop.contrast_ratio(tokens["--accent"], tokens["--bg-page"]) < 3.0

    def test_small_accent_text_uses_text_token(self) -> None:
        spec = (TEMPLATES / "shapes" / "spec.css").read_text(encoding="utf-8")
        assert "color: var(--accent-text, var(--accent))" in spec


THEMES = ["birchline", "dark-focus", "interactive-warm", "minimal-document"]


def _dark_tokens() -> dict[str, str]:
    import re

    css = (TEMPLATES / "components" / "theme-toggle.css").read_text(encoding="utf-8")
    block = re.search(r'\[data-theme="dark"\] \{([^}]*)\}', css)
    assert block is not None
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1)))


def _theme_variants() -> dict[str, dict[str, str]]:
    """Every theme alone and with the theme-toggle dark block layered on top, tokens resolved."""
    import re

    variants = {}
    for theme in THEMES:
        css = re.sub(r"/\*.*?\*/", "", (TEMPLATES / "themes" / f"{theme}.css").read_text(encoding="utf-8"), flags=re.S)
        raw = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css))
        for name, layer in ((theme, raw), (theme + "+dark", {**raw, **_dark_tokens()})):
            variants[name] = _tokens("".join(f"{k}: {v};" for k, v in layer.items()))
    return variants


def _resolve_color(value: str, tokens: dict[str, str]) -> str | None:
    """Resolve a CSS color value (var() with optional fallback, hex, or white) to #RRGGBB."""
    import re

    value = value.strip()
    m = re.fullmatch(r"var\((--[\w-]+)(?:\s*,\s*(.+))?\)", value)
    if m:
        if m.group(1) in tokens:
            return _resolve_color(tokens[m.group(1)], tokens)
        return _resolve_color(m.group(2), tokens) if m.group(2) else None
    value = "#FFFFFF" if value.lower() == "white" else value
    return value.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None


def _oklch_hue(hex_color: str) -> float:
    import math

    def lin(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(hex_color[i : i + 2], 16)) for i in (1, 3, 5))
    lms = [
        (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3),
        (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3),
        (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3),
    ]
    a = 1.9779984951 * lms[0] - 2.4285922050 * lms[1] + 0.4505937099 * lms[2]
    bb = 0.0259040371 * lms[0] + 0.7827717662 * lms[1] - 0.8086757660 * lms[2]
    return math.degrees(math.atan2(bb, a)) % 360


class TestAccentFillContrast:
    """Buttons, active chips, and selected states put white labels on --accent-fill: 4.5:1 in every theme."""

    VARIANTS = _theme_variants()

    @pytest.mark.parametrize("variant", sorted(VARIANTS))
    @pytest.mark.parametrize("fill", ["--accent-fill", "--accent-fill-hover"])
    def test_white_on_fill_passes_aa(self, variant: str, fill: str) -> None:
        tokens = self.VARIANTS[variant]
        assert tokens["--on-accent-fill"].upper() == "#FFFFFF"
        ratio = slop.contrast_ratio(tokens["--on-accent-fill"], tokens[fill])
        assert ratio is not None and ratio >= 4.5, f"{variant} white on {fill} {tokens[fill]}: {ratio}"

    def test_birchline_fill_stays_clay(self) -> None:
        tokens = self.VARIANTS["birchline"]
        assert tokens["--accent"] == "#D97757"
        assert tokens["--accent-fill"] != tokens["--accent"]
        for fill in ("--accent-fill", "--accent-fill-hover"):
            assert abs(_oklch_hue(tokens[fill]) - _oklch_hue(tokens["--accent"])) < 3.0

    def test_every_white_on_fill_rule_passes(self) -> None:
        """Scan every template rule that sets both a background and white text, in every theme and dark mode."""
        import re

        checked: set[str] = set()
        failures = []
        for sub in ("components", "shapes", "themes"):
            for path in sorted((TEMPLATES / sub).glob("*.css")):
                css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
                for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
                    bg = re.search(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", body)
                    fg = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", body)
                    if not (bg and fg):
                        continue
                    for variant, tokens in self.VARIANTS.items():
                        fill, text = _resolve_color(bg.group(1), tokens), _resolve_color(fg.group(1), tokens)
                        if fill is None or text != "#FFFFFF":
                            continue
                        checked.add(selector.strip())
                        ratio = slop.contrast_ratio(text, fill)
                        if ratio is None or ratio < 4.5:
                            failures.append(f"{path.name} {selector.strip()} [{variant}] white on {fill}: {ratio:.2f}")
        assert {".tag-btn.active", ".btn-primary", ".export-btn"} <= checked
        assert not failures, "\n".join(failures)


class TestInteractiveWarmButtons:
    """One primary per region: bare buttons are neutral; primary is opt-in."""

    CSS = (TEMPLATES / "themes" / "interactive-warm.css").read_text(encoding="utf-8")

    def test_bare_button_not_primary(self) -> None:
        import re

        base = re.search(r":where\(button, \[role=\"button\"\]\) \{([^}]*)\}", self.CSS)
        assert base is not None
        assert "--color-primary" not in base.group(1)
        assert not re.search(r"^button, \[role=\"button\"\] \{", self.CSS, re.MULTILINE)

    @pytest.mark.parametrize("variant", [".btn-primary", ".btn-secondary", ".btn-outline", ".btn-ghost"])
    def test_variants_defined(self, variant: str) -> None:
        assert f"{variant} {{" in self.CSS
        assert f"{variant}:hover" in self.CSS
