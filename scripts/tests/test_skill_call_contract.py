"""Skill-tool call contract.

The repo-wide scan runs as `scripts/validate-references.py --check-skill-calls`
(a CI step). These tests prove that check catches each bad fixture, plus one
runtime constant that must route to an indexed skill.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
validate_references = importlib.import_module("validate-references")


def _repo(tmp_path: Path, command: str, skill_body: str = "# Demo\n") -> Path:
    """Build a minimal repo: one command, one skill, one pipeline-only entry."""
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "demo.md").write_text(command, encoding="utf-8")
    skill = tmp_path / "skills" / "cat" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(skill_body, encoding="utf-8")
    (tmp_path / "skills" / "INDEX.json").write_text(json.dumps({"skills": {"workflow": {}}}), encoding="utf-8")
    pipelines = tmp_path / "skills" / "process" / "workflow" / "references" / "pipeline-index.json"
    pipelines.parent.mkdir(parents=True)
    pipelines.write_text(json.dumps({"pipelines": {"deep-pipe": {}}}), encoding="utf-8")
    return tmp_path


GOOD_COMMAND = "---\nallowed-tools: [Skill]\n---\nCall the Skill tool with `workflow`.\n"


def test_check_skill_calls_passes_clean_repo(tmp_path: Path) -> None:
    assert validate_references.check_skill_calls(_repo(tmp_path, GOOD_COMMAND)) == []


def test_check_skill_calls_flags_missing_skill_tool_grant(tmp_path: Path) -> None:
    command = "---\nallowed-tools: [Read]\n---\nCall the Skill tool with `workflow`.\n"
    failures = validate_references.check_skill_calls(_repo(tmp_path, command))
    assert failures == ["commands/demo.md: calls the Skill tool but allowed-tools lacks Skill"]


def test_check_skill_calls_flags_legacy_command_handoff(tmp_path: Path) -> None:
    command = GOOD_COMMAND + "Read and follow the skill at skills/x/SKILL.md.\n"
    failures = validate_references.check_skill_calls(_repo(tmp_path, command))
    assert len(failures) == 1 and "legacy skill handoff wording" in failures[0]


def test_check_skill_calls_flags_direct_pipeline_handoff(tmp_path: Path) -> None:
    root = _repo(tmp_path, GOOD_COMMAND, "# Demo\n\nThen hand off to `deep-pipe` for phases.\n")
    failures = validate_references.check_skill_calls(root)
    assert failures == ["skills/cat/demo/SKILL.md:3: direct handoff to pipeline 'deep-pipe'"]


def test_debug_error_remediation_uses_indexed_workflow_skill(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "hooks/lib"))
    default_fix_actions = importlib.import_module("learning_db_v2").DEFAULT_FIX_ACTIONS

    for error_type in ("syntax_error", "type_error"):
        assert default_fix_actions[error_type] == {"fix_type": "skill", "fix_action": "workflow"}
