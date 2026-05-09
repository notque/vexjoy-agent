#!/usr/bin/env python3
"""Deterministic HTML template assembler for html-artifact skill.

Given a shape, title, and optional components, reads CSS/JS template files
from the templates/ directory and injects them into the base HTML template.

Exit codes:
    0: template assembled successfully
    1: invalid shape, theme, or component
    2: base template not found

Usage:
    python3 skills/meta/html-artifact/scripts/assemble-template.py --shape spec --title "Auth Comparison"
    python3 skills/meta/html-artifact/scripts/assemble-template.py --shape spec --title "Test" --components tabs,collapsible
    python3 skills/meta/html-artifact/scripts/assemble-template.py --shape code-review --title "PR #42" --theme dark-focus
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

VALID_SHAPES = ("spec", "code-review", "prototype", "report", "editor", "data-viz", "diagram", "deck")
VALID_THEMES = ("birchline", "dark-focus", "interactive-warm", "minimal-document")
VALID_COMPONENTS = (
    "tabs",
    "collapsible",
    "drag-drop",
    "copy-button",
    "keyboard-nav",
    "theme-toggle",
    "filter",
    "slider",
    "scrollytelling",
)

SHAPE_DEFAULT_THEME: dict[str, str] = {
    "spec": "birchline",
    "code-review": "dark-focus",
    "prototype": "interactive-warm",
    "report": "birchline",
    "editor": "interactive-warm",
    "data-viz": "dark-focus",
    "diagram": "dark-focus",
    "deck": "dark-focus",
}

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
BASE_TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "base-template.html"


def _read_template(relpath: str) -> str:
    """Read a template file, returning empty string if not found."""
    p = TEMPLATES_DIR / relpath
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def assemble_template(
    shape: str,
    title: str,
    theme: str | None = None,
    components: list[str] | None = None,
) -> str:
    """Assemble an HTML template with theme, shape, and component CSS/JS.

    Args:
        shape: One of the valid artifact shapes.
        title: The title to inject into the template.
        theme: Optional theme override. Defaults to shape-specific theme.
        components: Optional list of component names to inject.

    Returns:
        The assembled HTML string.

    Raises:
        ValueError: If shape, theme, or component is invalid.
        FileNotFoundError: If base template is missing.
    """
    if shape not in VALID_SHAPES:
        raise ValueError(f"Invalid shape '{shape}'. Valid shapes: {', '.join(VALID_SHAPES)}")

    resolved_theme = theme if theme is not None else SHAPE_DEFAULT_THEME[shape]
    if resolved_theme not in VALID_THEMES:
        raise ValueError(f"Invalid theme '{resolved_theme}'. Valid themes: {', '.join(VALID_THEMES)}")

    if components:
        invalid = [c for c in components if c not in VALID_COMPONENTS]
        if invalid:
            raise ValueError(
                f"Invalid component(s): {', '.join(invalid)}. Valid components: {', '.join(VALID_COMPONENTS)}"
            )

    template = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Inject title
    html = template.replace("<!-- TITLE -->", title)

    # Build CSS injection: reset + theme + shape + components
    css_parts: list[str] = []

    # 1. Base reset
    reset_css = _read_template("base-reset.css")
    if reset_css:
        css_parts.append(reset_css)

    # 2. Theme CSS (replaces the base template's Birchline tokens)
    theme_css = _read_template(f"themes/{resolved_theme}.css")
    if theme_css:
        css_parts.append(theme_css)

    # 3. Shape-specific CSS
    shape_css = _read_template(f"shapes/{shape}.css")
    if shape_css:
        css_parts.append(shape_css)

    # 4. Component CSS
    if components:
        for comp in components:
            comp_css = _read_template(f"components/{comp}.css")
            if comp_css:
                css_parts.append(comp_css)

    # Build JS injection: components only
    js_parts: list[str] = []
    if components:
        for comp in components:
            comp_js = _read_template(f"components/{comp}.js")
            if comp_js:
                js_parts.append(comp_js)

    # Inject CSS after the STYLES placeholder
    if css_parts:
        css_block = "\n".join(css_parts)
        html = html.replace(
            "/* <!-- STYLES --> */",
            css_block + "\n    /* <!-- STYLES --> */",
        )

    # Inject JS after the SCRIPTS placeholder
    if js_parts:
        js_block = "\n".join(js_parts)
        html = html.replace(
            "/* <!-- SCRIPTS --> */",
            js_block + "\n    /* <!-- SCRIPTS --> */",
        )

    return html


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Assemble an HTML artifact template.")
    parser.add_argument("--shape", required=True, help="Artifact shape.")
    parser.add_argument("--title", required=True, help="Title for the artifact.")
    parser.add_argument(
        "--theme",
        default=None,
        help="Theme override (birchline, dark-focus, interactive-warm, minimal-document).",
    )
    parser.add_argument(
        "--components",
        default=None,
        help="Comma-separated component names to inject (tabs, collapsible, drag-drop, etc.).",
    )
    args = parser.parse_args()

    if args.shape not in VALID_SHAPES:
        sys.stderr.write(f"Error: Invalid shape '{args.shape}'. Valid shapes: {', '.join(VALID_SHAPES)}\n")
        sys.exit(1)

    if args.theme is not None and args.theme not in VALID_THEMES:
        sys.stderr.write(f"Error: Invalid theme '{args.theme}'. Valid themes: {', '.join(VALID_THEMES)}\n")
        sys.exit(1)

    comp_list: list[str] | None = None
    if args.components:
        comp_list = [c.strip() for c in args.components.split(",") if c.strip()]
        invalid = [c for c in comp_list if c not in VALID_COMPONENTS]
        if invalid:
            sys.stderr.write(
                f"Error: Invalid component(s): {', '.join(invalid)}. Valid: {', '.join(VALID_COMPONENTS)}\n"
            )
            sys.exit(1)

    try:
        html = assemble_template(args.shape, args.title, args.theme, comp_list)
    except FileNotFoundError:
        sys.stderr.write(f"Error: Base template not found at {BASE_TEMPLATE_PATH}\n")
        sys.exit(2)

    sys.stdout.write(html)


if __name__ == "__main__":
    main()
