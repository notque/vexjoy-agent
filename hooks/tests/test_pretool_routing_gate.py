"""Behavior and protocol tests for Gemini Turn-1 routing enforcement hooks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROUTING_GATE = ROOT / "hooks" / "pretool-routing-gate.py"
TURN_GATE = ROOT / "hooks" / "gemini-turn-gate-userprompt.py"


def run_hook(
    hook_path: Path, payload: dict, env_override: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_turn_gate_non_trivial_injects_mandate(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-1"
    payload = {
        "session_id": session_id,
        "prompt": "Refactor the authentication module and add unit tests for OAuth",
    }
    res = run_hook(TURN_GATE, payload, {"VEXJOY_ROUTING_STATE_DIR": str(state_dir)})
    assert res.returncode == 0
    assert "[VEXJOY ROUTING MANDATE]" in res.stdout

    # Verify state file was created and marked not routed
    state_file = state_dir / f"routing-state-{session_id}.json"
    assert state_file.is_file()
    state = json.loads(state_file.read_text())
    assert state["routed"] is False
    assert state["non_trivial"] is True


def test_turn_gate_trivial_continuation_does_not_inject(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-2"
    payload = {
        "session_id": session_id,
        "prompt": "proceed",
    }
    res = run_hook(TURN_GATE, payload, {"VEXJOY_ROUTING_STATE_DIR": str(state_dir)})
    assert res.returncode == 0
    assert "[VEXJOY ROUTING MANDATE]" not in res.stdout

    state_file = state_dir / f"routing-state-{session_id}.json"
    assert state_file.is_file()
    state = json.loads(state_file.read_text())
    assert state["routed"] is True
    assert state["non_trivial"] is False


def test_routing_gate_allows_read_only_tools(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-3"

    # Read tool
    res = run_hook(
        ROUTING_GATE,
        {"session_id": session_id, "tool_name": "Read", "tool_input": {"file_path": "foo.txt"}},
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir)},
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout

    # Read-only git status command
    res = run_hook(
        ROUTING_GATE,
        {"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git status"}},
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir)},
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout


def test_routing_gate_allows_subagent_dispatch(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-4"

    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "python-general-engineer", "prompt": "fix bug"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "HARNESS": "agy"},
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout

    # Subagent dispatch should mark session as routed in state
    state_file = state_dir / f"routing-state-{session_id}.json"
    assert state_file.is_file()
    state = json.loads(state_file.read_text())
    assert state["routed"] is True


def test_routing_gate_denies_mutating_tool_when_unrouted(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-5"

    # Initialize unrouted state
    state_file = state_dir / f"routing-state-{session_id}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"session_id": session_id, "routed": False, "non_trivial": True}))

    # Attempt edit_file — must use HARNESS=agy so provider guard does not short-circuit
    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.rs", "old_string": "a", "new_string": "b"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "HARNESS": "agy"},
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "VexJoy Routing Gate" in data["hookSpecificOutput"]["permissionDecisionReason"]

    # Attempt mutating bash command
    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "cargo test"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "HARNESS": "agy"},
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_routing_gate_allows_when_bypass_or_routed(tmp_path: Path):
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-6"

    # Bypass env
    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.rs"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "ROUTING_GATE_BYPASS": "1"},
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout

    # State already routed
    state_file = state_dir / f"routing-state-{session_id}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"session_id": session_id, "routed": True, "non_trivial": True}))

    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "cargo test"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "HARNESS": "agy"},
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout


def test_routing_gate_allows_claude_session_no_agy_env(tmp_path: Path):
    """Claude/Anthropic sessions (no AGY env vars) must never be blocked."""
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-claude-1"

    # Initialize unrouted state — same setup that would block AGY sessions
    state_file = state_dir / f"routing-state-{session_id}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"session_id": session_id, "routed": False, "non_trivial": True}))

    # No AGY env vars present (standard Claude/Anthropic session)
    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.rs", "old_string": "a", "new_string": "b"},
        },
        {
            "VEXJOY_ROUTING_STATE_DIR": str(state_dir),
            "HARNESS": "",
            "AGY_SESSION": "",
            "ANTIGRAVITY_BRAIN_DIR": "",
        },
    )
    assert res.returncode == 0
    assert "deny" not in res.stdout, "Routing gate must not block Claude/Anthropic sessions (no AGY env)"


def test_routing_gate_enforces_for_agy_session(tmp_path: Path):
    """AGY/Gemini sessions must still be blocked when unrouted."""
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-agy-1"

    state_file = state_dir / f"routing-state-{session_id}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"session_id": session_id, "routed": False, "non_trivial": True}))

    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/main.rs", "old_string": "a", "new_string": "b"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "HARNESS": "agy"},
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny", (
        "Routing gate must still block AGY sessions when unrouted"
    )


def test_routing_gate_enforces_for_agy_session_env2(tmp_path: Path):
    """AGY_SESSION=1 env var also triggers enforcement."""
    state_dir = tmp_path / "routing_state"
    session_id = "test-session-agy-2"

    state_file = state_dir / f"routing-state-{session_id}.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"session_id": session_id, "routed": False, "non_trivial": True}))

    res = run_hook(
        ROUTING_GATE,
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "cargo test"},
        },
        {"VEXJOY_ROUTING_STATE_DIR": str(state_dir), "AGY_SESSION": "1"},
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny", "AGY_SESSION=1 must trigger enforcement"
