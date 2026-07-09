"""Focused contracts for governance documentation that drives execution."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_full_repo_review_runs_all_four_waves() -> None:
    skill = (REPO_ROOT / "skills/research/full-repo-review/SKILL.md").read_text()
    report = (REPO_ROOT / "skills/research/full-repo-review/references/report-template.md").read_text()

    assert "Wave 0, Wave 1, Wave 2, and Wave 3" in skill
    assert "Waves executed: 0, 1, 2, 3" in skill
    assert "**Waves executed**: 0, 1, 2, 3" in report


def test_agent_evaluation_has_one_executable_structural_scorer() -> None:
    skill = (REPO_ROOT / "skills/meta/agent-evaluation/SKILL.md").read_text()
    legacy_scorer = REPO_ROOT / "skills/meta/agent-evaluation/scripts/validate.py"

    assert "scripts/score-component.py" in skill
    assert not legacy_scorer.exists()


def test_support_directory_detection_is_shape_based() -> None:
    hook = (REPO_ROOT / "hooks/sync-to-user-claude.py").read_text()

    assert "def _is_support_dir(item: Path) -> bool:" in hook
    assert "has_md and not has_skill_subdir" in hook
    assert "child.is_dir() and _is_support_dir(child)" in hook
