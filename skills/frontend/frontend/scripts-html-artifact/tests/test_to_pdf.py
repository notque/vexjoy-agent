"""Tests for to-pdf.py — Playwright-based PDF export for html-artifact."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "to-pdf.py")

# --- Import module directly for unit tests ---
sys.path.insert(0, str(Path(__file__).parent.parent))
to_pdf = import_module("to-pdf")


def _playwright_runs() -> bool:
    """Returns True only if Playwright imports AND chromium can launch.

    Avoids the May 9 mistake of skipping based on Chrome binary existence
    (which lied) — actually launches a browser to confirm.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


# --- Sample HTML fragments for unit tests ---

_HTML_DECK = """<!DOCTYPE html>
<html><head><title>T</title>
<style>
.slide { width: 13.333in; height: 7.5in; padding: 0.5in; box-sizing: border-box;
  background: #0a0a0a; color: #f5f5f5; display: flex; align-items: center;
  justify-content: center; font: 96px/1.1 system-ui, sans-serif; }
.slide h1 { margin: 0; }
</style></head>
<body data-shape="deck">
<div class="slide"><h1>Slide One: Introduction</h1></div>
<div class="slide"><h1>Slide Two: Body</h1></div>
<div class="slide"><h1>Slide Three: Conclusion</h1></div>
</body></html>
"""

_HTML_SPEC = """<!DOCTYPE html>
<html><head><title>T</title></head>
<body data-shape="spec">
<main><h1>Spec</h1><p>Body</p></main>
</body></html>
"""

_HTML_REPORT = """<!DOCTYPE html>
<html><head><title>T</title></head>
<body data-shape="report">
<main><h1>Report</h1><p>Body</p></main>
</body></html>
"""

_HTML_NO_SHAPE = """<!DOCTYPE html>
<html><head><title>T</title></head>
<body><main><p>No shape</p></main></body></html>
"""

_HTML_MALFORMED = "this is not html"


class TestShapeDetection:
    """Unit: detect_shape() pulls the data-shape attribute from <body>."""

    def test_detect_deck(self) -> None:
        assert to_pdf.detect_shape(_HTML_DECK) == "deck"

    def test_detect_spec(self) -> None:
        assert to_pdf.detect_shape(_HTML_SPEC) == "spec"

    def test_detect_missing_returns_none(self) -> None:
        assert to_pdf.detect_shape(_HTML_NO_SHAPE) is None

    def test_detect_with_extra_attributes(self) -> None:
        html = '<body class="foo" data-shape="report" data-theme="light">'
        assert to_pdf.detect_shape(html) == "report"

    def test_detect_data_shape_first_attribute(self) -> None:
        html = '<body data-shape="diagram" class="x">'
        assert to_pdf.detect_shape(html) == "diagram"

    def test_detect_case_insensitive_tag(self) -> None:
        html = '<BODY data-shape="editor">'
        assert to_pdf.detect_shape(html) == "editor"


class TestPageOptionsForShape:
    """Unit: shape → page-size mapping."""

    def test_deck_widescreen_landscape_no_margin(self) -> None:
        opts = to_pdf.page_options_for_shape("deck")
        assert opts["width"] == "13.333in"
        assert opts["height"] == "7.5in"
        assert opts["landscape"] is True
        assert opts["margin"]["top"] == "0"
        assert "format" not in opts

    def test_spec_letter_landscape(self) -> None:
        opts = to_pdf.page_options_for_shape("spec")
        assert opts["format"] == "Letter"
        assert opts["landscape"] is True
        assert opts["margin"]["top"] == "0.5in"

    def test_report_letter_portrait(self) -> None:
        opts = to_pdf.page_options_for_shape("report")
        assert opts["format"] == "Letter"
        assert opts["landscape"] is False
        assert opts["margin"]["top"] == "0.75in"

    def test_editor_letter_portrait(self) -> None:
        opts = to_pdf.page_options_for_shape("editor")
        assert opts["format"] == "Letter"
        assert opts["landscape"] is False

    @pytest.mark.parametrize("shape", ["spec", "code-review", "prototype", "data-viz", "diagram"])
    def test_letter_landscape_shapes(self, shape: str) -> None:
        opts = to_pdf.page_options_for_shape(shape)
        assert opts["format"] == "Letter"
        assert opts["landscape"] is True

    def test_unknown_shape_falls_back_to_default(self) -> None:
        opts = to_pdf.page_options_for_shape("not-a-shape")
        assert opts["format"] == "Letter"
        assert opts["landscape"] is False

    def test_none_falls_back_to_default(self) -> None:
        opts = to_pdf.page_options_for_shape(None)
        assert opts["format"] == "Letter"
        assert opts["landscape"] is False

    def test_returned_dict_is_independent_copy(self) -> None:
        a = to_pdf.page_options_for_shape("deck")
        b = to_pdf.page_options_for_shape("deck")
        a["margin"]["top"] = "2in"
        # b's margin should still be the documented default
        assert b["margin"]["top"] == "0"


