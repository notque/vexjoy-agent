from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "validate_positive_instruction_docs",
    _SCRIPTS_DIR / "validate_positive_instruction_docs.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_positive_instruction_docs"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_scan_file_flags_negative_heading(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Anti-Patterns\n", encoding="utf-8")
    _mod.REPO_ROOT = tmp_path
    violations = _mod.scan_file(path)
    assert len(violations) == 1
    assert violations[0].pattern == "Anti-Pattern"


def test_scan_file_skips_fenced_text(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("```md\nDo NOT use this\n```\n", encoding="utf-8")
    _mod.REPO_ROOT = tmp_path
    violations = _mod.scan_file(path)
    assert violations == []
