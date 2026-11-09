"""Tests for scripts/audit-reference-depth.py: which components the audit scans."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "audit-reference-depth.py"
_spec = importlib.util.spec_from_file_location("audit_reference_depth", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_reference_depth"] = audit
_spec.loader.exec_module(audit)

DEEP_REF = "# Patterns\n\n```bash\ngrep -rn 'func main(' .\n```\n\nGo 1.22+ changed loop variables.\n" * 20


def write(path: Path, text: str = "# doc\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with one agent, a category-nested skill, a nested ``skill/`` layout, and a flat skill."""
    root = tmp_path / "repo"
    write(root / "agents" / "go-engineer.md")
    write(root / "agents" / "go-engineer" / "references" / "patterns.md", DEEP_REF)
    write(root / "skills" / "meta" / "router" / "SKILL.md")
    write(root / "skills" / "meta" / "router" / "references" / "rules.md", DEEP_REF)
    write(root / "skills" / "voice" / "narrator" / "skill" / "SKILL.md")
    write(root / "skills" / "flat" / "SKILL.md")
    # Reference content shaped like a skill is not a skill.
    write(root / "skills" / "meta" / "router" / "references" / "example" / "SKILL.md")
    monkeypatch.setattr(audit, "_REPO_ROOT", root)
    monkeypatch.setattr(audit, "_REPO_AGENTS_DIR", root / "agents")
    monkeypatch.setattr(audit, "_REPO_SKILLS_DIR", root / "skills")
    monkeypatch.setattr(audit, "_CLAUDE_AGENTS_DIR", tmp_path / "none" / "agents")
    monkeypatch.setattr(audit, "_CLAUDE_SKILLS_DIR", tmp_path / "none" / "skills")
    return root


def test_scan_all_finds_skills_at_every_nesting_depth(repo: Path) -> None:
    results = audit.scan_all()

    assert sorted(r.name for r in results if r.kind == "skill") == ["flat", "narrator", "router"]
    assert [r.name for r in results if r.kind == "agent"] == ["go-engineer"]


def test_category_nested_skill_is_scored_from_its_references(repo: Path) -> None:
    by_name = {r.name: r for r in audit.scan_all() if r.kind == "skill"}

    assert by_name["router"].ref_dir == repo / "skills" / "meta" / "router" / "references"
    assert by_name["router"].level >= 2
    assert by_name["flat"].level == 0


def test_references_in_subdirectories_are_measured(repo: Path) -> None:
    write(repo / "skills" / "flat" / "references" / "go" / "patterns.md", DEEP_REF)

    by_name = {r.name: r for r in audit.scan_all() if r.kind == "skill"}

    assert len(by_name["flat"].ref_files) == 1
    assert by_name["flat"].level >= 2


def test_scan_single_finds_a_nested_skill_by_name(repo: Path) -> None:
    result = audit.scan_single("router", "skill")

    assert result is not None
    assert result.md_path == repo / "skills" / "meta" / "router" / "SKILL.md"
    assert audit.scan_single("example", "skill") is None
    assert audit.scan_single("absent", "skill") is None
