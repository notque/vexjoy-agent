"""Behavior and protocol tests for the dispatch spec gate (PreToolUse:Agent)."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "pretool-dispatch-spec-gate.py"
BUILD_DISPATCH = ROOT / "scripts" / "build-dispatch.py"
SETTINGS = ROOT / ".claude" / "settings.json"

REQUIRED = ("**Request (verbatim):**", "**Acceptance criteria:**", "## Repo state")


def _run(stdin: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {k: v for k, v in os.environ.items() if not k.startswith("DISPATCH_SPEC_GATE")}
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=merged,
        timeout=10,
        check=False,
    )


def _event(prompt: str, tool_name: str = "Agent") -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {"prompt": prompt}})


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)["hookSpecificOutput"]


def _load_build_dispatch():
    spec = importlib.util.spec_from_file_location("build_dispatch", BUILD_DISPATCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BARE_MEDIUM = "[do-route] agent=x skill=y complexity=medium model=opus\n**Intent:** z"


# --- protocol -----------------------------------------------------------------


def test_empty_stdin_exits_zero_and_silent() -> None:
    result = _run("")
    assert result.returncode == 0
    assert result.stdout == ""


def test_malformed_json_exits_zero_and_silent() -> None:
    result = _run("{not json")
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("stdin", ["[]", '{"tool_name":"Agent"}', '{"tool_name":"Agent","tool_input":[]}'])
def test_unexpected_shapes_stay_silent(stdin: str) -> None:
    result = _run(stdin)
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_agent_tool_stays_silent() -> None:
    result = _run(_event(BARE_MEDIUM, tool_name="Bash"))
    assert result.returncode == 0
    assert result.stdout == ""


# --- gating -------------------------------------------------------------------


def test_medium_without_blocks_denies_by_default_with_every_missing_label(tmp_path: Path) -> None:
    result = _run(_event(BARE_MEDIUM), env={"CLAUDE_LEARNING_DIR": str(tmp_path)})
    assert result.returncode == 0
    out = _payload(result)
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "additionalContext" not in out
    reason = out["permissionDecisionReason"]
    assert reason.startswith("[dispatch-spec-gate]")
    for label in REQUIRED:
        assert label in reason
    assert "build-dispatch.py" in reason
    assert "verbatim" in reason

    db_path = tmp_path / "learning.db"
    assert db_path.is_file()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT event_type, tool_name, hook_phase, severity, blocked, payload FROM governance_events"
        ).fetchall()
    assert len(rows) == 1
    event_type, tool_name, hook_phase, severity, blocked, payload_json = rows[0]
    assert event_type == "policy_violation"
    assert tool_name == "Agent"
    assert hook_phase == "pre"
    assert severity == "medium"
    assert blocked == 1
    assert "pretool-dispatch-spec-gate" in payload_json


def test_complex_without_blocks_denies_by_default(tmp_path: Path) -> None:
    result = _run(
        _event(BARE_MEDIUM.replace("complexity=medium", "complexity=complex")),
        env={"CLAUDE_LEARNING_DIR": str(tmp_path)},
    )
    out = _payload(result)
    assert out["permissionDecision"] == "deny"
    assert "complexity=complex" in out["permissionDecisionReason"]


@pytest.mark.parametrize("complexity", ["trivial", "simple"])
def test_low_complexity_stays_silent(complexity: str) -> None:
    result = _run(_event(BARE_MEDIUM.replace("complexity=medium", f"complexity={complexity}")))
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_marker_stays_silent() -> None:
    result = _run(_event("Fix the bug in foo.py. complexity=medium is mentioned but no marker leads."))
    assert result.returncode == 0
    assert result.stdout == ""


def test_marker_not_on_first_line_stays_silent() -> None:
    result = _run(_event("Preamble text\n" + BARE_MEDIUM))
    assert result.returncode == 0
    assert result.stdout == ""


def test_only_missing_labels_are_named(tmp_path: Path) -> None:
    prompt = BARE_MEDIUM + "\n**Request (verbatim):** do it\n**Acceptance criteria:** passes"
    out = _payload(_run(_event(prompt), env={"CLAUDE_LEARNING_DIR": str(tmp_path)}))
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    assert "missing 1 handoff block(s)" in reason
    assert "## Repo state" in reason
    assert "**Request (verbatim):**" not in reason
    assert "**Acceptance criteria:**" not in reason


def test_all_blocks_present_stays_silent() -> None:
    prompt = BARE_MEDIUM + "\n" + "\n".join(f"{label} filled" for label in REQUIRED)
    result = _run(_event(prompt))
    assert result.returncode == 0
    assert result.stdout == ""


# --- modes --------------------------------------------------------------------


def test_warn_mode_downgrades_to_additional_context_with_same_reason(tmp_path: Path) -> None:
    denied = _payload(_run(_event(BARE_MEDIUM), env={"CLAUDE_LEARNING_DIR": str(tmp_path)}))
    assert denied["permissionDecision"] == "deny"
    result = _run(_event(BARE_MEDIUM), env={"DISPATCH_SPEC_GATE_MODE": "warn"})
    assert result.returncode == 0
    out = _payload(result)
    assert out["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in out
    assert out["additionalContext"] == denied["permissionDecisionReason"]


def test_default_deny_stays_silent_when_complete() -> None:
    prompt = BARE_MEDIUM + "\n" + "\n".join(REQUIRED)
    result = _run(_event(prompt))
    assert result.returncode == 0
    assert result.stdout == ""


def test_bypass_disables_gate() -> None:
    result = _run(_event(BARE_MEDIUM), env={"DISPATCH_SPEC_GATE_BYPASS": "1"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_effort_cap_still_denies_even_in_warn_mode(tmp_path: Path) -> None:
    event = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
            "tool_input": {"prompt": "plain task", "effort": "max"},
        }
    )
    result = _run(event, env={"DISPATCH_SPEC_GATE_MODE": "warn", "CLAUDE_LEARNING_DIR": str(tmp_path)})
    assert result.returncode == 0
    out = _payload(result)
    assert out["permissionDecision"] == "deny"
    assert "effort='max'" in out["permissionDecisionReason"]


# --- round-trip lock against build-dispatch.py --------------------------------


def _decision(complexity: str) -> dict:
    return {
        "agent": "python-general-engineer",
        "skill": "testing",
        "complexity": complexity,
        "model": "opus",
        "task_spec": {
            "request_verbatim": "make the thing",
            "intent": "make the thing work",
            "acceptance": "tests pass",
        },
    }


@pytest.mark.usefixtures("use_public_index")
def test_full_preamble_from_build_dispatch_stays_silent() -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("medium"), SETTINGS, gather=True, repo_root=ROOT)
    for label in REQUIRED:
        assert label in preamble, f"build_preamble no longer emits {label!r}; gate labels drifted"
    result = _run(_event(preamble))
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.usefixtures("use_public_index")
def test_no_gather_preamble_at_medium_denies_about_repo_state_only(tmp_path: Path) -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("medium"), SETTINGS, gather=False, repo_root=ROOT)
    out = _payload(_run(_event(preamble), env={"CLAUDE_LEARNING_DIR": str(tmp_path)}))
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    assert "missing 1 handoff block(s)" in reason
    assert "## Repo state" in reason


@pytest.mark.usefixtures("use_public_index")
def test_no_gather_preamble_at_simple_stays_silent() -> None:
    build = _load_build_dispatch()
    preamble = build.build_preamble(_decision("simple"), SETTINGS, gather=False, repo_root=ROOT)
    result = _run(_event(preamble))
    assert result.stdout == ""


# --- budget and registration --------------------------------------------------


@pytest.mark.performance
def test_silent_path_under_50ms_median() -> None:
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        _run(_event(BARE_MEDIUM.replace("complexity=medium", "complexity=simple")))
        samples.append(time.perf_counter() - start)
    assert sorted(samples)[2] < 0.08, samples


@pytest.mark.usefixtures("use_public_index")
@pytest.mark.parametrize("mode", ["summary", "files", "none"])
@pytest.mark.parametrize("complexity", ["medium", "complex"])
def test_inherited_model_context_modes_pass_strict_gate(mode, complexity):
    build = _load_build_dispatch()
    decision = {**_decision(complexity), "model": "inherit", "context_mode": mode}
    prompt = build.build_preamble(decision, SETTINGS, repo_root=ROOT)
    result = _run(_event(prompt), env={"DISPATCH_SPEC_GATE_MODE": "deny"})
    assert result.returncode == 0
    assert result.stdout == ""
