#!/usr/bin/env python3
"""Tests for scripts/workflow-registry.py — auto-derived native-variant map.

Scans skills/workflow/references/*.js for the exported `meta.name` and maps
name -> script path. Absence of a meta.name means the file does not register
(its pipeline, if any, stays prose-only). The registry is derived, never
hand-maintained, so adding a *.js with a meta.name auto-registers it (R3).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "workflow-registry.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workflow_js"
REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("workflow_registry", SCRIPT)
wr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wr)


# --- meta.name parsing (the tolerant regex) ----------------------------------


def test_parse_inline_single_quotes():
    name = wr.parse_meta_name((FIXTURES / "inline-meta.js").read_text())
    assert name == "inline-pipeline"


def test_parse_multiline_key_order_independent():
    """name appearing after description, across lines, still parses."""
    name = wr.parse_meta_name((FIXTURES / "multiline-meta.js").read_text())
    assert name == "multiline-pipeline"


def test_parse_no_meta_returns_none():
    name = wr.parse_meta_name((FIXTURES / "no-meta.js").read_text())
    assert name is None


def test_parse_real_comprehensive_review_variant():
    """The shipped variant must register under its real meta.name."""
    js = (REPO_ROOT / "skills" / "workflow" / "references" / "comprehensive-review-workflow.js").read_text()
    assert wr.parse_meta_name(js) == "comprehensive-review-workflow"


# --- build_registry over a directory -----------------------------------------


def test_build_registry_skips_no_meta(tmp_path):
    reg = wr.build_registry(FIXTURES)
    assert reg["inline-pipeline"].endswith("inline-meta.js")
    assert reg["multiline-pipeline"].endswith("multiline-meta.js")
    # no-meta.js contributes no entry
    assert all(not p.endswith("no-meta.js") for p in reg.values())


def test_build_registry_empty_dir(tmp_path):
    assert wr.build_registry(tmp_path) == {}


def test_build_registry_missing_dir(tmp_path):
    assert wr.build_registry(tmp_path / "does-not-exist") == {}


# --- default scan registers the real variant ---------------------------------


def test_default_registry_includes_comprehensive_review():
    reg = wr.build_registry()
    assert "comprehensive-review-workflow" in reg
    assert reg["comprehensive-review-workflow"].endswith("comprehensive-review-workflow.js")


# --- CLI / JSON contract -----------------------------------------------------


def test_cli_exit_zero_and_json_map():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert isinstance(out, dict)
    assert "comprehensive-review-workflow" in out
