"""Tests for Phase A validator gates: assembler marker + theme-toggle requirement."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

validate_mod = import_module("validate-artifact")
validate_artifact = validate_mod.validate_artifact
THEME_TOGGLE_REQUIRED_SHAPES = validate_mod.THEME_TOGGLE_REQUIRED_SHAPES


MARKER = "<!-- assembled by html-artifact v1.1 -->"


def _shell(body: str, *, marker: bool = True, head_extra: str = "") -> str:
    """Build a minimal valid HTML shell with controllable marker + body."""
    marker_line = f"    {MARKER}\n" if marker else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        f"{marker_line}"
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "    <title>Test</title>\n"
        "    <style>body { margin: 0; }</style>\n"
        f"{head_extra}"
        "</head>\n"
        f"{body}\n"
        "</html>"
    )


def _write(tmp_path: Path, html: str, name: str = "artifact.html") -> Path:
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    return p


def test_marker_required(tmp_path: Path) -> None:
    """HTML without the assembler marker must fail and message must mention rejection."""
    html = _shell("<body><h1>X</h1></body>", marker=False)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert not result.valid
    assert result.checks["has_assembler_marker"] is False
    assert any("Hand-authored HTML rejected" in e for e in result.errors)


def test_marker_present_passes(tmp_path: Path) -> None:
    """Synthesized HTML with marker + valid structure passes."""
    html = _shell("<body><h1>Hello</h1></body>", marker=True)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert result.valid, f"unexpected errors: {result.errors}"
    assert result.checks["has_assembler_marker"] is True


def test_theme_toggle_required_for_deck(tmp_path: Path) -> None:
    """Deck shape without any theme-toggle element must fail with 'Theme toggle missing'."""
    body = '<body data-shape="deck"><h1>Slides</h1></body>'
    html = _shell(body, marker=True)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert not result.valid
    assert result.checks["has_theme_toggle"] is False
    assert any("Theme toggle missing" in e for e in result.errors)


def test_theme_toggle_present_passes(tmp_path: Path) -> None:
    """Deck HTML with <button data-theme-toggle> passes."""
    body = '<body data-shape="deck"><button data-theme-toggle>Theme</button><h1>S</h1></body>'
    html = _shell(body, marker=True)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert result.valid, f"unexpected errors: {result.errors}"
    assert result.checks["has_theme_toggle"] is True


def test_theme_toggle_via_class_passes(tmp_path: Path) -> None:
    """<button class="theme-toggle"> (no data attr) also satisfies the gate."""
    body = '<body data-shape="deck"><button class="theme-toggle">T</button><h1>S</h1></body>'
    html = _shell(body, marker=True)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert result.valid, f"unexpected errors: {result.errors}"
    assert result.checks["has_theme_toggle"] is True


def test_theme_toggle_not_required_for_editor(tmp_path: Path) -> None:
    """'editor' shape is NOT in THEME_TOGGLE_REQUIRED_SHAPES; passes without toggle."""
    assert "editor" not in THEME_TOGGLE_REQUIRED_SHAPES, "Test premise broken: editor unexpectedly in required shapes"
    body = '<body data-shape="editor"><h1>Edit</h1></body>'
    html = _shell(body, marker=True)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert result.valid, f"unexpected errors: {result.errors}"
    assert "has_theme_toggle" not in result.checks


def test_validator_aggregates_failures(tmp_path: Path) -> None:
    """When BOTH marker and theme-toggle are missing, both errors are reported."""
    body = '<body data-shape="deck"><h1>S</h1></body>'
    html = _shell(body, marker=False)
    path = _write(tmp_path, html)
    result = validate_artifact(path)
    assert not result.valid
    assert any("Hand-authored HTML rejected" in e for e in result.errors)
    assert any("Theme toggle missing" in e for e in result.errors)
    assert result.checks["has_assembler_marker"] is False
    assert result.checks["has_theme_toggle"] is False
