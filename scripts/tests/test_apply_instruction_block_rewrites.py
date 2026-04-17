from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "apply_instruction_block_rewrites",
    _SCRIPTS_DIR / "apply_instruction_block_rewrites.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["apply_instruction_block_rewrites"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_replace_block_updates_expected_range(tmp_path: Path) -> None:
    path = tmp_path / "sample.md"
    path.write_text("## Anti-Patterns\n\nDo NOT use git add -A\n\n## Next\n", encoding="utf-8")
    original = "## Anti-Patterns\n\nDo NOT use git add -A"
    changed = _mod.replace_block(
        path,
        1,
        3,
        _mod.block_sha(original),
        "## Preferred Actions\n\nStage files by name with `git add path/to/file`.",
    )
    assert changed is True
    text = path.read_text(encoding="utf-8")
    assert "## Preferred Actions" in text
    assert "## Next" in text
