#!/usr/bin/env python3
"""Assemble slide layout HTML and CSS from layout templates.

Each layout type has paired .html and .css files in templates/layouts/.
This script combines selected layouts into a single CSS output and
lists available HTML templates.

Usage:
    python3 assemble-layouts.py --list
    python3 assemble-layouts.py --layouts title,content,code
    python3 assemble-layouts.py --all --output layouts.css
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LAYOUTS_DIR = SCRIPT_DIR.parent / "templates" / "layouts"

LAYOUT_TYPES = {
    "title": {
        "description": "Title slide: 1 heading + 1 subtitle (max 12 words)",
        "density": "1 heading + 1 subtitle",
    },
    "content": {
        "description": "Content slide: 4-6 bullets (each max 10 words, no nesting)",
        "density": "4-6 bullets, 10 words each",
    },
    "grid": {
        "description": "Feature grid: max 6 cards (icon + label + descriptor)",
        "density": "6 cards max",
    },
    "code": {
        "description": "Code slide: 8-10 lines, monospace, syntax highlight allowed",
        "density": "8-10 lines",
    },
    "quote": {
        "description": "Quote slide: 1 quote (max 30 words) + attribution",
        "density": "1 quote + 1 attribution",
    },
    "image": {
        "description": "Image slide: 1 image (max-height: min(50vh, 400px)) + caption (max 10 words)",
        "density": "1 image + caption",
    },
    "section-break": {
        "description": "Section break: 1 word/phrase, full-bleed accent background",
        "density": "1 word or short phrase",
    },
}

OVERFLOW_CHECKS = {
    "fixed-inner-height": {
        "detection": "grep -n 'height: [0-9]*px' output.html | grep -v 'max-height\\|min-height'",
        "fix": "Use max-height: min(Xvh, Ypx) instead of fixed px height",
    },
    "min-height-on-slide": {
        "detection": "grep -n 'min-height' output.html | grep 'slide'",
        "fix": "Use exact height: 100vh; height: 100dvh (not min-height)",
    },
    "nested-bullets": {
        "detection": "grep -n '<li>.*<ul>' output.html",
        "fix": "Flatten to single level. Split into separate slides if needed.",
    },
    "pre-without-overflow": {
        "detection": "grep -A5 '<pre>' output.html | grep 'overflow'",
        "fix": "Add max-height: min(55vh, 500px); overflow: hidden to .slide-code pre",
    },
    "hard-coded-colors": {
        "detection": "grep -n 'color: #' output.html | grep -v ':root'",
        "fix": "Use var(--text-primary), var(--accent), etc. instead of hex values",
    },
}

BREAKPOINTS = [
    (1920, 1080, "Standard desktop / projector"),
    (1440, 900, 'MacBook 15"'),
    (1280, 720, "HD projector"),
    (1024, 768, "iPad landscape"),
    (768, 1024, "iPad portrait"),
    (375, 667, "iPhone SE"),
    (414, 896, "iPhone 11/XR"),
    (667, 375, "iPhone landscape"),
    (896, 414, "iPhone 11 landscape"),
]


def list_layouts():
    print("Available slide layout types:")
    print()
    for name, info in LAYOUT_TYPES.items():
        html_path = LAYOUTS_DIR / f"{name}.html"
        css_path = LAYOUTS_DIR / f"{name}.css"
        html_ok = "OK" if html_path.exists() else "MISSING"
        css_ok = "OK" if css_path.exists() else "MISSING"
        print(f"  {name:<16} HTML [{html_ok}]  CSS [{css_ok}]")
        print(f"    {info['description']}")
        print(f"    Density limit: {info['density']}")
        print()

    print("Overflow checks (run after assembly):")
    for name, check in sorted(OVERFLOW_CHECKS.items()):
        print(f"  {name}: {check['fix']}")
        print(f"    Detect: {check['detection']}")
    print()

    print("Validation breakpoints (all 9 must pass):")
    for w, h, context in BREAKPOINTS:
        print(f"  {w}x{h:<6} {context}")


def load_file(name: str) -> str:
    path = LAYOUTS_DIR / name
    if not path.exists():
        print(f"Error: layout file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def assemble(layout_names: list, include_html: bool, output_path: str = None):
    parts_css = []
    parts_html = []

    for name in layout_names:
        if name not in LAYOUT_TYPES:
            print(f"Warning: unknown layout '{name}', skipping", file=sys.stderr)
            continue

        css_file = f"{name}.css"
        css_path = LAYOUTS_DIR / css_file
        if css_path.exists():
            parts_css.append(f"/* === Layout: {name} === */\n{load_file(css_file)}")

        if include_html:
            html_file = f"{name}.html"
            html_path = LAYOUTS_DIR / html_file
            if html_path.exists():
                parts_html.append(f"<!-- === Layout: {name} === -->\n{load_file(html_file)}")

    output = "\n\n".join(parts_css)
    if include_html and parts_html:
        output += "\n\n<!-- === HTML Templates === -->\n\n"
        output += "\n\n".join(parts_html)

    if output_path:
        Path(output_path).write_text(output)
        print(f"Written to {output_path}", file=sys.stderr)
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble slide layout CSS and HTML from templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --layouts title,content,code
  %(prog)s --all --output layouts.css
  %(prog)s --layouts title,content --include-html
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available layouts")
    parser.add_argument("--layouts", help="Comma-separated layout names to include")
    parser.add_argument("--all", action="store_true", help="Include all layouts")
    parser.add_argument(
        "--include-html", dest="include_html", action="store_true", help="Include HTML templates in output"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list:
        list_layouts()
        return

    if args.all:
        layout_names = list(LAYOUT_TYPES.keys())
    elif args.layouts:
        layout_names = [l.strip() for l in args.layouts.split(",") if l.strip()]
    else:
        parser.error("--layouts or --all is required (use --list to see layouts)")

    assemble(layout_names, args.include_html, args.output)


if __name__ == "__main__":
    main()
