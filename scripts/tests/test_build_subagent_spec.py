"""Unit tests for scripts/build-subagent-spec.py.

The repo's specialist agents are retired (plans/009): the Antigravity persona
is built from a skill. The agent-file path stays for private overlay agents.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "build-subagent-spec.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_subagent_spec", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def bss():
    return _load_module()


def test_resolve_specialist_category(bss):
    assert bss.resolve_specialist_category("programming") == "implementer"
    assert bss.resolve_specialist_category("frontend") == "implementer"
    assert bss.resolve_specialist_category("review") == "reviewer"
    assert bss.resolve_specialist_category("security") == "reviewer"
    assert bss.resolve_specialist_category("research") == "scout"
    assert bss.resolve_specialist_category("x", {"routing": {"category": "code-review"}}) == "reviewer"
    # Overlay agent names keep the name heuristics.
    assert bss.resolve_specialist_category("reviewer-acme") == "reviewer"
    assert bss.resolve_specialist_category("acme-coordinator") == "coordinator"


def test_resolve_tool_permissions(bss):
    assert bss.resolve_tool_permissions("implementer") == (True, False, False)
    assert bss.resolve_tool_permissions("builder") == (True, False, False)
    assert bss.resolve_tool_permissions("reviewer") == (False, False, False)
    assert bss.resolve_tool_permissions("auditor") == (False, False, False)
    assert bss.resolve_tool_permissions("scout") == (False, True, False)
    assert bss.resolve_tool_permissions("researcher") == (False, True, False)
    assert bss.resolve_tool_permissions("coordinator") == (True, True, True)
    assert bss.resolve_tool_permissions("planner") == (True, True, True)


def test_build_subagent_spec_from_skill_implementer(bss):
    spec = bss.build_subagent_spec(skill="programming", repo_root=ROOT)
    assert spec["Name"] == "programming-worker"
    assert spec["Description"]
    assert spec["category"] == "implementer"
    assert (spec["EnableWriteTools"], spec["EnableMCPTools"], spec["EnableSubagentTools"]) == (True, False, False)
    assert "`programming` skill's SKILL.md" in spec["SystemPrompt"]
    assert "Reference Loading Table" in spec["SystemPrompt"]
    assert "Worker Base Instructions" in spec["SystemPrompt"]
    assert spec["companion_skills"] == ["programming"]
    assert spec["define_subagent"]["Name"] == "programming-worker"
    assert spec["sdk_config"]["capabilities"]["enable_write_tools"] is True


def test_build_subagent_spec_from_skill_reviewer_and_scout(bss):
    review = bss.build_subagent_spec(skill="review", repo_root=ROOT)
    assert review["category"] == "reviewer"
    assert review["EnableWriteTools"] is False
    research = bss.build_subagent_spec(skill="research", repo_root=ROOT)
    assert research["category"] == "scout"
    assert research["EnableMCPTools"] is True


def test_build_subagent_spec_overrides(bss):
    spec = bss.build_subagent_spec(
        skill="review",
        repo_root=ROOT,
        category_override="coordinator",
        enable_write_override=True,
    )
    assert spec["category"] == "coordinator"
    assert spec["EnableWriteTools"] is True
    assert spec["EnableMCPTools"] is True
    assert spec["EnableSubagentTools"] is True


def test_overlay_agent_file_still_builds(bss, tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "skills" / "shared-patterns").mkdir(parents=True)
    (tmp_path / "skills" / "shared-patterns" / "base-instructions.md").write_text("# Base\n", encoding="utf-8")
    (tmp_path / "agents" / "acme-overlay-engineer.md").write_text(
        "---\nname: acme-overlay-engineer\ndescription: Private overlay agent.\n---\nYou are the acme agent.\n",
        encoding="utf-8",
    )
    spec = bss.build_subagent_spec("acme-overlay-engineer", repo_root=tmp_path)
    assert spec["Name"] == "acme-overlay-engineer"
    assert spec["category"] == "implementer"
    assert spec["SystemPrompt"].startswith("You are the acme agent.")
    assert "# Base" in spec["SystemPrompt"]


def test_missing_skill_and_agent_raise(bss):
    with pytest.raises(FileNotFoundError, match="Skill definition not found"):
        bss.build_subagent_spec(skill="non-existent-skill-xyz", repo_root=ROOT)
    with pytest.raises(FileNotFoundError, match="Agent definition not found"):
        bss.build_subagent_spec("non-existent-agent-xyz", repo_root=ROOT)
    with pytest.raises(ValueError):
        bss.build_subagent_spec(repo_root=ROOT)


def test_cli_execution():
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--skill", "programming"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["Name"] == "programming-worker"
    assert data["EnableWriteTools"] is True

    res_def = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--skill", "review", "--format", "define_subagent"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert res_def.returncode == 0, res_def.stderr
    data_def = json.loads(res_def.stdout)
    assert "SystemPrompt" in data_def
    assert data_def["EnableWriteTools"] is False
    assert "sdk_config" not in data_def

    res_sdk = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--skill", "research", "--format", "sdk"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert res_sdk.returncode == 0, res_sdk.stderr
    data_sdk = json.loads(res_sdk.stdout)
    assert data_sdk["name"] == "research-worker"
    assert data_sdk["capabilities"]["enable_mcp_tools"] is True

    res_none = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, check=False)
    assert res_none.returncode == 2


def test_cli_handles_non_dict_yaml_frontmatter_cleanly(tmp_path: Path):
    """CLI invocation must use scripts.lib.frontmatter and reject non-dict YAML safely."""
    agent_file = tmp_path / "list-agent.md"
    agent_file.write_text("---\n- item1\n- item2\n---\n\n# Body\nDo work.\n", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", str(agent_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["Name"] == "list-agent"
    assert "Do work." in data["SystemPrompt"]
