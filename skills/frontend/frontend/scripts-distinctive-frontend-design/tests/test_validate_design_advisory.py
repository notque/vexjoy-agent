"""Tests that validate_design.py treats context-dependent picks as warnings.

Fonts and palettes that suit some surfaces but not others (see
skills/shared-patterns/ui-design-judgment.md) must warn, not fail, and the CLI
must exit 0 unless --strict is passed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import import_module
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "validate_design.py"
sys.path.insert(0, str(SCRIPT.parent))
vd = import_module("validate_design")


def _palette(tmp_path: Path, accent: str) -> Path:
    p = tmp_path / "palette.json"
    p.write_text(
        json.dumps(
            {
                "palette_name": "Test",
                "dominant": {"bg": "#FFFFFF"},
                "secondary": {"surface": "#F4F4F5"},
                "accent": {"primary": accent},
            }
        ),
        encoding="utf-8",
    )
    return p


def test_reflexive_font_warns_not_fails():
    score, passed, _, warnings = vd.validate_fonts(["Inter"], "proj")
    assert passed is True
    assert score > 0
    assert any("reflexive font pick" in w for w in warnings)


def test_font_match_is_whole_word():
    _, passed, _, warnings = vd.validate_fonts(["Interstate"], "proj")
    assert passed is True
    assert not any("reflexive font pick" in w for w in warnings)


def test_common_palette_warns_not_fails(tmp_path):
    score, passed, _, warnings = vd.validate_palette(_palette(tmp_path, "#3B82F6"))
    assert passed is True
    assert score > 0
    assert any("common default palette" in w for w in warnings)


def test_pure_white_dominant_is_fine(tmp_path):
    _, _, _, warnings = vd.validate_palette(_palette(tmp_path, "#C2410C"))
    assert not any("pure" in w.lower() for w in warnings)


def _run(tmp_path: Path, *extra: str) -> int:
    palette = _palette(tmp_path, "#3B82F6")
    cmd = [sys.executable, str(SCRIPT), "--fonts", "Inter,Roboto", "--palette", str(palette), "--project", "t"]
    # Keep project-history writes out of the repo: run a copy of the script in tmp.
    copy = tmp_path / "scripts" / "validate_design.py"
    copy.parent.mkdir(exist_ok=True)
    copy.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    cmd[1] = str(copy)
    return subprocess.run([*cmd, *extra], capture_output=True, text=True).returncode


def test_cli_advisory_exit_zero(tmp_path):
    assert _run(tmp_path) == 0


def test_cli_strict_exits_one_below_80(tmp_path):
    assert _run(tmp_path, "--strict") == 1


def _emitted(tmp_path: Path, css: str) -> Path:
    # The tmp copy of validate_design.py imports css_slop_rules from its own folder.
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    rules = SCRIPT.parent / "css_slop_rules.py"
    (scripts / rules.name).write_text(rules.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out.css"
    out.write_text(css, encoding="utf-8")
    return out


def test_cli_invisible_text_exits_one_without_strict(tmp_path):
    css = _emitted(tmp_path, ".x { color: #1a1a1a; background-color: #1e1e1e; }")
    assert _run(tmp_path, "--emitted-css", str(css)) == 1


def test_cli_low_contrast_warning_stays_advisory(tmp_path):
    css = _emitted(tmp_path, ".w { color: oklch(0.30 0.02 250); background-color: oklch(0.35 0.02 250); }")
    assert _run(tmp_path, "--emitted-css", str(css)) == 0