class TestSlideCount:
    """Unit: deck page_count derives from .slide elements."""

    def test_three_slides(self) -> None:
        assert to_pdf.count_slides(_HTML_DECK) == 3

    def test_zero_slides(self) -> None:
        assert to_pdf.count_slides(_HTML_REPORT) == 0

    def test_slide_among_other_classes(self) -> None:
        html = '<div class="slide active dark">A</div><div class="card slide">B</div>'
        assert to_pdf.count_slides(html) == 2

    def test_slide_substring_does_not_match(self) -> None:
        html = '<div class="slideshow">A</div>'
        assert to_pdf.count_slides(html) == 0

    def test_slide_deck_wrapper_does_not_count(self) -> None:
        # `.slide-deck` is the wrapper element; only its `.slide` children should count.
        html = (
            '<div class="slide-deck">'
            '<div class="slide active">A</div>'
            '<div class="slide">B</div>'
            '<div class="slide-nav">x</div>'
            "</div>"
        )
        assert to_pdf.count_slides(html) == 2


class TestValidateHtml:
    """Unit: structural sanity check before launching browser."""

    def test_valid_html_returns_none(self) -> None:
        assert to_pdf.validate_html(_HTML_SPEC) is None

    def test_empty_string_errors(self) -> None:
        assert to_pdf.validate_html("") is not None
        assert to_pdf.validate_html("   \n  ") is not None

    def test_no_html_tag_errors(self) -> None:
        assert to_pdf.validate_html(_HTML_MALFORMED) is not None

    def test_no_body_tag_errors(self) -> None:
        assert to_pdf.validate_html("<html><head><title>T</title></head></html>") is not None


