"""Negative-results registry check (`validate-doc-links.py --check-negative-results`).

The registry is doc-backed: `docs/what-didnt-work.md`. The repo check is a CI
step; these tests prove it passes a well-formed registry and catches each
kind of bad entry.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
doc_links = importlib.import_module("validate-doc-links")

GOOD_ENTRY = """## 2026-07-01 Provenance footers
**Expectation**: footers help.
**What happened**: nobody read them.
**Evidence**: docs/x.md line 4
**Decision**: rejected
"""


def _registry(tmp_path: Path, body: str, link: bool = True) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "what-didnt-work.md").write_text("# What didn't work\n\n" + body, encoding="utf-8")
    link_text = "See docs/what-didnt-work.md.\n" if link else "Nothing here.\n"
    (tmp_path / "CONTRIBUTING.md").write_text(link_text, encoding="utf-8")
    skill = tmp_path / "skills" / "process" / "process" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(link_text, encoding="utf-8")
    return tmp_path


def test_well_formed_registry_passes(tmp_path: Path) -> None:
    assert doc_links.check_negative_results(_registry(tmp_path, GOOD_ENTRY)) == []


def test_real_registry_passes() -> None:
    assert doc_links.check_negative_results(REPO_ROOT) == []


def test_bad_entry_is_caught(tmp_path: Path) -> None:
    bad = GOOD_ENTRY.replace("**What happened**", "What happened").replace("rejected", "maybe")
    bad = bad.replace("docs/x.md line 4", "we just knew") + "Dash " + chr(0x2014) + " here\n"
    failures = "\n".join(doc_links.check_negative_results(_registry(tmp_path, bad, link=False)))
    assert "missing **What happened**" in failures
    assert "Decision must be" in failures
    assert "Evidence must name a location" in failures
    assert "em or en dash" in failures
    assert "CONTRIBUTING.md does not link" in failures
    assert "skills/process/process/SKILL.md does not link" in failures


def test_missing_or_empty_registry_is_caught(tmp_path: Path) -> None:
    assert doc_links.check_negative_results(tmp_path) == ["docs/what-didnt-work.md is missing"]
    (tmp_path / "e").mkdir()
    empty = _registry(tmp_path / "e", "no entries yet\n")
    assert any("no dated" in f for f in doc_links.check_negative_results(empty))
