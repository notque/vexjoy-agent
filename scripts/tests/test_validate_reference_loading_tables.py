from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "validate_reference_loading_tables",
    _SCRIPTS_DIR / "validate_reference_loading_tables.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_reference_loading_tables"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def test_skill_with_references_requires_reference_loading_table(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "demo-skill"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "checklist.md").write_text("# Checklist\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")

    violations = _mod.validate_components(repo, ["skill"])

    assert len(violations) == 1
    assert violations[0].component == "demo-skill"
    assert violations[0].component_type == "skill"


def test_agent_with_parseable_table_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    refs_dir = repo / "agents" / "demo-agent" / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "patterns.md").write_text("# Patterns\n", encoding="utf-8")
    (repo / "agents" / "demo-agent.md").write_text(
        "\n".join(
            [
                "# Demo Agent",
                "",
                "## Reference Loading Table",
                "",
                "| Signal | Load reference |",
                "|---|---|",
                "| Build tasks | `patterns.md` |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    violations = _mod.validate_components(repo, ["agent"])

    assert violations == []


def test_paths_filter_limits_validation_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"

    skill_a = repo / "skills" / "skill-a"
    refs_a = skill_a / "references"
    refs_a.mkdir(parents=True)
    (refs_a / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (skill_a / "SKILL.md").write_text("# Skill A\n", encoding="utf-8")

    skill_b = repo / "skills" / "skill-b"
    refs_b = skill_b / "references"
    refs_b.mkdir(parents=True)
    (refs_b / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (skill_b / "SKILL.md").write_text(
        "\n".join(
            [
                "# Skill B",
                "",
                "## Reference Loading Table",
                "",
                "| Signal | Load These Files | Why |",
                "|---|---|---|",
                "| Validation phase | `references/rules.md` | Keeps routing thin |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    violations = _mod.validate_components(repo, ["skill"], [skill_a / "SKILL.md"])

    assert len(violations) == 1
    assert violations[0].component == "skill-a"


def test_do_skill_is_exempt_from_reference_loading_table_requirement(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    refs_dir = repo / "skills" / "do" / "references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "routing-tables.md").write_text("# Routing\n", encoding="utf-8")
    (repo / "skills" / "do" / "SKILL.md").write_text("# /do\n", encoding="utf-8")

    violations = _mod.validate_components(repo, ["skill"])

    assert violations == []