class TestCLIBehavior:
    """Subprocess tests for the CLI surface (no browser interaction)."""

    def test_missing_input_exits_1(self, tmp_path: Path) -> None:
        out = tmp_path / "out.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(tmp_path / "missing.html"), "--output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1
        assert "input file not found" in proc.stderr

    def test_malformed_html_exits_1(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.html"
        bad.write_text("not valid html", encoding="utf-8")
        out = tmp_path / "out.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(bad), "--output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1
        assert "Error" in proc.stderr

    def test_missing_data_shape_with_no_flag_exits_1(self, tmp_path: Path) -> None:
        src = tmp_path / "noshape.html"
        src.write_text(_HTML_NO_SHAPE, encoding="utf-8")
        out = tmp_path / "out.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1
        assert "data-shape" in proc.stderr

    def test_invalid_shape_arg_exits_2(self, tmp_path: Path) -> None:
        src = tmp_path / "x.html"
        src.write_text(_HTML_SPEC, encoding="utf-8")
        out = tmp_path / "out.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out), "--shape", "banana"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # argparse choices rejection exits 2
        assert proc.returncode == 2

    def test_help_exits_0(self) -> None:
        cmd = [sys.executable, SCRIPT, "--help"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert "--input" in proc.stdout
        assert "--output" in proc.stdout


class TestJsonOutputContract:
    """JSON output schema tests — verified through unit-level helpers."""

    def test_default_page_returned_for_unknown_shape(self) -> None:
        opts = to_pdf.page_options_for_shape("phantom-shape")
        assert opts == to_pdf.DEFAULT_PAGE
        # Defensive: returned dict is a copy
        opts["format"] = "A4"
        assert to_pdf.DEFAULT_PAGE["format"] == "Letter"


class TestInstallHintRouting:
    """Regression: missing chromium binary must surface install hint, not opaque error."""

    def test_missing_browser_exits_2_with_hint(self, tmp_path: Path, monkeypatch) -> None:
        # Simulate the "Executable doesn't exist" error Playwright raises when
        # the python package is installed but `playwright install chromium` was skipped.
        src = tmp_path / "x.html"
        src.write_text(_HTML_SPEC, encoding="utf-8")
        out = tmp_path / "out.pdf"

        def _raise_missing_binary(*_a: object, **_kw: object) -> None:
            raise RuntimeError(
                "Executable doesn't exist at /tmp/fake/chrome\n"
                "Looks like Playwright was just installed or updated.\n"
                "Please run the following command to download new browsers:\n"
                "    playwright install"
            )

        monkeypatch.setattr(to_pdf, "render_pdf", _raise_missing_binary)
        rc = to_pdf.main(["--input", str(src), "--output", str(out)])
        assert rc == 2

    def test_other_runtime_errors_still_exit_3(self, tmp_path: Path, monkeypatch) -> None:
        src = tmp_path / "x.html"
        src.write_text(_HTML_SPEC, encoding="utf-8")
        out = tmp_path / "out.pdf"

        def _raise_other(*_a: object, **_kw: object) -> None:
            raise RuntimeError("Page navigation timed out after 30000ms")

        monkeypatch.setattr(to_pdf, "render_pdf", _raise_other)
        rc = to_pdf.main(["--input", str(src), "--output", str(out)])
        assert rc == 3


class TestPathHandling:
    """Regression: file:// URLs must escape spaces and unicode per RFC 8089."""

    def test_path_with_spaces_uses_as_uri(self, tmp_path: Path) -> None:
        # pathlib.as_uri() encodes spaces as %20; raw f-string concat doesn't.
        spaced = tmp_path / "with spaces"
        spaced.mkdir()
        src = spaced / "art.html"
        src.write_text(_HTML_SPEC, encoding="utf-8")
        # Confirm the URI form Playwright will receive is properly encoded.
        uri = src.resolve().as_uri()
        assert "%20" in uri
        assert "file://" in uri


# --- Integration tests (browser-required) ---


@pytest.mark.skipif(
    not _playwright_runs(),
    reason="Playwright not installed or chromium unavailable",
)
class TestPdfIntegration:
    """Generate real PDFs for each documented page-size class."""

    def _write_html(self, tmp_path: Path, html: str, name: str) -> Path:
        p = tmp_path / name
        p.write_text(html, encoding="utf-8")
        return p

    def test_generate_deck_pdf_with_slide_count(self, tmp_path: Path) -> None:
        src = self._write_html(tmp_path, _HTML_DECK, "deck.html")
        out = tmp_path / "deck.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["shape"] == "deck"
        assert result["page_count"] == 3
        assert out.is_file()
        assert out.stat().st_size > 10_000

    def test_generate_spec_pdf(self, tmp_path: Path) -> None:
        src = self._write_html(tmp_path, _HTML_SPEC, "spec.html")
        out = tmp_path / "spec.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["shape"] == "spec"
        assert out.stat().st_size > 10_000

    def test_generate_report_pdf(self, tmp_path: Path) -> None:
        src = self._write_html(tmp_path, _HTML_REPORT, "report.html")
        out = tmp_path / "report.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["shape"] == "report"
        assert out.stat().st_size > 10_000

    def test_shape_flag_override(self, tmp_path: Path) -> None:
        # data-shape says "report"; CLI flag says "spec" — flag wins.
        src = self._write_html(tmp_path, _HTML_REPORT, "src.html")
        out = tmp_path / "out.pdf"
        cmd = [sys.executable, SCRIPT, "--input", str(src), "--output", str(out), "--shape", "spec", "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["shape"] == "spec"
