"""Focused contracts for governance documentation that drives execution."""

from __future__ import annotations

import json
import re
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


def test_workflow_catalog_targets_resolve() -> None:
    """Every public target named by the workflow catalog must load."""
    workflow = REPO_ROOT / "skills/workflow/SKILL.md"
    targets = re.findall(r"`((?:references|skills)/[^`]+\.md)`", workflow.read_text())

    assert targets
    for target in targets:
        if "..." in target:
            continue
        resolved = workflow.parent / target if target.startswith("references/") else REPO_ROOT / target
        assert resolved.is_file(), f"workflow catalog target is missing: {target}"


def test_content_pipeline_targets_resolve() -> None:
    """Public content routes cannot depend on files outside this repository."""
    index = json.loads((REPO_ROOT / "skills/workflow/references/pipeline-index.json").read_text())
    for pipeline in index["pipelines"].values():
        if pipeline.get("category") == "content":
            assert (REPO_ROOT / pipeline["file"]).is_file(), pipeline["file"]


def test_create_voice_has_no_missing_public_file_reference() -> None:
    """The public voice-creation skill must rely only on checked-in files."""
    skill = (REPO_ROOT / "skills/content/create-voice/SKILL.md").read_text()
    refs = re.findall(r"`(skills/[^`]+)`", skill)

    for ref in refs:
        if "{" not in ref and "*" not in ref:
            assert (REPO_ROOT / ref).exists(), f"create-voice reference is missing: {ref}"


def test_structural_scores_are_advisory_not_severity_mappings() -> None:
    """Static score bands cannot alone create HIGH or CRITICAL findings."""
    skill = (REPO_ROOT / "skills/research/full-repo-review/SKILL.md").read_text()
    playbook = (REPO_ROOT / "skills/research/full-repo-review/references/audit-playbook.md").read_text()

    assert "score alone never determines severity" in skill
    assert "score alone never determines severity" in playbook
    assert "grades F and D are CRITICAL" not in skill
    assert "maps to CRITICAL severity" not in playbook
