from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bulk_fix_do_framing", _SCRIPTS_DIR / "bulk_fix_do_framing.py")
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["bulk_fix_do_framing"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


class DummyFinding:
    def __init__(self, file: str, line_range: list[int], block_text: str):
        self.file = file
        self.line_range = line_range
        self.block_text = block_text


def test_classify_table_backed_antipattern_header() -> None:
    finding = DummyFinding(
        "agents/example.md",
        [10, 14],
        "## Anti-Patterns\n\n| Rationalization | Why It's Wrong | Required Action |\n|---|---|---|",
    )
    candidate = _mod.classify_finding(finding)
    assert candidate is not None
    assert candidate.action == "annotate"
    assert candidate.reason == "table-backed-section-header"


def test_classify_skips_real_antipattern_block() -> None:
    finding = DummyFinding(
        "skills/example/SKILL.md",
        [20, 25],
        "## Anti-Patterns\n\n**What it looks like**: Bad thing.\n\n**Why wrong**: Breaks.",
    )
    assert _mod.classify_finding(finding) is None


def test_insert_annotation_before_heading(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("## Anti-Patterns\n\n| A | B |\n", encoding="utf-8")
    changed = _mod.insert_annotation(path, 1, "<!-- no-pair-required: test -->")
    assert changed is True
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[0] == "<!-- no-pair-required: test -->"
    assert text[1] == "## Anti-Patterns"
