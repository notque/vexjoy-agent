#!/usr/bin/env python3
"""Assemble slide deck JavaScript from controller components.

Combines the core SlideController with optional feature components
(speaker notes, countdown timer, etc.).

Usage:
    python3 assemble-controllers.py --list
    python3 assemble-controllers.py --core
    python3 assemble-controllers.py --core --features speaker-notes,countdown-timer
    python3 assemble-controllers.py --core --output controller.js
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONTROLLERS_DIR = SCRIPT_DIR.parent / "templates" / "controllers"

COMPONENTS = {
    "slide-controller": {
        "files": ["slide-controller.js"],
        "css": ["indicator.css"],
        "description": "Core SlideController with keyboard, touch, wheel, and IntersectionObserver",
        "required": True,
    },
    "speaker-notes": {
        "files": ["speaker-notes.js"],
        "css": ["speaker-notes.css"],
        "description": "Speaker notes panel toggled with 'n' key",
        "required": False,
    },
    "countdown-timer": {
        "files": ["countdown-timer.js"],
        "css": [],
        "description": "Countdown timer with urgent state at <2 minutes",
        "required": False,
    },
}

PATTERN_CHECKS = {
    "navigating-guard": {
        "detection": "grep -c 'navigating' output.html",
        "fix": "Add `if (this.navigating) return;` as first line of go()",
        "symptom": "Deck skips 2-3 slides on rapid key presses",
    },
    "wheel-debounce": {
        "detection": "rg 'clearTimeout' output.html",
        "fix": "Wrap wheel handler in clearTimeout + setTimeout(150ms)",
        "symptom": "Trackpad flick jumps to last slide",
    },
    "display-none": {
        "detection": "grep 'display.*none' output.html",
        "fix": "Use opacity:0; position:absolute instead of display:none",
        "symptom": "Reveal animations never fire",
    },
    "touch-y-axis": {
        "detection": "grep 'screenY' output.html",
        "fix": "Add Math.abs(dy) > Math.abs(dx) guard in touchend",
        "symptom": "Swipe fires on vertical scroll",
    },
    "space-prevent-default": {
        "detection": "grep -A1 'Space' output.html",
        "fix": "Call e.preventDefault() before this.next() on Space key",
        "symptom": "Space scrolls page AND advances slide",
    },
}


def list_components():
    print("Available controller components:")
    print()
    for name, info in sorted(COMPONENTS.items()):
        req = " [REQUIRED]" if info["required"] else " [optional]"
        print(f"  {name:<20}{req}")
        print(f"    {info['description']}")
        js_files = ", ".join(info["files"])
        css_files = ", ".join(info["css"]) if info["css"] else "(none)"
        print(f"    JS:  {js_files}")
        print(f"    CSS: {css_files}")
        print()

    print("Pattern checks (run after assembly):")
    for name, check in sorted(PATTERN_CHECKS.items()):
        print(f"  {name}: {check['symptom']}")
        print(f"    Detect: {check['detection']}")
        print(f"    Fix:    {check['fix']}")


def load_file(name: str) -> str:
    path = CONTROLLERS_DIR / name
    if not path.exists():
        print(f"Error: component file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def assemble(features: list, include_css: bool, output_path: str = None):
    parts_js = []
    parts_css = []

    # Always include core
    core = COMPONENTS["slide-controller"]
    for f in core["files"]:
        parts_js.append(f"// === {f} ===\n{load_file(f)}")
    if include_css:
        for f in core["css"]:
            parts_css.append(f"/* === {f} === */\n{load_file(f)}")

    # Add requested features
    for feature in features:
        if feature not in COMPONENTS:
            print(f"Warning: unknown feature '{feature}', skipping", file=sys.stderr)
            continue
        comp = COMPONENTS[feature]
        for f in comp["files"]:
            parts_js.append(f"// === {f} ({feature}) ===\n{load_file(f)}")
        if include_css:
            for f in comp["css"]:
                parts_css.append(f"/* === {f} ({feature}) === */\n{load_file(f)}")

    output = "\n\n".join(parts_js)
    if include_css and parts_css:
        output += "\n\n/* === CSS Components === */\n"
        output += "\n\n".join(parts_css)

    if output_path:
        Path(output_path).write_text(output)
        print(f"Written to {output_path}", file=sys.stderr)
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble slide deck JavaScript from controller components.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --core
  %(prog)s --core --features speaker-notes,countdown-timer
  %(prog)s --core --include-css --output bundle.js
        """,
    )
    parser.add_argument("--list", action="store_true", help="List available components")
    parser.add_argument("--core", action="store_true", help="Include core SlideController")
    parser.add_argument("--features", help="Comma-separated optional features to include")
    parser.add_argument(
        "--include-css", dest="include_css", action="store_true", help="Include CSS components in output"
    )
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list:
        list_components()
        return

    if not args.core:
        parser.error("--core is required to assemble (use --list to see components)")

    features = []
    if args.features:
        features = [f.strip() for f in args.features.split(",") if f.strip()]

    assemble(features, args.include_css, args.output)


if __name__ == "__main__":
    main()
