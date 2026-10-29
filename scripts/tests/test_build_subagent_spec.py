"""Unit tests for scripts/build-subagent-spec.py."""

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
    assert bss.resolve_specialist_category("python-general-engineer") == "implementer"
    assert bss.resolve_specialist_category("typescript-frontend-engineer") == "implementer"
    assert bss.resolve_specialist_category("reviewer-code") == "reviewer"
    assert bss.resolve_specialist_category("reviewer-system") == "reviewer"
    assert bss.resolve_specialist_category("research-subagent-executor") == "scout"
    assert bss.resolve_specialist_category("project-coordinator-engineer") == "coordinator"
    assert bss.resolve_specialist_category("pipeline-orchestrator-engineer") == "coordinator"
    assert bss.resolve_specialist_category("research-coordinator-engineer") == "coordinator"


def test_resolve_tool_permissions(bss):
    assert bss.resolve_tool_permissions("implementer") == (True, False, False)
    assert bss.resolve_tool_permissions("builder") == (True, False, False)
    assert bss.resolve_tool_permissions("reviewer") == (False, False, False)
    assert bss.resolve_tool_permissions("auditor") == (False, False, False)
    assert bss.resolve_tool_permissions("scout") == (False, True, False)
    assert bss.resolve_tool_permissions("researcher") == (False, True, False)
    assert bss.resolve_tool_permissions("coordinator") == (True, True, True)
    assert bss.resolve_tool_permissions("planner") == (True, True, True)


def test_build_subagent_spec_implementer(bss):
    spec = bss.build_subagent_spec("python-general-engineer", repo_root=ROOT)
    assert spec["Name"] == "python-general-engineer"
    assert "Python development" in spec["Description"]
    assert spec["EnableWriteTools"] is True
    assert spec["EnableMCPTools"] is False
    assert spec["EnableSubagentTools"] is False
    assert spec["category"] == "implementer"
    assert "Agent Base Instructions" in spec["SystemPrompt"]
    assert "You are an **operator** for Python software development" in spec["SystemPrompt"]

    # Verify define_subagent sub-dict
    define_payload = spec["define_subagent"]
    assert define_payload["Name"] == "python-general-engineer"
    assert define_payload["EnableWriteTools"] is True
    assert define_payload["EnableMCPTools"] is False
    assert define_payload["EnableSubagentTools"] is False

    # Verify sdk_config sub-dict
    sdk_cfg = spec["sdk_config"]
    assert sdk_cfg["name"] == "python-general-engineer"
    assert sdk_cfg["capabilities"]["enable_write_tools"] is True
    assert sdk_cfg["capabilities"]["enable_mcp_tools"] is False
    assert sdk_cfg["capabilities"]["enable_subagents"] is False


def test_build_subagent_spec_reviewer(bss):
    spec = bss.build_subagent_spec("reviewer-code", repo_root=ROOT)
    assert spec["Name"] == "reviewer-code"
    assert spec["EnableWriteTools"] is False
    assert spec["EnableMCPTools"] is False
    assert spec["EnableSubagentTools"] is False
    assert spec["category"] == "reviewer"


def test_build_subagent_spec_scout(bss):
    spec = bss.build_subagent_spec("research-subagent-executor", repo_root=ROOT)
    assert spec["Name"] == "research-subagent-executor"
    assert spec["EnableWriteTools"] is False
    assert spec["EnableMCPTools"] is True
    assert spec["EnableSubagentTools"] is False
    assert spec["category"] == "scout"


def test_build_subagent_spec_coordinator(bss):
    spec = bss.build_subagent_spec("project-coordinator-engineer", repo_root=ROOT)
    assert spec["Name"] == "project-coordinator-engineer"
    assert spec["EnableWriteTools"] is True
    assert spec["EnableMCPTools"] is True
    assert spec["EnableSubagentTools"] is True
    assert spec["category"] == "coordinator"


def test_build_subagent_spec_overrides(bss):
    spec = bss.build_subagent_spec(
        "reviewer-code",
        repo_root=ROOT,
        category_override="coordinator",
        enable_write_override=True,
    )
    assert spec["category"] == "coordinator"
    assert spec["EnableWriteTools"] is True
    assert spec["EnableMCPTools"] is True
    assert spec["EnableSubagentTools"] is True


def test_build_subagent_spec_missing_agent_raises(bss):
    with pytest.raises(FileNotFoundError, match="Agent definition not found"):
        bss.build_subagent_spec("non-existent-agent-xyz", repo_root=ROOT)


def test_cli_execution():
    cmd = [sys.executable, str(SCRIPT_PATH), "--agent", "python-general-engineer"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["Name"] == "python-general-engineer"
    assert data["EnableWriteTools"] is True

    # Test define_subagent format
    cmd_def = [sys.executable, str(SCRIPT_PATH), "--agent", "reviewer-code", "--format", "define_subagent"]
    res_def = subprocess.run(cmd_def, capture_output=True, text=True, cwd=ROOT, check=False)
    assert res_def.returncode == 0
    data_def = json.loads(res_def.stdout)
    assert "SystemPrompt" in data_def
    assert data_def["EnableWriteTools"] is False
    assert "sdk_config" not in data_def

    # Test sdk format
    cmd_sdk = [sys.executable, str(SCRIPT_PATH), "--agent", "research-subagent-executor", "--format", "sdk"]
    res_sdk = subprocess.run(cmd_sdk, capture_output=True, text=True, cwd=ROOT, check=False)
    assert res_sdk.returncode == 0
    data_sdk = json.loads(res_sdk.stdout)
    assert data_sdk["name"] == "research-subagent-executor"
    assert data_sdk["capabilities"]["enable_mcp_tools"] is True
