"""Regression tests for git -C hook parsing, MSYS2 paths, effort caps, SQL concat, and telemetry."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
HOOKS = REPO / "hooks"
SCRIPTS = REPO / "scripts"


def _run_hook(hook: Path, event: dict, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=merged,
        timeout=10,
    )


def _load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_git_repo(path: Path, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-b", branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True)
    (path / "a.txt").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def test_branch_safety_blocks_git_dash_c_commit_and_honors_opt_in(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo, "main")

    # git -C <repo> commit must be blocked on main (was previously bypassed)
    res = _run_hook(
        HOOKS / "pretool-branch-safety.py",
        {"tool_name": "Bash", "tool_input": {"command": f'git -C "{repo}" commit -m "x"'}, "cwd": str(tmp_path)},
    )
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    # Marker file explicitly enables direct main commits for single-owner repos
    (repo / ".vexjoy-allow-main-commits").write_text("", encoding="utf-8")
    res2 = _run_hook(
        HOOKS / "pretool-branch-safety.py",
        {"tool_name": "Bash", "tool_input": {"command": f'git -C "{repo}" commit -m "x"'}, "cwd": str(tmp_path)},
    )
    assert res2.returncode == 0
    assert res2.stdout.strip() == ""


def test_dispatch_spec_gate_caps_xhigh_effort(tmp_path: Path) -> None:
    res = _run_hook(
        HOOKS / "pretool-dispatch-spec-gate.py",
        {
            "tool_name": "Agent",
            "tool_input": {"prompt": "do work", "effort": "xhigh"},
        },
        env={"CLAUDE_LEARNING_DIR": str(tmp_path)},
    )
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "medium" in out["hookSpecificOutput"]["permissionDecisionReason"]

    # Explicit override marker passes
    res2 = _run_hook(
        HOOKS / "pretool-dispatch-spec-gate.py",
        {
            "tool_name": "Agent",
            "tool_input": {"prompt": "[effort-override: approved] do work", "effort": "xhigh"},
        },
        env={"CLAUDE_LEARNING_DIR": str(tmp_path)},
    )
    assert res2.returncode == 0
    assert res2.stdout.strip() == ""


def test_config_protection_blocks_unsolicited_memory_write(tmp_path: Path) -> None:
    mem_path = str(tmp_path / ".claude" / "projects" / "proj-a" / "memory" / "rule.md")
    res = _run_hook(
        HOOKS / "pretool-config-protection.py",
        {"tool_name": "Write", "tool_input": {"file_path": mem_path}},
        env={"CLAUDE_LEARNING_DIR": str(tmp_path)},
    )
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    res_allow = _run_hook(
        HOOKS / "pretool-config-protection.py",
        {"tool_name": "Write", "tool_input": {"file_path": mem_path}},
        env={"CLAUDE_LEARNING_DIR": str(tmp_path), "VEXJOY_ALLOW_MEMORY_WRITE": "1"},
    )
    assert res_allow.returncode == 0
    assert res_allow.stdout.strip() == ""


def test_gemini_turn_gate_dedups_repeated_prompt_and_honors_direct(tmp_path: Path) -> None:
    env = {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path), "CLAUDECODE": "0", "HARNESS": "agy"}
    ev = {"session_id": "sess-1", "prompt": "refactor the parser module across files"}
    r1 = _run_hook(HOOKS / "gemini-turn-gate-userprompt.py", ev, env=env)
    assert "VEXJOY ROUTING MANDATE" in r1.stdout
    # Second invocation with identical prompt must not re-inject
    r2 = _run_hook(HOOKS / "gemini-turn-gate-userprompt.py", ev, env=env)
    assert "VEXJOY ROUTING MANDATE" not in r2.stdout

    # Explicit direct-answer prompt is treated as trivial
    r3 = _run_hook(
        HOOKS / "gemini-turn-gate-userprompt.py",
        {"session_id": "sess-2", "prompt": "check the status of foo, only answer directly"},
        env=env,
    )
    assert "VEXJOY ROUTING MANDATE" not in r3.stdout


def test_sql_scanner_ignores_static_literal_concat_but_catches_variable_concat(tmp_path: Path) -> None:
    mod = _load_mod(SCRIPTS / "security-review-scan.py", "sec_scan_test")
    static_js = tmp_path / "static.js"
    static_js.write_text('const q = "SELECT a, b " + "FROM tbl " + "WHERE active = 1";\n', encoding="utf-8")
    vuln_js = tmp_path / "vuln.js"
    vuln_js.write_text('const q = "SELECT a FROM tbl WHERE id = " + userId;\n', encoding="utf-8")

    rules = mod._build_rules()
    f_static = [f for f in mod._scan_file(str(static_js), rules) if f.get("category") == "sql-injection" or f.get("rule") == "sql-injection"]
    f_vuln = [f for f in mod._scan_file(str(vuln_js), rules) if f.get("category") == "sql-injection" or f.get("rule") == "sql-injection"]
    assert f_static == []
    assert len(f_vuln) >= 1


def test_usage_meter_dedups_message_id_and_tracks_effort() -> None:
    mod = _load_mod(SCRIPTS / "usage-meter.py", "usage_meter_test")
    rows = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "effort": "medium",
            "message": {"id": "msg_1", "model": "claude-opus", "usage": {"input_tokens": 100, "output_tokens": 10}},
        },
        {
            "type": "assistant",
            "effort": "medium",
            "message": {"id": "msg_1", "model": "claude-opus", "usage": {"input_tokens": 100, "output_tokens": 50}},
        },
    ]
    res = mod.analyze(rows)
    assert res["per_model"]["claude-opus"]["generations"] == 1
    assert res["per_model"]["claude-opus"]["output_tokens"] == 50
    assert res["per_effort"]["claude-opus"]["medium"] == 1


def test_agent_telemetry_report_multi_provider(tmp_path: Path) -> None:
    mod = _load_mod(SCRIPTS / "agent-telemetry-report.py", "agent_tel_test")
    claude_dir = tmp_path / "claude" / "proj" / "sess1" / "subagents"
    claude_dir.mkdir(parents=True)
    (claude_dir / "agent-a.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-11-26T12:00:00Z",
                "effort": "xhigh",
                "message": {
                    "id": "m1",
                    "role": "assistant",
                    "model": "claude-opus-4",
                    "usage": {"input_tokens": 1000, "output_tokens": 500, "cache_read_input_tokens": 2000},
                    "content": [{"type": "text", "text": "I've saved this as a standing rule."}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ag_dir = tmp_path / "ag" / "conv1" / ".system_generated" / "logs"
    ag_dir.mkdir(parents=True)
    (ag_dir / "transcript.jsonl").write_text(
        json.dumps(
            {
                "step_index": 1,
                "created_at": "2026-11-26T12:05:00Z",
                "model": "gemini-4-argon",
                "input_tokens": 500,
                "output_tokens": 200,
                "cache_read_tokens": 100,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = mod.build_report(
        tmp_path / "tel.db",
        days=7,
        providers=("claude", "antigravity"),
        claude_projects=tmp_path / "claude",
        ag_brain=tmp_path / "ag",
        learning_dir=tmp_path / "learn",
    )
    models = {r["model"] for r in report["scorecard"]}
    assert "claude-opus-4" in models
    assert "gemini-4-argon" in models
    assert report["structural_signals"].get("standing_rule_claim") == 1
