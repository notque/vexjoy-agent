#!/usr/bin/env python3
"""Verdict-parsing tests for pretool-synthesis-gate.

Added from the E2 mutation check: the existing BLOCKED test only checked that the
word BLOCKED appears in the denial, and the UNKNOWN-verdict denial also contains
that word. A hook that treated a real BLOCKED verdict as UNKNOWN passed.

Run with: python3 -m pytest hooks/tests/test_pretool_synthesis_gate_verdicts.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-synthesis-gate.py"


def _project(tmp_path: Path, synthesis: str | None) -> Path:
    (tmp_path / "skills" / "s").mkdir(parents=True)
    (tmp_path / ".adr-session.json").write_text(
        json.dumps({"domain": "d", "registered_at": "2999-01-01T00:00:00+00:00", "cwd": str(tmp_path)}),
        encoding="utf-8",
    )
    if synthesis is not None:
        (tmp_path / "adr" / "d").mkdir(parents=True)
        (tmp_path / "adr" / "d" / "synthesis.md").write_text(synthesis, encoding="utf-8")
    return tmp_path


def _decision(root: Path) -> tuple[bool, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("SYNTHESIS_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
    env["HOME"] = str(root)
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(root / "skills" / "s" / "SKILL.md")},
        "cwd": str(root),
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False, ""
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny", out["permissionDecisionReason"]


def test_blocked_verdict_denies_with_the_blocked_message(tmp_path):
    denied, reason = _decision(_project(tmp_path, "Verdict: BLOCKED\n"))
    assert denied is True
    assert "verdict is BLOCKED" in reason
    assert "no clear PROCEED" not in reason


def test_verdict_without_keyword_denies_with_the_unclear_message(tmp_path):
    denied, reason = _decision(_project(tmp_path, "Consultation notes, no decision yet.\n"))
    assert denied is True
    assert "no clear PROCEED or BLOCKED verdict" in reason
    assert "verdict is BLOCKED" not in reason


@pytest.mark.parametrize(
    "text", ["Verdict: PROCEED\n", "verdict: proceed\n", "PROCEED, though one concern was BLOCKED earlier\n"]
)
def test_proceed_verdict_allows(tmp_path, text):
    denied, _ = _decision(_project(tmp_path, text))
    assert denied is False


def test_lowercase_blocked_verdict_still_denies_as_blocked(tmp_path):
    denied, reason = _decision(_project(tmp_path, "verdict: blocked\n"))
    assert denied is True
    assert "verdict is BLOCKED" in reason
