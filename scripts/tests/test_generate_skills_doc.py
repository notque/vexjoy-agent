"""Tests for scripts/generate-skills-doc.py.

Run with: python3 -m pytest scripts/tests/test_generate_skills_doc.py -v
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate-skills-doc.py"

_spec = importlib.util.spec_from_file_location("generate_skills_doc", SCRIPT)
assert _spec and _spec.loader
gsd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsd)


def _entries() -> list[dict]:
    return gsd.strip_private(gsd.load_entries(REPO_ROOT), gsd._private_names(REPO_ROOT))


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO_ROOT)


def test_render_is_idempotent(tmp_path: Path) -> None:
    """Two renders to different paths are byte-identical."""
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    assert _run("--doc-path", str(a)).returncode == 0
    assert _run("--doc-path", str(b)).returncode == 0
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def test_every_rendered_name_has_skill_md(tmp_path: Path) -> None:
    """Every skill named in the catalog has a SKILL.md on disk."""
    out = tmp_path / "skills.md"
    assert _run("--doc-path", str(out)).returncode == 0
    names = re.findall(r"^\| `([^`]+)` \|", out.read_text(encoding="utf-8"), re.MULTILINE)
    assert names
    on_disk = {p.parent.name for p in (REPO_ROOT / "skills").rglob("SKILL.md")}
    assert set(names) <= on_disk
    assert len(names) == len(set(names))


def test_frontmatter_preserved(tmp_path: Path) -> None:
    """The docs-catalog frontmatter survives generation."""
    text = gsd.generate_doc(_entries())
    assert text.startswith('---\nsummary: "')
    assert "read_when:" in text.split("\n---\n", 1)[0]


def test_check_passes_fresh_and_fails_edited(tmp_path: Path) -> None:
    """--check exits 0 on a fresh render and 1 after a hand edit."""
    doc = tmp_path / "skills.md"
    assert _run("--doc-path", str(doc)).returncode == 0
    assert _run("--check", "--doc-path", str(doc)).returncode == 0
    doc.write_text(doc.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8")
    result = _run("--check", "--doc-path", str(doc))
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_user_invocable_marker() -> None:
    """User-invocable skills get a /name marker; others do not."""
    text = gsd.generate_doc(
        [
            {"name": "alpha", "description": "a | b", "category": "x-y", "user_invocable": True},
            {"name": "beta", "description": "b", "category": "x-y", "user_invocable": False},
        ]
    )
    assert "| `alpha` | a \\| b | `/alpha` |" in text
    assert "| `beta` | b |  |" in text
    assert "## X Y" in text


def test_committed_doc_is_current() -> None:
    """The committed docs/skills.md matches a fresh render."""
    assert _run("--check").returncode == 0
