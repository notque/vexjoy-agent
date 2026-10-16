"""Mutation-check tests for pretool-synthesis-gate: stale window, checklist path rules, unreadable files, debug trace."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "pretool-synthesis-gate.py"


def _setup(root: Path, *, age_hours: float | None = 1, registered_at: object = "auto", adr_path: str | None = None):
    (root / "skills" / "s").mkdir(parents=True, exist_ok=True)
    session: dict = {"domain": "d"}
    if registered_at == "auto":
        if age_hours is not None:
            session["registered_at"] = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
    else:
        session["registered_at"] = registered_at
    if adr_path is not None:
        session["adr_path"] = adr_path
    (root / ".adr-session.json").write_text(json.dumps(session), encoding="utf-8")


def _run(root: Path, file_path: str | None = None, env_extra: dict | None = None):
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("SYNTHESIS_GATE_BYPASS", "CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG")
    }
    env["HOME"] = str(root)
    env.update(env_extra or {})
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path or str(root / "skills" / "s" / "SKILL.md")},
        "cwd": str(root),
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False, "", proc.stderr
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny", out["permissionDecisionReason"], proc.stderr


def test_session_24_5_hours_old_is_reported_stale(tmp_path):
    _setup(tmp_path, age_hours=24.5)
    denied, reason, _ = _run(tmp_path)
    assert denied is True
    assert "STALE ADR SESSION" in reason


def test_naive_registration_timestamp_is_read_as_utc(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(days=3)).replace(tzinfo=None).isoformat()
    _setup(tmp_path, registered_at=old)
    denied, reason, _ = _run(tmp_path)
    assert denied is True
    assert "STALE ADR SESSION" in reason


@pytest.mark.parametrize("registered_at", ["auto", "not-a-date", 12345])
def test_fresh_or_unreadable_registration_adds_no_note_to_denial(tmp_path, registered_at):
    _setup(tmp_path, age_hours=1, registered_at=registered_at)
    denied, reason, stderr = _run(tmp_path)
    assert denied is True
    assert reason.endswith("synthesis.md.")
    assert "None" not in reason
    assert "None" not in stderr


def test_session_without_registration_date_adds_no_note(tmp_path):
    _setup(tmp_path, age_hours=None)
    denied, reason, _ = _run(tmp_path)
    assert denied is True
    assert "None" not in reason


@pytest.mark.parametrize("adr_path", ["adr/notes.txt", "docs/plan.md"])
def test_checklist_is_only_read_from_adr_markdown_files(tmp_path, adr_path):
    _setup(tmp_path, age_hours=48, adr_path=adr_path)
    target = tmp_path / adr_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("- [x] one\n- [x] two\n", encoding="utf-8")
    denied, reason, _ = _run(tmp_path)
    assert denied is True
    assert "not a repo-relative adr/*.md file" in reason
    assert "COMPLETE" not in reason


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs permission checks")
def test_unreadable_adr_file_is_reported_in_stale_note(tmp_path):
    _setup(tmp_path, age_hours=48, adr_path="adr/d.md")
    adr = tmp_path / "adr" / "d.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("- [ ] a\n", encoding="utf-8")
    adr.chmod(0)
    try:
        denied, reason, _ = _run(tmp_path)
    finally:
        adr.chmod(0o644)
    assert denied is True
    assert "STALE ADR SESSION" in reason
    assert "unreadable" in reason


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs permission checks")
def test_unreadable_synthesis_file_still_blocks(tmp_path):
    _setup(tmp_path)
    syn = tmp_path / "adr" / "d" / "synthesis.md"
    syn.parent.mkdir(parents=True)
    syn.write_text("PROCEED\n", encoding="utf-8")
    syn.chmod(0)
    try:
        denied, reason, _ = _run(tmp_path)
    finally:
        syn.chmod(0o644)
    assert denied is True
    assert "consultation required" in reason


# debug trace: CLAUDE_HOOKS_DEBUG prints a tagged line on stderr for each path, nothing otherwise.


def _allow_cases(tmp_path: Path):
    _setup(tmp_path)
    syn = tmp_path / "adr" / "d" / "synthesis.md"
    syn.parent.mkdir(parents=True)
    syn.write_text("PROCEED\n", encoding="utf-8")
    return {
        "bypass": {"env_extra": {"SYNTHESIS_GATE_BYPASS": "1"}},
        "not_gated": {"file_path": str(tmp_path / "README.md")},
        "proceed": {},
    }


@pytest.mark.parametrize("case", ["bypass", "not_gated", "proceed"])
def test_allow_paths_trace_only_in_debug_mode(tmp_path, case):
    kwargs = _allow_cases(tmp_path)[case]
    denied, _, quiet = _run(tmp_path, **kwargs)
    assert denied is False
    assert quiet == ""
    env_extra = {**kwargs.get("env_extra", {}), "CLAUDE_HOOKS_DEBUG": "1"}
    denied, _, loud = _run(tmp_path, kwargs.get("file_path"), env_extra)
    assert denied is False
    assert "[synthesis-gate]" in loud


def test_no_session_traces_only_in_debug_mode(tmp_path):
    (tmp_path / "skills" / "s").mkdir(parents=True)
    _, _, quiet = _run(tmp_path)
    _, _, loud = _run(tmp_path, env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert quiet == ""
    assert "No .adr-session.json" in loud


def test_active_session_trace_names_the_domain_only_in_debug_mode(tmp_path):
    _setup(tmp_path)
    _, _, quiet = _run(tmp_path)
    _, _, loud = _run(tmp_path, env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert "Active ADR session" not in quiet
    assert "Active ADR session: domain=d" in loud


def test_proceed_verdict_trace_says_so_in_debug_mode(tmp_path):
    _allow_cases(tmp_path)
    _, _, loud = _run(tmp_path, env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert "Verdict=PROCEED" in loud
