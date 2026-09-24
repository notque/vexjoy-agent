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


SURFACES = ("--bg-page", "--bg-surface", "--bg-card", "--bg-muted")
STATUS = ("--color-success", "--color-warning", "--color-danger")


def _sub_vars(value: str, tokens: dict[str, str]) -> str:
    """Replace every var() in a value with its token, or its fallback when the token is unset."""
    import re

    for _ in range(12):
        m = re.search(r"var\((--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)", value)
        if not m:
            break
        value = value[: m.start()] + tokens.get(m.group(1), m.group(2) or "") + value[m.end() :]
    return value.strip()


def _rgba(value: str, tokens: dict[str, str]) -> tuple[float, float, float, float] | None:
    """Parse a CSS color (var(), hex, white/black/transparent, rgb[a](), color-mix in srgb) to RGBA."""
    import re

    value = _sub_vars(value, tokens).lower()
    named = {"white": "#ffffff", "black": "#000000"}
    value = named.get(value, value)
    if value in ("transparent", "none"):
        return (0.0, 0.0, 0.0, 0.0)
    if m := re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", value):
        h = m.group(1) if len(m.group(1)) == 6 else "".join(c * 2 for c in m.group(1))
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    if m := re.fullmatch(r"rgba?\(([^)]*)\)", value):
        parts = [float(p) for p in re.split(r"[,\s/]+", m.group(1).strip()) if p]
        return (parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else 1.0)
    if m := re.fullmatch(r"color-mix\(in srgb,\s*(.+?)\s+(\d+(?:\.\d+)?)%\s*,\s*(.+)\)", value):
        a, b, p = _rgba(m.group(1), tokens), _rgba(m.group(3), tokens), float(m.group(2)) / 100
        if a is None or b is None:
            return None
        alpha = a[3] * p + b[3] * (1 - p)
        if alpha == 0:
            return (0.0, 0.0, 0.0, 0.0)
        mixed = tuple((a[i] * a[3] * p + b[i] * b[3] * (1 - p)) / alpha for i in range(3))
        return (*mixed, alpha)
    return None


def _over(top: tuple[float, ...], base: tuple[float, ...]) -> tuple[float, float, float, float]:
    return (*(top[i] * top[3] + base[i] * (1 - top[3]) for i in range(3)), 1.0)


def _hex(c: tuple[float, ...]) -> str:
    return "#" + "".join(f"{round(x):02X}" for x in c[:3])


def _decl(body: str, prop: str) -> str | None:
    """Last value of a property in a declaration block (last one wins, as in the cascade)."""
    import re

    found = re.findall(rf"(?:^|;)\s*{prop}\s*:\s*([^;]+)", body)
    return found[-1].strip() if found else None


def _floor(selector: str, body: str, tokens: dict[str, str]) -> float:
    """4.5:1 for normal text; 3:1 when the CSS makes it large text or a glyph-only icon."""
    import re

    size, weight = None, 400
    for prop in ("font", "font-size"):
        if value := _decl(body, prop):
            value = _sub_vars(value, tokens)
            if m := re.search(r"(?:(\d{3})\s+)?(\d+(?:\.\d+)?)px", value):
                size = float(m.group(2))
                weight = int(m.group(1)) if m.group(1) else weight
            elif m := re.search(r"(\d+(?:\.\d+)?)rem", value):
                size = float(m.group(1)) * 16
    if (fw := _decl(body, "font-weight")) and fw.isdigit():
        weight = int(fw)
    large = size is not None and (size >= 24 or (size >= 18.66 and weight >= 700))
    content = _decl(body, "content")
    glyphs = re.sub(r"\\[0-9a-fA-F]{1,6}\s?", "#", content.strip("'\"")) if content else ""
    icon = "::" in selector and content is not None and not re.search(r"[A-Za-z0-9]|attr\(", glyphs)
    return 3.0 if large or icon else 4.5


def _css_of(path: Path) -> str:
    import re

    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        text = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


_STATE = r":(?:hover|active|focus|focus-visible|focus-within|checked)\b"


