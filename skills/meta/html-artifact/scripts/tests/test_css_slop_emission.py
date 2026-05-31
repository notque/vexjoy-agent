"""Tests for the vendored slop scan wired into validate-artifact.py and the
self-describing stamp emitted by assemble-template.py."""

from __future__ import annotations

import re
import sys
import tempfile
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

validate_mod = import_module("validate-artifact")
validate_artifact = validate_mod.validate_artifact

assemble_mod = import_module("assemble-template")
assemble_template = assemble_mod.assemble_template

slop = import_module("css_slop_rules")
scan_css = slop.scan_css

STAMP_RE = re.compile(r"/\* vexjoy-artifact: shape=(\S+) theme=(\S+) contrast=(pass|fail|n/a) \*/")

# Clean CSS: no slop patterns.
CLEAN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clean</title>
    <style>
    body { color: #111111; background-color: #ffffff; }
    .card { transition: opacity 150ms, transform 150ms; }
    h1 { color: #222222; }
    </style>
</head>
<body><h1>Hello</h1><p>content</p></body>
</html>"""

# Slop CSS: transition-all + gradient-text-headline on h1.
SLOP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Slop</title>
    <style>
    .card { transition: all 200ms ease; }
    h1 { background-clip: text; -webkit-background-clip: text; }
    </style>
</head>
<body><h1>Headline</h1><p>content</p></body>
</html>"""


def _write_tmp(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


class TestSlopScanWiring:
    """The vendored scan_css fires on slop and stays silent on clean CSS."""

    def test_clean_css_no_slop_warnings(self) -> None:
        path = _write_tmp(CLEAN_HTML)
        try:
            result = validate_artifact(path)
            assert result.checks["css_slop_clean"] is True
            assert not any(w.startswith("CSS slop") for w in result.warnings)
            # Slop warnings are non-blocking — clean file is still valid.
            assert result.valid
        finally:
            path.unlink()

    def test_slop_css_emits_warnings(self) -> None:
        path = _write_tmp(SLOP_HTML)
        try:
            result = validate_artifact(path)
            assert result.checks["css_slop_clean"] is False
            slop_warnings = [w for w in result.warnings if w.startswith("CSS slop")]
            assert any("transition-all" in w for w in slop_warnings)
            assert any("gradient-text-headline" in w for w in slop_warnings)
        finally:
            path.unlink()

    def test_slop_is_non_blocking(self) -> None:
        # Structurally valid file with slop: warnings only, exit-equivalent valid.
        path = _write_tmp(SLOP_HTML)
        try:
            result = validate_artifact(path)
            assert result.valid
        finally:
            path.unlink()

    def test_scan_shape_agnostic(self) -> None:
        # Same slop CSS flagged regardless of declared shape (report has no hero).
        path = _write_tmp(SLOP_HTML)
        try:
            for shape in ("report", "data-viz", "spec", "deck"):
                result = validate_artifact(path, shape=shape)
                assert result.checks["css_slop_clean"] is False
        finally:
            path.unlink()

    def test_oversized_file_still_scanned_fast(self) -> None:
        # The slop scanner is linear, so oversized files are scanned, not skipped.
        # Slop in an oversized file is still flagged; the size check fires
        # independently. Must complete quickly, not hang.
        import time

        path = _write_tmp(SLOP_HTML + ("x" * (501 * 1024)))
        try:
            start = time.perf_counter()
            result = validate_artifact(path)
            assert time.perf_counter() - start < 1.0
            assert result.checks["css_slop_clean"] is False
            assert not result.checks["reasonable_size"]
        finally:
            path.unlink()

    def test_oversized_single_line_does_not_hang(self) -> None:
        # Adversarial ~1MB minified single line: the old O(n^2) block regex hung.
        import time

        unit = '<div class="btn cta" style="color:#111;background:#222">x</div>'
        path = _write_tmp("<html><body>" + unit * 16000 + "</body></html>")
        try:
            start = time.perf_counter()
            validate_artifact(path)
            assert time.perf_counter() - start < 1.0
        finally:
            path.unlink()


class TestVendoredModuleParity:
    """The vendored scan_css is the same engine as the source module."""

    def test_findings_match_direct_scan(self) -> None:
        findings = scan_css(SLOP_HTML)
        rule_ids = {f.rule_id for f in findings}
        assert "transition-all" in rule_ids
        assert "gradient-text-headline" in rule_ids

    def test_clean_css_no_findings(self) -> None:
        assert scan_css(CLEAN_HTML) == []


class TestStampEmission:
    """assemble-template.py emits a parseable vexjoy-artifact stamp."""

    def test_stamp_present_and_parseable(self) -> None:
        html = assemble_template("spec", "Test")
        m = STAMP_RE.search(html)
        assert m is not None
        assert m.group(1) == "spec"
        assert m.group(2) == "birchline"
        assert m.group(3) == "n/a"

    def test_stamp_is_first_css_comment(self) -> None:
        html = assemble_template("report", "Test")
        style_open = html.index("<style>")
        first_comment = html.index("/*", style_open)
        assert html[first_comment:].startswith("/* vexjoy-artifact:")

    def test_stamp_reflects_theme_override(self) -> None:
        html = assemble_template("spec", "Test", theme="dark-focus")
        m = STAMP_RE.search(html)
        assert m is not None
        assert m.group(2) == "dark-focus"

    def test_stamp_per_shape_default_theme(self) -> None:
        html = assemble_template("code-review", "Test")
        m = STAMP_RE.search(html)
        assert m is not None
        assert m.group(1) == "code-review"
        assert m.group(2) == "dark-focus"

    def test_stamp_survives_validation_as_clean(self) -> None:
        # The stamp itself must not trip any slop rule.
        html = assemble_template("report", "Stamped")
        path = _write_tmp(html)
        try:
            result = validate_artifact(path)
            stamp_warnings = [w for w in result.warnings if "vexjoy-artifact" in w]
            assert stamp_warnings == []
        finally:
            path.unlink()
