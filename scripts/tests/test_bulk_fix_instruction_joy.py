from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bulk_fix_instruction_joy", _SCRIPTS_DIR / "bulk_fix_instruction_joy.py")
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["bulk_fix_instruction_joy"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_scan_file_marks_safe_heading_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Anti-Patterns\n\nBody\n", encoding="utf-8")
    findings = _mod.scan_file(path)
    assert len(findings) == 1
    assert findings[0].safe_fix == "## Patterns to Detect and Fix"


def test_apply_safe_rewrites_rewrites_heading_only(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Anti-Patterns\n\n### FORBIDDEN Patterns (HARD GATE)\n", encoding="utf-8")
    changed = _mod.apply_safe_rewrites(path)
    assert changed == 2
    text = path.read_text(encoding="utf-8")
    assert "## Patterns to Detect and Fix" in text
    assert "### Hard Gate Patterns" in text


def test_apply_safe_rewrites_skips_code_fence(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("```md\n## Anti-Patterns\n```\n", encoding="utf-8")
    changed = _mod.apply_safe_rewrites(path)
    assert changed == 0
    assert path.read_text(encoding="utf-8") == "```md\n## Anti-Patterns\n```\n"