def _rules(css: str) -> dict[str, str]:
    """Map each single selector to its merged declarations; comma lists are split."""
    import re

    rules: dict[str, str] = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for selector in re.split(r",(?![^()]*\))", selectors):
            selector = " ".join(selector.split())
            if selector and not selector.startswith("@"):
                rules[selector] = rules.get(selector, "") + ";" + body
    return rules


def _cascaded(selector: str, rules: dict[str, str]) -> str:
    """A rule's body layered over its base rules, so a :hover or .x .child rule keeps the base color."""
    import re

    last = re.split(r"\s*[ >+~]\s*", selector)[-1]
    bases = [re.sub(_STATE, "", last), re.sub(_STATE, "", selector)]
    chain = [b for i, b in enumerate(bases) if b != selector and b in rules and b not in bases[:i]]
    return ";".join(rules[b] for b in chain) + ";" + rules[selector]


def _non_text(selector: str, body: str) -> bool:
    """True when the CSS makes the element a graphic: an empty pseudo-element, a range-input part,
    or a box sized by height or inset with no typography."""
    import re

    if (_decl(body, "content") or "").strip() in ("''", '""'):
        return True
    if re.search(r"::-(?:webkit|moz)-|input\[type=\"range\"\]$", selector):
        return True
    shaped = _decl(body, "height") or _decl(body, "inset")
    return bool(shaped) and not (_decl(body, "font") or _decl(body, "font-size") or _decl(body, "content"))


def _text_pairs(css: str, variants: dict[str, dict[str, str]], surfaces: tuple[str, ...] = SURFACES):
    """Yield (selector, variant, fg, bg, ratio, floor) for every text color and background a rule can pair.

    A rule with both color and background pairs them (a translucent background is composited over each
    surface). A rule with only a color is checked on every theme surface it may sit on. A rule with only
    a background is checked with the inherited --text-primary. State rules inherit from their base rule.
    Disabled states are exempt (WCAG 1.4.3), and so are graphics with no text (see _non_text).
    """
    rules = _rules(css)
    for selector in rules:
        if "disabled" in selector or ":root" in selector:
            continue
        body = _cascaded(selector, rules)
        own = rules[selector]
        if not (_decl(own, "color") or _decl(own, "background(?:-color)?")) or _non_text(selector, body):
            continue
        fg_value, bg_value = _decl(body, "color"), _decl(body, "background(?:-color)?")
        for variant, tokens in variants.items():
            fg = _rgba(fg_value or "var(--text-primary)", tokens)
            bases = [b for s in surfaces if s in tokens and (b := _rgba(tokens[s], tokens))]
            bg = _rgba(bg_value, tokens) if bg_value else None
            if fg is None or fg[3] == 0 or (bg_value and bg is None) or (bg and bg[3] == 0 and not fg_value):
                continue
            backs = [bg] if bg and bg[3] == 1 else [_over(bg, b) for b in bases] if bg and bg[3] > 0 else bases
            floor = _floor(selector, body, tokens)
            for back in backs:
                text = _over(fg, back) if fg[3] < 1 else fg
                yield selector, variant, _hex(text), _hex(back), slop.contrast_ratio(_hex(text), _hex(back)), floor


def _scan_files() -> list[Path]:
    files = [TEMPLATES / "base-reset.css"]
    for sub in ("components", "shapes", "themes", "print"):
        files += sorted((TEMPLATES / sub).glob("*.css"))
    return files


def _failures(
    files: list[Path], variants: dict[str, dict[str, str]], surfaces=SURFACES
) -> dict[tuple[str, str], float]:
    """Worst ratio per (file selector, variant) that falls below its floor."""
    worst: dict[tuple[str, str], float] = {}
    for path in files:
        for selector, variant, _fg, _bg, ratio, floor in _text_pairs(_css_of(path), variants, surfaces):
            if ratio < floor:
                key = (f"{path.name} {selector}", variant)
                worst[key] = min(ratio, worst.get(key, ratio))
    return worst


