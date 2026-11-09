"""Skill-tool call contract.

The repo-wide scan runs as `scripts/validate-references.py --check-skill-calls`
(a CI step). These tests prove that check catches each bad fixture.
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


def test_check_skill_calls_flags_call_to_a_skill_that_does_not_exist(tmp_path: Path) -> None:
    root = _repo(tmp_path, GOOD_COMMAND, "# Demo\n\nCall the Skill tool with `read-only-ops`.\n")
    failures = validate_references.check_skill_calls(root)
    assert failures == [
        "skills/cat/demo/SKILL.md:3: calls the Skill tool with 'read-only-ops', which is no indexed skill or command"
    ]


def test_check_skill_calls_accepts_indexed_skills_and_command_names(tmp_path: Path) -> None:
    body = "# Demo\n\nCall the Skill tool with `workflow`. Then call the Skill tool with `demo`.\n"
    assert validate_references.check_skill_calls(_repo(tmp_path, GOOD_COMMAND, body)) == []


def test_check_skill_calls_skips_tests_for_unknown_names(tmp_path: Path) -> None:
    root = _repo(tmp_path, GOOD_COMMAND)
    fixture = root / "hooks" / "tests" / "test_demo.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('EXPECTED = "Call the Skill tool with `inst-skill`."\n', encoding="utf-8")
    assert validate_references.check_skill_calls(root) == []


def _dispatch_repo(tmp_path: Path, skill_body: str) -> Path:
    """Add one real agent to the minimal repo, so dispatch names have something to resolve to."""
    root = _repo(tmp_path, GOOD_COMMAND, skill_body)
    (root / "agents").mkdir()
    (root / "agents" / "real-engineer.md").write_text("# real-engineer\n", encoding="utf-8")
    return root


def test_check_skill_calls_flags_dispatch_of_an_agent_that_does_not_exist(tmp_path: Path) -> None:
    body = '# Demo\n\nagent(prompt, {agentType: "reviewer-language-specialist"})\n[do-route] agent=ghost-engineer\n'
    failures = validate_references.check_skill_calls(_dispatch_repo(tmp_path, body))
    assert failures == [
        "skills/cat/demo/SKILL.md:3: dispatches agent 'reviewer-language-specialist', which is no indexed agent",
        "skills/cat/demo/SKILL.md:4: dispatches agent 'ghost-engineer', which is no indexed agent",
    ]


def test_check_skill_calls_flags_dispatch_of_a_skill_that_does_not_exist(tmp_path: Path) -> None:
    body = (
        '# Demo\n\n{agentType: "real-engineer", skills: ["workflow", "systematic-code-review"]}\n'
        '{"agent": "real-engineer", "skill": "auto-pipeline"}\n'
    )
    failures = validate_references.check_skill_calls(_dispatch_repo(tmp_path, body))
    assert failures == [
        "skills/cat/demo/SKILL.md:3: dispatches skill 'systematic-code-review', which is no indexed skill or command",
        "skills/cat/demo/SKILL.md:4: dispatches skill 'auto-pipeline', which is no indexed skill or command",
    ]


def test_check_skill_calls_accepts_real_builtin_and_placeholder_dispatch_names(tmp_path: Path) -> None:
    body = (
        '# Demo\n\n{"agent": "real-engineer", "skill": "workflow", "skills": ["demo"]}\n'
        '{"agent": "general-purpose", "skill": "<skill; omit when agent-only>"}\n'
        "[do-route] agent=main skill={s} complexity={c}\n"
        'Agent(subagent_type: "Explore") then agent={a} skill=workflow\n'
    )
    assert validate_references.check_skill_calls(_dispatch_repo(tmp_path, body)) == []


def test_check_skill_calls_reads_agents_from_the_index_and_do_references(tmp_path: Path) -> None:
    root = _dispatch_repo(tmp_path, "# Demo\n")
    (root / "agents" / "INDEX.json").write_text(json.dumps({"agents": {"indexed-engineer": {}}}), encoding="utf-8")
    ref = root / "skills" / "meta" / "do" / "references" / "dispatch.md"
    ref.parent.mkdir(parents=True)
    ref.write_text('{agentType: "indexed-engineer"}\n{agentType: "workflow-orchestrator"}\n', encoding="utf-8")
    assert validate_references.check_skill_calls(root) == [
        "skills/meta/do/references/dispatch.md:2: dispatches agent 'workflow-orchestrator', which is no indexed agent"
    ]
