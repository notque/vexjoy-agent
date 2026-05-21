#!/usr/bin/env python3
"""Render an html-artifact to PDF via Playwright (sync API).

Auto-detects shape from `<body data-shape="...">` and selects per-shape page size,
landscape/portrait, and margins. Waits for `networkidle` before snapshotting.

Usage:
    python3 to-pdf.py --input artifact.html --output artifact.pdf
    python3 to-pdf.py --input artifact.html --output artifact.pdf --shape deck
    python3 to-pdf.py --input artifact.html --output artifact.pdf --json

Exit codes:
    0: PDF generated successfully
    1: input/output validation error, missing data-shape, or malformed HTML
    2: Playwright unavailable (install instructions printed to stderr)
    3: PDF generation failed (browser launch, page load, or page.pdf failure)
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

VALID_SHAPES = ("spec", "code-review", "prototype", "report", "editor", "data-viz", "diagram", "deck")

PAGE_SIZE_MAP: dict[str, dict[str, Any]] = {
    "deck": {
        "width": "13.333in",
        "height": "7.5in",
        "landscape": True,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    },
    "spec": {
        "format": "Letter",
        "landscape": True,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
    "code-review": {
        "format": "Letter",
        "landscape": True,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
    "prototype": {
        "format": "Letter",
        "landscape": True,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
    "data-viz": {
        "format": "Letter",
        "landscape": True,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
    "diagram": {
        "format": "Letter",
        "landscape": True,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
    "report": {
        "format": "Letter",
        "landscape": False,
        "margin": {"top": "0.75in", "right": "0.75in", "bottom": "0.75in", "left": "0.75in"},
    },
    "editor": {
        "format": "Letter",
        "landscape": False,
        "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
    },
}

DEFAULT_PAGE: dict[str, Any] = {
    "format": "Letter",
    "landscape": False,
    "margin": {"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
}

INSTALL_HINT = 'pip install -e ".[pdf]" && playwright install chromium'

_DATA_SHAPE_RE = re.compile(r"<body[^>]*\bdata-shape\s*=\s*\"([^\"]+)\"", re.IGNORECASE)
# Match a complete class attribute so we can split into tokens for exact-match counting.
_CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"', re.IGNORECASE)
_HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
_BODY_OPEN_RE = re.compile(r"<body([^>]*)>", re.IGNORECASE)

# Defensive deck print stylesheet injected at render time when shape=deck.
# Guarantees one slide per printed page even when source HTML omits the bundled
# deck-print.css (minimal fixtures, ad-hoc decks, or assembler regressions).
# Uses !important to override any screen `display: none` applied to non-active
# slides by the deck shape stylesheet.
_DECK_PRINT_STYLESHEET = """
<style id="to-pdf-deck-print">
@page { size: 13.333in 7.5in; margin: 0; }
@media print {
  html, body {
    margin: 0 !important;
    padding: 0 !important;
    background: #0a0a0a !important;
    color: #f5f5f5 !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  *, *::before, *::after {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  .deck-nav, .progress-bar, .slide-counter, .deck-controls, .theme-toggle,
  .slide-nav {
    display: none !important;
  }
  /* Un-clip the deck wrapper so child slides can flow into separate pages. */
  .slide-deck {
    position: static !important;
    width: auto !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
    aspect-ratio: auto !important;
    overflow: visible !important;
    display: block !important;
  }
  .slide, .slide:not(.active) {
    display: flex !important;
    flex-direction: column;
    justify-content: center;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    position: relative !important;
    inset: auto !important;
    width: 13.333in !important;
    height: 7.5in !important;
    margin: 0 !important;
    padding: 0.5in !important;
    box-sizing: border-box !important;
    page-break-after: always !important;
    break-after: page !important;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    overflow: hidden;
    background: #0a0a0a !important;
    color: #f5f5f5 !important;
  }
  .slide:last-child {
    page-break-after: auto !important;
    break-after: auto !important;
  }
}
</style>
"""


def inject_deck_print_css(html: str) -> str:
    """Inject defensive deck print CSS just before </head> for shape=deck.

    Idempotent: source HTML already containing `id="to-pdf-deck-print"` is
    returned unchanged. Falls back to inserting after `<body ...>` if no
    `</head>` exists; falls back to prepending if no `<body>` exists either.
    """
    if 'id="to-pdf-deck-print"' in html:
        return html
    if _HEAD_CLOSE_RE.search(html):
        return _HEAD_CLOSE_RE.sub(_DECK_PRINT_STYLESHEET + "</head>", html, count=1)
    if _BODY_OPEN_RE.search(html):
        return _BODY_OPEN_RE.sub(lambda m: f"<body{m.group(1)}>{_DECK_PRINT_STYLESHEET}", html, count=1)
    return _DECK_PRINT_STYLESHEET + html


def detect_shape(html: str) -> str | None:
    """Extract the shape from `<body data-shape="...">`. Returns None if absent."""
    match = _DATA_SHAPE_RE.search(html)
    if match:
        return match.group(1).strip()
    return None


def page_options_for_shape(shape: str | None) -> dict[str, Any]:
    """Look up Playwright `page.pdf()` options for a given shape, falling back to default.

    Returns a deep copy so callers can mutate freely without affecting the source map.
    """
    if shape is None:
        return copy.deepcopy(DEFAULT_PAGE)
    return copy.deepcopy(PAGE_SIZE_MAP.get(shape, DEFAULT_PAGE))


def count_slides(html: str) -> int:
    """Count elements whose class attribute contains the exact token `slide`.

    Scans every `class="..."` attribute and tokenizes on whitespace, counting
    only attributes that have the literal token `slide` (e.g. `class="slide"`,
    `class="slide active"`). Attributes containing only related tokens such as
    `slide-deck`, `slide-nav`, or `slideshow` do not increment the count.
    """
    count = 0
    for match in _CLASS_ATTR_RE.finditer(html):
        tokens = match.group(1).split()
        if "slide" in tokens:
            count += 1
    return count


def validate_html(html: str) -> str | None:
    """Cheap structural sanity check on the HTML. Returns error message or None."""
    if not html.strip():
        return "Input HTML is empty."
    lower = html.lower()
    if "<html" not in lower:
        return "Input does not look like HTML (no <html> tag found)."
    if "<body" not in lower:
        return "Input does not look like HTML (no <body> tag found)."
    return None


def render_pdf(input_path: Path, output_path: Path, shape: str | None) -> dict[str, Any]:
    """Launch Playwright, load the HTML file, and write a PDF.

    Returns a dict with keys: output, page_count, shape, bytes.

    Raises RuntimeError on browser launch / page.goto / page.pdf failures.
    ImportError if Playwright is unavailable.
    """
    from playwright.sync_api import sync_playwright

    html = input_path.read_text(encoding="utf-8")
    err = validate_html(html)
    if err:
        raise ValueError(err)

    resolved_shape = shape if shape is not None else detect_shape(html)
    options = page_options_for_shape(resolved_shape)
    options["path"] = str(output_path)
    options["print_background"] = True

    # For decks, inject defensive print CSS so each .slide reliably becomes one
    # printed page even when the source HTML omits the bundled deck-print.css
    # (e.g. minimal fixtures). Write the augmented HTML to a sibling temp file
    # so that file:// loading still resolves any relative resources from the
    # original artifact's directory.
    load_path = input_path
    temp_path: Path | None = None
    if resolved_shape == "deck":
        augmented = inject_deck_print_css(html)
        if augmented != html:
            temp_path = input_path.with_name(f".{input_path.stem}.to-pdf.tmp.html")
            temp_path.write_text(augmented, encoding="utf-8")
            load_path = temp_path

    file_url = f"file://{load_path.resolve()}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(file_url, wait_until="networkidle")
                page.wait_for_load_state("networkidle")
                page.pdf(**options)
            finally:
                browser.close()
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    pdf_bytes = output_path.stat().st_size
    if resolved_shape == "deck":
        page_count = count_slides(html)
    else:
        page_count = 0  # unknown without parsing the PDF; deck is the documented case

    return {
        "output": str(output_path.resolve()),
        "page_count": page_count,
        "shape": resolved_shape or "default",
        "bytes": pdf_bytes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an html-artifact to PDF via Playwright.")
    parser.add_argument("--input", required=True, help="Path to the source .html file.")
    parser.add_argument("--output", required=True, help="Path for the generated .pdf file.")
    parser.add_argument(
        "--shape",
        default=None,
        choices=VALID_SHAPES,
        help="Override shape detection (otherwise read from <body data-shape>).",
    )
    parser.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="Emit machine-readable JSON to stdout on success.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        sys.stderr.write(f"Error: input file not found: {input_path}\n")
        return 1

    # Resolve shape: --shape wins, else parse <body data-shape>.
    if args.shape is None:
        html = input_path.read_text(encoding="utf-8")
        err = validate_html(html)
        if err:
            sys.stderr.write(f"Error: {err}\n")
            return 1
        detected = detect_shape(html)
        if detected is None:
            sys.stderr.write(
                "Error: HTML artifact missing data-shape attribute. "
                "Re-assemble with assemble-template.py or pass --shape explicitly.\n"
            )
            return 1
        shape = detected
    else:
        shape = args.shape

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = render_pdf(input_path, output_path, shape)
    except ImportError:
        sys.stderr.write(f"Error: Playwright is not installed.\nInstall with: {INSTALL_HINT}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Error: PDF generation failed: {type(e).__name__}: {e}\n")
        return 3

    if args.json_out:
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        sys.stdout.write(
            f"PDF written to {result['output']} "
            f"(shape={result['shape']}, {result['bytes']} bytes"
            + (f", {result['page_count']} slides" if result["page_count"] else "")
            + ")\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