class TestTextContrast:
    """Every text color on every background it can sit on, in every theme, with and without the dark toggle."""

    VARIANTS = _theme_variants()

    @pytest.mark.parametrize("variant", sorted(VARIANTS))
    def test_text_tokens_clear_aa_on_every_surface(self, variant: str) -> None:
        tokens = self.VARIANTS[variant]
        for fg in ("--text-primary", "--text-secondary", "--text-muted", "--accent-text", *STATUS):
            for bg in SURFACES:
                ratio = slop.contrast_ratio(tokens[fg], tokens[bg])
                assert ratio >= 4.5, f"{variant} {fg} {tokens[fg]} on {bg} {tokens[bg]}: {ratio:.2f}"

    @pytest.mark.parametrize("variant", sorted(VARIANTS))
    def test_status_text_clears_aa_on_its_own_tint(self, variant: str) -> None:
        # Badges put status text on a 12-15% tint of the same color over a surface.
        tokens = self.VARIANTS[variant]
        for status in STATUS:
            for pct in (12, 15):
                for surface in SURFACES:
                    back = _hex(
                        _over(
                            _rgba(f"color-mix(in srgb, var({status}) {pct}%, transparent)", tokens),
                            _rgba(tokens[surface], tokens),
                        )
                    )
                    ratio = slop.contrast_ratio(tokens[status], back)
                    assert ratio >= 4.5, f"{variant} {status} on {pct}% tint over {surface}: {ratio:.2f}"

    def test_toggle_dark_sets_status_colors(self) -> None:
        # Light-theme status colors are too dark for the toggle's navy surfaces.
        assert set(STATUS) <= set(_dark_tokens())

    def test_every_rule_pair_passes(self) -> None:
        failures = _failures(_scan_files(), self.VARIANTS)
        assert not failures, "\n".join(f"{k[0]} [{k[1]}]: {v:.2f}" for k, v in sorted(failures.items()))

    def test_scan_covers_known_pairs(self) -> None:
        seen = {sel for path in _scan_files() for sel, *_ in _text_pairs(_css_of(path), self.VARIANTS)}
        assert {".key-nav-counter", ".copy-svg-btn", ".severity-badge.safe", ".tab", ".risk-level.med"} <= seen

    def test_scan_catches_old_muted_tokens(self) -> None:
        # Before this fix --text-muted was #8C8CA8 in dark mode and #888888 in minimal-document.
        old = {
            "dark-focus": {**self.VARIANTS["dark-focus"], "--text-muted": "#8C8CA8"},
            "minimal-document": {**self.VARIANTS["minimal-document"], "--text-muted": "#888888"},
        }
        files = [TEMPLATES / "components" / "keyboard-nav.css", TEMPLATES / "shapes" / "diagram.css"]
        failures = _failures(files, old)
        for name in ("keyboard-nav.css .key-nav-counter", "diagram.css .copy-svg-btn"):
            assert round(failures[(name, "dark-focus")], 2) == 4.11
            assert round(failures[(name, "minimal-document")], 2) == 3.33

    def test_floor_relaxes_only_for_large_text_and_icons(self) -> None:
        tokens = self.VARIANTS["birchline"]
        assert _floor(".x", "font: var(--type-caption)", tokens) == 4.5
        assert _floor(".x", "font-size: var(--type-h2); font-weight: 700", tokens) == 3.0
        assert _floor(".x", "font-size: 20px; font-weight: 700", tokens) == 3.0
        assert _floor(".x", "font-size: 20px", tokens) == 4.5
        assert _floor("summary::after", "content: '\\25B8'; font-size: 18px", tokens) == 3.0
        assert _floor("a::after", 'content: " (" attr(href) ")"', tokens) == 4.5

    @pytest.mark.parametrize("path", sorted((TEMPLATES / "saved").glob("*.html")), ids=lambda p: p.stem)
    def test_saved_templates_pass(self, path: Path) -> None:
        import re

        css = _css_of(path)
        raw: dict[str, str] = {}
        for block in re.findall(r":root\s*\{([^}]*)\}", css):
            raw.update(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block))
        tokens = _tokens("".join(f"{k}: {v};" for k, v in raw.items()))
        surfaces = tuple(s for s in ("--bg", "--surface", *SURFACES) if s in tokens)
        failures = _failures([path], {path.stem: tokens}, surfaces)
        assert not failures, "\n".join(f"{k[0]}: {v:.2f}" for k, v in sorted(failures.items()))
