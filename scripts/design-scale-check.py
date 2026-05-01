#!/usr/bin/env python3
"""Check CSS/HTML files for spacing and font-size values that don't snap to a scale.

Flags any px value in spacing/sizing properties that is not a multiple of the
configured base (default: 4px). This is a deterministic check — LLMs orchestrate,
programs execute. Spacing scale compliance is a counting problem.

Usage:
    python3 scripts/design-scale-check.py styles.css
    python3 scripts/design-scale-check.py --base 8 src/
    python3 scripts/design-scale-check.py --allow 1,2 components/*.tsx
    cat styles.css | python3 scripts/design-scale-check.py -
    find src -name '*.css' | xargs python3 scripts/design-scale-check.py

Exit codes:
    0 = all values on scale
    1 = violations found
"""

import argparse
import re
import sys
from pathlib import Path

# Properties whose px values must snap to the grid.
SPACING_PROPS = re.compile(
    r"\b(margin|margin-top|margin-right|margin-bottom|margin-left"
    r"|padding|padding-top|padding-right|padding-bottom|padding-left"
    r"|gap|row-gap|column-gap"
    r"|font-size"
    r"|width|min-width|max-width"
    r"|height|min-height|max-height"
    r"|top|right|bottom|left"
    r"|border-radius"
    r"|outline-offset)\s*:",
    re.IGNORECASE,
)

# Match a px value: captures the numeric part and the 'px' suffix.
PX_VALUE = re.compile(r"(?<![.\w-])(-?\d+(?:\.\d+)?)\s*px\b")

# Inline style attribute in HTML/JSX/TSX files.
INLINE_STYLE = re.compile(r'style\s*=\s*["{]([^"}>]+)["}]', re.IGNORECASE)

# CSS-in-JS patterns: property: "Npx" or property: 'Npx' or property: Npx
CSS_IN_JS_PROP = re.compile(
    r"\b(margin|marginTop|marginRight|marginBottom|marginLeft"
    r"|padding|paddingTop|paddingRight|paddingBottom|paddingLeft"
    r"|gap|rowGap|columnGap"
    r"|fontSize"
    r"|width|minWidth|maxWidth"
    r"|height|minHeight|maxHeight"
    r"|top|right|bottom|left"
    r"|borderRadius"
    r"|outlineOffset)\s*:\s*['\"]?(\d+(?:\.\d+)?)\s*px",
    re.IGNORECASE,
)

SUPPORTED_EXTENSIONS = {".css", ".scss", ".less", ".html", ".htm", ".tsx", ".jsx", ".vue", ".svelte"}


def check_line(line: str, base: int, allowed: set[int]) -> list[tuple[int, int]]:
    """Return list of (value, nearest_on_scale) for violations in a single line.

    Checks both CSS property declarations and inline style attributes.
    """
    violations: list[tuple[int, int]] = []

    # Check standard CSS properties
    found_css_prop = bool(SPACING_PROPS.search(line))
    if found_css_prop:
        for m in PX_VALUE.finditer(line):
            raw = m.group(1)
            # Skip fractional values (e.g., 0.5px for borders)
            if "." in raw:
                continue
            val = int(raw)
            if val < 0:
                val = abs(val)
            if val in allowed:
                continue
            if val % base != 0:
                nearest = round(val / base) * base
                violations.append((int(m.group(1)), nearest))

    # Check CSS-in-JS camelCase properties (only when no standard CSS property matched,
    # to avoid double-counting lines like "padding: 7px" which match both patterns)
    if not found_css_prop:
        for m in CSS_IN_JS_PROP.finditer(line):
            raw = m.group(2)
            if "." in raw:
                continue
            val = int(raw)
            if val < 0:
                val = abs(val)
            if val in allowed:
                continue
            if val % base != 0:
                nearest = round(val / base) * base
                violations.append((int(m.group(2)), nearest))

    # Check inline style attributes
    for style_match in INLINE_STYLE.finditer(line):
        style_content = style_match.group(1)
        if SPACING_PROPS.search(style_content):
            for m in PX_VALUE.finditer(style_content):
                raw = m.group(1)
                if "." in raw:
                    continue
                val = int(raw)
                if val < 0:
                    val = abs(val)
                if val in allowed:
                    continue
                if val % base != 0:
                    nearest = round(val / base) * base
                    violations.append((int(m.group(1)), nearest))

    return violations


def check_file(filepath: Path, base: int, allowed: set[int]) -> list[str]:
    """Check a single file. Returns list of formatted violation messages."""
    messages: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        messages.append(f"{filepath}: error reading file: {e}")
        return messages

    for line_num, line in enumerate(content.splitlines(), start=1):
        for val, nearest in check_line(line, base, allowed):
            messages.append(
                f"{filepath}:{line_num}: value {val}px is not a multiple of {base}px (nearest: {nearest}px)"
            )

    return messages


def check_stdin(base: int, allowed: set[int]) -> list[str]:
    """Check content from stdin. Returns list of formatted violation messages."""
    messages: list[str] = []
    for line_num, line in enumerate(sys.stdin, start=1):
        for val, nearest in check_line(line.rstrip("\n"), base, allowed):
            messages.append(f"<stdin>:{line_num}: value {val}px is not a multiple of {base}px (nearest: {nearest}px)")
    return messages


def collect_files(paths: list[str]) -> list[Path]:
    """Expand paths: files are kept if they have a supported extension, directories are walked."""
    result: list[Path] = []
    for p_str in paths:
        p = Path(p_str)
        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                result.append(p)
        elif p.is_dir():
            for ext in sorted(SUPPORTED_EXTENSIONS):
                result.extend(sorted(p.rglob(f"*{ext}")))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check CSS/HTML files for spacing values not on a px grid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        help="Files or directories to check. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--base",
        type=int,
        default=4,
        help="Base grid size in px (default: 4). Values must be multiples of this.",
    )
    parser.add_argument(
        "--allow",
        type=str,
        default="",
        help="Comma-separated px values to allow (e.g., --allow 1,2 for border widths).",
    )

    args = parser.parse_args()

    base: int = args.base
    allowed: set[int] = set()
    if args.allow:
        for v in args.allow.split(","):
            v = v.strip()
            if v:
                allowed.add(int(v))
    # Always allow 0
    allowed.add(0)

    all_messages: list[str] = []

    if "-" in args.paths:
        all_messages.extend(check_stdin(base, allowed))
        file_paths = [p for p in args.paths if p != "-"]
    else:
        file_paths = args.paths

    if not file_paths and "-" not in args.paths and not all_messages:
        # No files and no stdin — check if stdin has data
        if not sys.stdin.isatty():
            all_messages.extend(check_stdin(base, allowed))
        else:
            parser.print_help()
            sys.exit(0)

    files = collect_files(file_paths)
    for f in files:
        all_messages.extend(check_file(f, base, allowed))

    for msg in all_messages:
        print(msg)

    sys.exit(1 if all_messages else 0)


if __name__ == "__main__":
    main()
