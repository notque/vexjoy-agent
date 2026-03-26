#!/usr/bin/env python3
"""
validate-slides.py — Deterministic viewport overflow checker for HTML slide decks.

Exit codes:
  0 — All slides pass at all required breakpoints. No overflow detected.
  1 — Overflow detected. Report printed to stdout listing slide index and breakpoint.
  2 — Playwright unavailable. Manual checklist gate must be used instead.

Usage:
  python3 validate-slides.py path/to/deck.html
  python3 validate-slides.py path/to/deck.html --breakpoints 1920x1080,1440x900

Detection method:
  For each .slide element: scrollHeight > clientHeight indicates overflow.
  This is the same signal a browser uses to show a scrollbar.
"""

import argparse
import json
import sys
from pathlib import Path

# Required breakpoints per ADR-106 specification.
# Format: (width, height, label)
DEFAULT_BREAKPOINTS = [
    (1920, 1080, "1920x1080 desktop/projector"),
    (1440, 900, "1440x900 MacBook 15"),
    (1280, 720, "1280x720 HD projector"),
    (1024, 768, "1024x768 iPad landscape / older projector"),
    (768, 1024, "768x1024 iPad portrait"),
    (375, 667, "375x667 iPhone SE"),
    (414, 896, "414x896 iPhone 11/XR"),
    (667, 375, "667x375 iPhone landscape"),
    (896, 414, "896x414 iPhone 11 landscape"),
]

# JS snippet injected into each page to detect overflow on .slide elements.
OVERFLOW_CHECK_JS = """
(function() {
  const slides = Array.from(document.querySelectorAll('.slide'));
  const results = slides.map((slide, i) => {
    const clientH = slide.clientHeight;
    const scrollH = slide.scrollHeight;
    const overflows = scrollH > clientH;
    return {
      index: i,
      clientHeight: clientH,
      scrollHeight: scrollH,
      overflows: overflows
    };
  });
  return JSON.stringify(results);
})();
"""


def parse_breakpoints(spec: str) -> list[tuple[int, int, str]]:
    """Parse a comma-separated list of WxH breakpoint specs into tuples."""
    result = []
    for part in spec.split(","):
        part = part.strip()
        if "x" not in part:
            raise ValueError(f"Invalid breakpoint format '{part}' — expected WxH (e.g. 1920x1080)")
        w, h = part.split("x", 1)
        result.append((int(w), int(h), f"{w}x{h}"))
    return result


def check_playwright_available() -> bool:
    """Return True if playwright and its chromium browser are importable and installed."""
    try:
        from playwright.sync_api import sync_playwright

        return True
    except ImportError:
        return False


def print_manual_checklist(html_path: str) -> None:
    """Print the fallback manual checklist when Playwright is unavailable."""
    print(
        "\n[validate-slides] Playwright is not installed.\n"
        "Falling back to manual checklist gate (Gate 5 fallback).\n"
        "This is less reliable than automated validation.\n"
        "\n"
        "For EVERY slide in the deck, verify ALL of the following:\n"
        "\n"
        "  [ ] height: 100vh AND height: 100dvh present on .slide\n"
        "  [ ] overflow: hidden present on .slide\n"
        "  [ ] All body text uses clamp() for font sizing\n"
        "  [ ] No fixed-height content boxes (no height: 300px on inner elements)\n"
        "  [ ] No min-height on .slide that could allow growth past 100dvh\n"
        "  [ ] No -clamp(...) patterns anywhere in CSS (use calc(-1 * clamp(...)) instead)\n"
        "\n"
        f"File: {html_path}\n"
        "\n"
        "Confirm all items pass for every slide before proceeding.\n"
        "This exit code (2) must NOT be treated as a pass — it means validation\n"
        "could not run automatically.\n",
        file=sys.stderr,
    )


def run_validation(html_path: Path, breakpoints: list[tuple[int, int, str]]) -> int:
    """
    Run Playwright-based overflow detection across all breakpoints.

    Returns:
      0 if no overflow found
      1 if overflow found (report printed to stdout)
    """
    from playwright.sync_api import sync_playwright

    file_url = html_path.resolve().as_uri()
    failures: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width, height, label in breakpoints:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                )
                page = context.new_page()
                page.goto(file_url, wait_until="networkidle")

                raw = page.evaluate(OVERFLOW_CHECK_JS)
                results = json.loads(raw)

                for item in results:
                    if item["overflows"]:
                        failures.append(
                            {
                                "breakpoint": label,
                                "width": width,
                                "height": height,
                                "slide_index": item["index"],
                                "client_height": item["clientHeight"],
                                "scroll_height": item["scrollHeight"],
                                "overflow_px": item["scrollHeight"] - item["clientHeight"],
                            }
                        )

                context.close()
        finally:
            browser.close()

    if not failures:
        slide_count_check = _count_slides(html_path)
        print(
            f"[validate-slides] PASS — {len(breakpoints)} breakpoints checked"
            + (f", {slide_count_check} slides" if slide_count_check else "")
        )
        return 0

    # Print structured failure report.
    print(f"[validate-slides] FAIL — {len(failures)} overflow(s) detected\n")
    for f in failures:
        print(
            f"  Slide {f['slide_index']} @ {f['breakpoint']}: "
            f"scrollHeight={f['scroll_height']}px > clientHeight={f['client_height']}px "
            f"(overflow by {f['overflow_px']}px)"
        )
    print(
        "\nFix: Split overflowing slides. Do not shrink text or reduce font sizes.\n"
        "Re-run validate-slides.py after fixing. Gate 5 requires exit code 0."
    )
    return 1


def _count_slides(html_path: Path) -> int | None:
    """Quick non-browser slide count via string search."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="ignore")
        return content.count('class="slide"') + content.count("class='slide'")
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check HTML slide deck for viewport overflow across required breakpoints.",
        epilog=(
            "Exit 0: all clear. Exit 1: overflow found. Exit 2: Playwright unavailable (use manual checklist gate)."
        ),
    )
    parser.add_argument("html_file", help="Path to the HTML slide deck file.")
    parser.add_argument(
        "--breakpoints",
        default=None,
        help=(
            "Comma-separated list of WxH breakpoints to check "
            "(e.g. '1920x1080,375x667'). Defaults to all 9 ADR-106 breakpoints."
        ),
    )
    args = parser.parse_args()

    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"[validate-slides] ERROR: File not found: {html_path}", file=sys.stderr)
        return 1

    breakpoints = DEFAULT_BREAKPOINTS
    if args.breakpoints:
        try:
            breakpoints = parse_breakpoints(args.breakpoints)
        except ValueError as e:
            print(f"[validate-slides] ERROR: {e}", file=sys.stderr)
            return 1

    if not check_playwright_available():
        print_manual_checklist(str(html_path))
        return 2

    return run_validation(html_path, breakpoints)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[validate-slides] unexpected error: {e}", file=sys.stderr)
        sys.exit(2)
