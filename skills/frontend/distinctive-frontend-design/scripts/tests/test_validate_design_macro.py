"""Tests for the macrostructure + emitted-CSS additions to validate_design.py.

Covers: variety step-down on repeated macrostructure, back-compat with old
history entries (no macrostructure field), history write of the new field,
stamp parsing, and the emitted-CSS slop scan helper.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
vd = import_module("validate_design")


def _patch_history(monkeypatch, tmp_path, projects):
    """Point validate_design's history lookups at a real temp file.

    skill_dir = Path(__file__).parent.parent, so faking __file__ to
    tmp/scripts/validate_design.py makes the history land at tmp/references/.
    """
    (tmp_path / "references").mkdir(exist_ok=True)
    hist = tmp_path / "references" / "project-history.json"
    hist.write_text(json.dumps({"projects": projects}), encoding="utf-8")
    fake_script = tmp_path / "scripts" / "validate_design.py"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vd, "__file__", str(fake_script))
    return hist


# --- variety penalty on repeated macrostructure ---


def test_macro_repeat_penalizes(monkeypatch, tmp_path):
    _patch_history(
        monkeypatch,
        tmp_path,
        [{"name": "prev", "fonts": ["A", "B"], "palette_name": "X", "macrostructure": "macro:bento"}],
    )
    score, details = vd.calculate_variety_score("new", ["C", "D"], "Y", "macro:bento")
    assert score == 70
    assert "macro:bento" in details


def test_macro_distinct_no_penalty(monkeypatch, tmp_path):
    _patch_history(
        monkeypatch,
        tmp_path,
        [{"name": "prev", "fonts": ["A", "B"], "palette_name": "X", "macrostructure": "macro:bento"}],
    )
    score, _ = vd.calculate_variety_score("new", ["C", "D"], "Y", "macro:timeline")
    assert score == 90


# --- back-compat: old entries lack the macrostructure field ---


def test_old_entry_without_macro_loads(monkeypatch, tmp_path):
    _patch_history(
        monkeypatch,
        tmp_path,
        [{"name": "prev", "fonts": ["A", "B"], "palette_name": "X", "timestamp": "2025-01-01"}],
    )
    # No KeyError; a new macro is simply not a repeat.
    score, _ = vd.calculate_variety_score("new", ["C", "D"], "Y", "macro:bento")
    assert score == 90


def test_empty_macro_never_penalizes(monkeypatch, tmp_path):
    _patch_history(
        monkeypatch,
        tmp_path,
        [{"name": "prev", "fonts": ["A", "B"], "palette_name": "X", "macrostructure": "macro:bento"}],
    )
    score, _ = vd.calculate_variety_score("new", ["C", "D"], "Y", "")
    assert score == 90


# --- history write includes the field ---


def test_update_history_writes_macro(tmp_path, monkeypatch):
    # skill_dir = Path(__file__).parent.parent, so faking __file__ at tmp/scripts/x.py
    # makes skill_dir == tmp and the history file land in tmp/references/.
    (tmp_path / "references").mkdir()
    hist = tmp_path / "references" / "project-history.json"
    fake_script = tmp_path / "scripts" / "validate_design.py"
    fake_script.parent.mkdir(parents=True)

    orig_file = vd.__file__
    try:
        monkeypatch.setattr(vd, "__file__", str(fake_script))
        vd.update_project_history("proj", ["F1", "F2"], "Pal", "macro:gallery-grid")
        rec = json.loads(hist.read_text(encoding="utf-8"))["projects"][-1]
        assert rec["macrostructure"] == "macro:gallery-grid"
        assert rec["name"] == "proj"
        assert "timestamp" in rec
    finally:
        vd.__file__ = orig_file


# --- stamp parsing ---


def test_read_macro_from_stamp():
    css = "/* vexjoy-design: macro=macro:split-hero theme=Dusk contrast=pass nav=top footer=slim mobile=pass */\nbody{}"
    assert vd.read_macro_from_stamp(css) == "macro:split-hero"


def test_read_macro_from_stamp_absent():
    assert vd.read_macro_from_stamp("body { color: #111; }") == ""


# --- emitted-css slop scan helper ---


def test_scan_emitted_css(tmp_path):
    f = tmp_path / "out.css"
    f.write_text(".btn { transition: all 0.2s; }", encoding="utf-8")
    findings = vd.scan_emitted_css(f)
    assert any(x["rule_id"] == "transition-all" for x in findings)


def test_scan_emitted_css_clean(tmp_path):
    f = tmp_path / "out.css"
    f.write_text(".btn { transition: opacity 0.2s; }", encoding="utf-8")
    assert vd.scan_emitted_css(f) == []
