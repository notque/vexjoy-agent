from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "extract_negative_instruction_blocks",
    _SCRIPTS_DIR / "extract_negative_instruction_blocks.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_negative_instruction_blocks"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_extracts_negative_heading_block(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Anti-Patterns\n\nDo NOT use this.\n", encoding="utf-8")
    _mod.REPO_ROOT = tmp_path
    blocks = _mod.extract_blocks(path)
    assert len(blocks) == 1
    assert "Anti-Pattern" in blocks[0].hit_patterns
    assert blocks[0].heading == "## Anti-Patterns"


def test_ignores_code_fence_content(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Example\n\n```md\nDo NOT use this\n```\n", encoding="utf-8")
    _mod.REPO_ROOT = tmp_path
    blocks = _mod.extract_blocks(path)
    assert blocks == []
