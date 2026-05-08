#!/usr/bin/env python3
"""Deterministic HTML template assembler for html-artifact skill.

Given a shape and title, injects the correct theme CSS into the base template
and outputs a ready-to-fill HTML skeleton to stdout.

Exit codes:
    0: template assembled successfully
    1: invalid shape or theme
    2: base template not found

Usage:
    python3 skills/meta/html-artifact/scripts/assemble-template.py --shape spec --title "Auth Comparison"
    python3 skills/meta/html-artifact/scripts/assemble-template.py --shape code-review --title "PR #42" --theme dark-focus
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

VALID_SHAPES = ("spec", "code-review", "prototype", "report", "editor", "data-viz")
VALID_THEMES = ("birchline", "dark-focus", "interactive-warm", "minimal-document")

SHAPE_DEFAULT_THEME: dict[str, str] = {
    "spec": "birchline",
    "code-review": "dark-focus",
    "prototype": "interactive-warm",
    "report": "birchline",
    "editor": "interactive-warm",
    "data-viz": "dark-focus",
}

# Theme CSS overrides. birchline is the base template default — no override needed.
THEME_CSS: dict[str, str] = {
    "birchline": "",
    "dark-focus": (
        "    /* === Dark Focus Theme Override === */\n"
        "    :root { --color-primary: #64B5F6; --color-slate: #e0e0e0; --color-ivory: #1a1a2e;"
        " --color-oat: #232340; --color-white: #2a2a4a; --color-gray-100: #2d2d50;"
        " --color-gray-300: #3d3d60; --color-gray-500: #8888a0; --color-gray-700: #c0c0d0;"
        " --color-success: #81C784; --color-warning: #FFB74D; --color-danger: #E57373;"
        " --color-info: #64B5F6; }\n"
        "    body { background: var(--color-ivory); color: var(--color-slate); }\n"
    ),
    "interactive-warm": (
        "    /* === Interactive Warm Theme Override === */\n"
        "    :root { --color-primary: #5B8DEF; --color-ivory: #FAFAF8; --color-oat: #F0F0EC; }\n"
    ),
    "minimal-document": (
        "    /* === Minimal Document Theme Override === */\n"
        "    :root { --color-ivory: #FFFFF8; --color-slate: #333333; --color-primary: #555555; }\n"
        "    body { font-family: Georgia, 'Times New Roman', serif; max-width: 680px;"
        " margin: 0 auto; line-height: 1.7; }\n"
    ),
}

BASE_TEMPLATE_PATH = Path(__file__).parent.parent / "assets" / "base-template.html"


def assemble_template(shape: str, title: str, theme: str | None = None) -> str:
    """Assemble an HTML template with the given shape, title, and theme.

    Args:
        shape: One of the 6 valid artifact shapes.
        title: The title to inject into the template.
        theme: Optional theme override. Defaults to shape-specific theme.

    Returns:
        The assembled HTML string.

    Raises:
        ValueError: If shape or theme is invalid.
        FileNotFoundError: If base template is missing.
    """
    if shape not in VALID_SHAPES:
        raise ValueError(f"Invalid shape '{shape}'. Valid shapes: {', '.join(VALID_SHAPES)}")

    resolved_theme = theme if theme is not None else SHAPE_DEFAULT_THEME[shape]
    if resolved_theme not in VALID_THEMES:
        raise ValueError(f"Invalid theme '{resolved_theme}'. Valid themes: {', '.join(VALID_THEMES)}")

    template = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")

    # Inject title
    html = template.replace("<!-- TITLE -->", title)

    # Inject theme CSS override after the STYLES comment placeholder
    theme_css = THEME_CSS[resolved_theme]
    if theme_css:
        html = html.replace("/* <!-- STYLES --> */", theme_css + "    /* <!-- STYLES --> */")

    return html


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Assemble an HTML artifact template.")
    parser.add_argument("--shape", required=True, help="Artifact shape.")
    parser.add_argument("--title", required=True, help="Title for the artifact.")
    parser.add_argument(
        "--theme", default=None, help="Theme override (birchline, dark-focus, interactive-warm, minimal-document)."
    )
    args = parser.parse_args()

    if args.shape not in VALID_SHAPES:
        sys.stderr.write(f"Error: Invalid shape '{args.shape}'. Valid shapes: {', '.join(VALID_SHAPES)}\n")
        sys.exit(1)

    if args.theme is not None and args.theme not in VALID_THEMES:
        sys.stderr.write(f"Error: Invalid theme '{args.theme}'. Valid themes: {', '.join(VALID_THEMES)}\n")
        sys.exit(1)

    try:
        html = assemble_template(args.shape, args.title, args.theme)
    except FileNotFoundError:
        sys.stderr.write(f"Error: Base template not found at {BASE_TEMPLATE_PATH}\n")
        sys.exit(2)

    sys.stdout.write(html)


if __name__ == "__main__":
    main()
