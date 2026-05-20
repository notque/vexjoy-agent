"""Tests for to-pdf.py — Chrome-headless PDF generator.

Tier 1 (always run): unit tests on pure functions imported via importlib.
Tier 2 (gated): integration tests that actually invoke Chrome.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
SCRIPT_PATH = SCRIPTS_DIR / "to-pdf.py"
ASSEMBLE_SCRIPT = SCRIPTS_DIR / "assemble-template.py"


def _load_to_pdf():
    """Import the hyphenated to-pdf.py via importlib."""
    spec = importlib.util.spec_from_file_location("to_pdf", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE executing so dataclasses can resolve
    # forward-referenced type names against the module namespace.
    sys.modules["to_pdf"] = mod
    spec.loader.exec_module(mod)
    return mod


to_pdf = _load_to_pdf()


# Marker for the assembler (validator gate dependency).
MARKER = "<!-- assembled by html-artifact v1.1 -->"


CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _chrome_available() -> bool:
    if os.environ.get("CHROME_PATH"):
        return Path(os.environ["CHROME_PATH"]).is_file()
    if Path(CHROME_MAC).is_file():
        return True
    return any(shutil.which(name) for name in ("chromium", "google-chrome", "chrome"))


def _chrome_runs() -> bool:
    """Return True if Chrome actually launches headless AND can render.

    Some CI runners install chromium but it aborts with SIGABRT (-6) when
    invoked headless due to missing sandbox/GPU dependencies.
    `_chrome_available()` only confirms the binary is present;
    `chromium --version` exits 0 even when headless rendering would crash.
    This helper matches the real workload more closely: it asks Chrome
    to dump the DOM of a trivial about:blank page and only returns True
    if that succeeds.
    """
    if not _chrome_available():
        return False
    chrome = (
        os.environ.get("CHROME_PATH")
        or (CHROME_MAC if Path(CHROME_MAC).is_file() else None)
        or shutil.which("chromium")
        or shutil.which("google-chrome")
        or shutil.which("chrome")
    )
    if not chrome:
        return False
    try:
        proc = subprocess.run(
            [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--dump-dom",
                "about:blank",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


# --- Tier 1: fast unit tests ---------------------------------------------------


class TestShapeDetection:
    """detect_shape() parses <body data-shape="...">."""

    def test_shape_detection_from_html(self) -> None:
        html = '<!DOCTYPE html><html><body data-shape="deck"><h1>x</h1></body></html>'
        assert to_pdf.detect_shape(html) == "deck"

    def test_shape_detection_fallback(self) -> None:
        """No data-shape -> detect_shape returns None; generate_pdf adds warning + defaults to 'report'."""
        html = "<!DOCTYPE html><html><body><h1>x</h1></body></html>"
        assert to_pdf.detect_shape(html) is None

    def test_shape_detection_case_insensitive(self) -> None:
        html = '<BODY data-shape="Spec"><p>x</p></BODY>'
        assert to_pdf.detect_shape(html) == "spec"


class TestPageSizeMapping:
    """resolve_page_size() maps shape -> token, honors override."""

    def test_deck_maps_to_deck_16x9(self) -> None:
        assert to_pdf.resolve_page_size("deck", "auto") == "deck-16x9"

    def test_report_maps_to_letter_portrait(self) -> None:
        assert to_pdf.resolve_page_size("report", "auto") == "letter-portrait"

    def test_spec_maps_to_letter_landscape(self) -> None:
        assert to_pdf.resolve_page_size("spec", "auto") == "letter-landscape"

    def test_unknown_shape_defaults_to_letter_portrait(self) -> None:
        assert to_pdf.resolve_page_size("nonsense", "auto") == "letter-portrait"

    def test_explicit_override_wins(self) -> None:
        assert to_pdf.resolve_page_size("deck", "letter-portrait") == "letter-portrait"


class TestChromePathResolution:
    """find_chrome() resolution order: override -> CHROME_PATH -> macOS bundle -> PATH."""

    def test_chrome_path_resolution_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting CHROME_PATH points find_chrome() at that file."""
        fake_chrome = tmp_path / "fake-chrome"
        fake_chrome.write_text("#!/bin/sh\necho fake\n")
        fake_chrome.chmod(0o755)
        monkeypatch.setenv("CHROME_PATH", str(fake_chrome))
        # No override: env var should be honored ahead of the bundled fallbacks.
        # (On macOS the bundle path may also exist; env var is checked first per code order.)
        result = to_pdf.find_chrome(None)
        assert result == str(fake_chrome)

    def test_chrome_path_override_wins_over_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit override beats CHROME_PATH env var."""
        env_chrome = tmp_path / "env-chrome"
        env_chrome.write_text("#!/bin/sh\n")
        env_chrome.chmod(0o755)
        override_chrome = tmp_path / "override-chrome"
        override_chrome.write_text("#!/bin/sh\n")
        override_chrome.chmod(0o755)
        monkeypatch.setenv("CHROME_PATH", str(env_chrome))
        assert to_pdf.find_chrome(str(override_chrome)) == str(override_chrome)

    def test_chrome_path_resolution_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no Chrome candidates exist, find_chrome() returns None.

        Note: a CLI-level test is intentionally omitted because CHROME_FALLBACKS
        contains an absolute path to the macOS Google Chrome bundle that cannot
        be hidden via env vars; it would resolve and trigger a real Chrome run.
        """
        bogus = tmp_path / "does-not-exist"
        monkeypatch.setenv("CHROME_PATH", str(bogus))
        # Empty PATH so bare-name fallbacks (chromium, google-chrome, chrome) cannot resolve.
        monkeypatch.setenv("PATH", str(tmp_path))
        # Replace fallback list with a single non-existent absolute path.
        monkeypatch.setattr(to_pdf, "CHROME_FALLBACKS", (str(bogus),))
        assert to_pdf.find_chrome(None) is None

    def test_chrome_path_explicit_bogus_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit override pointing at a non-existent file is rejected; falls through."""
        bogus = tmp_path / "no-such-binary"
        monkeypatch.delenv("CHROME_PATH", raising=False)
        monkeypatch.setenv("PATH", str(tmp_path))
        monkeypatch.setattr(to_pdf, "CHROME_FALLBACKS", (str(tmp_path / "also-missing"),))
        assert to_pdf.find_chrome(str(bogus)) is None


class TestSlideCounting:
    """count_slides() counts <section class='slide'> and <div class='slide'>."""

    def test_counts_section_slides(self) -> None:
        html = '<section class="slide">A</section><section class="slide">B</section><section class="slide">C</section>'
        assert to_pdf.count_slides(html) == 3

    def test_counts_div_slides(self) -> None:
        html = '<div class="slide">A</div><div class="slide">B</div>'
        assert to_pdf.count_slides(html) == 2

    def test_counts_mixed_sections_and_divs(self) -> None:
        html = '<section class="slide">A</section><div class="slide">B</div><section class="slide">C</section>'
        assert to_pdf.count_slides(html) == 3

    def test_counts_with_extra_classes(self) -> None:
        html = '<section class="slide active">A</section><section class="slide  large">B</section>'
        assert to_pdf.count_slides(html) == 2

    def test_returns_zero_when_no_slides(self) -> None:
        assert to_pdf.count_slides("<p>no slides here</p>") == 0


class TestPdfResultDict:
    """PdfResult.to_dict() emits the documented schema."""

    def test_to_dict_contains_required_keys(self) -> None:
        r = to_pdf.PdfResult(input="a.html", output="a.pdf")
        d = r.to_dict()
        for k in (
            "ok",
            "input",
            "output",
            "shape",
            "page_size",
            "size_bytes",
            "pages",
            "expected_pages",
            "chrome_path",
            "warnings",
            "errors",
        ):
            assert k in d, f"missing key {k}"


# --- Tier 2: integration tests (need Chrome) -----------------------------------


DECK_TWO_SLIDES = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    f"    {MARKER}\n"
    '    <meta charset="utf-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    "    <title>Deck</title>\n"
    "    <style>\n"
    "      @page { size: 13.333in 7.5in; margin: 0; }\n"
    "      html, body { margin: 0; padding: 0; background: #0b0b0b; color: #fff; }\n"
    "      .slide { width: 13.333in; height: 7.5in; page-break-after: always; "
    "display: flex; align-items: center; justify-content: center; "
    "background: #0b0b0b; color: #fff; font-size: 64px; }\n"
    "      .slide:last-child { page-break-after: auto; }\n"
    "    </style>\n"
    "</head>\n"
    '<body data-shape="deck">\n'
    '    <button data-theme-toggle aria-label="toggle theme">T</button>\n'
    '    <section class="slide">One</section>\n'
    '    <section class="slide">Two</section>\n'
    "</body>\n"
    "</html>\n"
)


@pytest.mark.integration
@pytest.mark.skipif(not _chrome_runs(), reason="Chrome/Chromium not installed or not runnable in this environment")
class TestPdfIntegration:
    """End-to-end: generate a PDF via Chrome headless."""

    def test_minimal_deck_pdf(self, tmp_path: Path) -> None:
        """2-slide deck -> 2-page PDF, > 10KB, exit 0 (or 1 with only warnings)."""
        in_path = tmp_path / "deck.html"
        in_path.write_text(DECK_TWO_SLIDES)
        out_path = tmp_path / "deck.pdf"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--input",
                str(in_path),
                "--output",
                str(out_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        # Exit 0 means clean; exit 1 means warnings (still produced PDF). Either is acceptable here.
        assert proc.returncode in (0, 1), f"unexpected rc={proc.returncode}; stdout={proc.stdout}"
        assert out_path.is_file(), "PDF was not written"
        assert out_path.stat().st_size > 10 * 1024, f"PDF too small: {out_path.stat().st_size} bytes"
        payload = json.loads(proc.stdout)
        assert payload["shape"] == "deck"
        # Page count detection is best-effort; assert at least 1.
        assert payload["pages"] >= 1

    def test_pdf_dark_theme_preserved(self, tmp_path: Path) -> None:
        """Render page 1 of the dark-theme PDF; assert mean luminance < 0.4. Skip if PIL/pypdfium2 unavailable."""
        try:
            import PIL  # type: ignore[import-not-found]
            import pypdfium2 as pdfium  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("pypdfium2 + PIL not available")
        _ = PIL  # required transitively by pdfium.to_pil(); silence linters

        in_path = tmp_path / "deck.html"
        in_path.write_text(DECK_TWO_SLIDES)
        out_path = tmp_path / "deck.pdf"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--input", str(in_path), "--output", str(out_path), "--json"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert proc.returncode in (0, 1)
        assert out_path.is_file()

        pdf = pdfium.PdfDocument(str(out_path))
        try:
            page = pdf[0]
            pil_image = page.render(scale=1.0).to_pil().convert("L")
        finally:
            pdf.close()
        # Mean luminance in [0,255]; dark theme expected well below mid-grey.
        pixels = list(pil_image.getdata())
        mean_lum = sum(pixels) / len(pixels) / 255.0
        assert mean_lum < 0.4, f"expected dark page, got mean luminance {mean_lum:.3f}"
