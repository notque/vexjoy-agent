"""Tests for hooks/pipeline-phase-gate.py — do-perspectives adr/ exclusion."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "pipeline-phase-gate.py"


def _run_hook(file_path: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PIPELINE_PHASE_GATE_BYPASS", None)
    env.pop("PIPELINE_CURRENT_PHASE", None)
    env.pop("PIPELINE_ID", None)
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": str(cwd)}),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )


def test_adr_domain_synthesis_is_not_blocked_by_do_perspectives(tmp_path: Path) -> None:
    """Writing adr/<domain>/synthesis.md must never be falsely blocked by do-perspectives."""
    target = tmp_path / "adr" / "auth-redesign" / "synthesis.md"
    target.parent.mkdir(parents=True)
    res = _run_hook(str(target), tmp_path)
    assert res.returncode == 0, res.stderr


def test_relative_adr_synthesis_is_not_blocked(tmp_path: Path) -> None:
    """Relative adr/<domain>/synthesis.md is also excluded after resolving against cwd."""
    (tmp_path / "adr" / "caching").mkdir(parents=True)
    res = _run_hook("adr/caching/synthesis.md", tmp_path)
    assert res.returncode == 0, res.stderr


def test_non_adr_synthesis_still_requires_perspectives_analysis(tmp_path: Path) -> None:
    """Writing synthesis.md outside adr/ still requires perspectives-analysis.md."""
    target = tmp_path / "work" / "synthesis.md"
    target.parent.mkdir(parents=True)
    res = _run_hook(str(target), tmp_path)
    assert res.returncode == 2
    assert "perspectives-analysis.md" in res.stderr
