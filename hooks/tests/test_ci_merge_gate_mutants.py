"""Mutation-check tests for ci-merge-gate: PR selection around shell syntax, bypass, governance records.

Fake `gh` fails or holds only PR 123; every other PR (including 55, the current-branch PR) passes, so a wrong PR
selection shows up as a missing deny.
"""

import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "ci-merge-gate.py"

_PASS = '[{"name": "ci", "state": "SUCCESS", "bucket": "pass"}]'
_FAIL = '[{"name": "boom", "state": "FAILURE", "bucket": "fail"}]'
_PEND = '[{"name": "slow", "state": "PENDING", "bucket": "pending"}]'


def _gh(tmp_path: Path, target_out: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    gh = bin_dir / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"open({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['pr', 'checks']:\n"
        f"    print({target_out!r} if a[2] == '123' else {_PASS!r})\n"
        "    sys.exit(0)\n"
        "if a[:2] == ['pr', 'view']:\n"
        "    print('55')\n"
        "    sys.exit(0)\n"
        "sys.exit(2)\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run(tmp_path: Path, command: str, target_out: str = _FAIL, env_extra: dict | None = None):
    bin_dir = _gh(tmp_path, target_out)
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_ADMIN_MERGE", "ALLOW_FORCE_MERGE")}
    env.pop("CLAUDE_HOOKS_DEBUG", None)
    env.pop("CI_MERGE_GATE_BYPASS", None)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["CLAUDE_LEARNING_DIR"] = str(tmp_path / "learn")
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    denied = bool(proc.stdout.strip()) and json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    return denied, proc.stderr, tmp_path / "calls.log"


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 123; echo done",
        "gh pr merge 123&&echo done",
        "gh pr merge 123|cat",
        'gh pr merge "123"',
        "gh pr merge '123' --squash",
    ],
)
def test_pr_number_is_found_next_to_shell_syntax_and_quotes(tmp_path, command):
    denied, _, _ = _run(tmp_path, command)
    assert denied is True


def test_bypass_env_lets_a_failing_merge_through_without_checking_ci(tmp_path):
    denied, _, log = _run(tmp_path, "gh pr merge 123", env_extra={"CI_MERGE_GATE_BYPASS": "1"})
    assert denied is False
    assert not log.exists()


def test_bypass_with_debug_says_so_on_stderr(tmp_path):
    _, stderr, _ = _run(tmp_path, "gh pr merge 123", env_extra={"CI_MERGE_GATE_BYPASS": "1", "CLAUDE_HOOKS_DEBUG": "1"})
    assert "Bypassed" in stderr


def test_bypass_without_debug_is_silent(tmp_path):
    _, stderr, _ = _run(tmp_path, "gh pr merge 123", env_extra={"CI_MERGE_GATE_BYPASS": "1"})
    assert stderr == ""


@pytest.mark.parametrize("checks", [_FAIL, _PEND])
def test_blocked_merge_is_recorded_as_blocked_in_governance_log(tmp_path, checks):
    denied, _, _ = _run(tmp_path, "gh pr merge 123", target_out=checks)
    assert denied is True
    conn = sqlite3.connect(tmp_path / "learn" / "learning.db")
    try:
        rows = conn.execute("SELECT blocked FROM governance_events WHERE tool_name='Bash'").fetchall()
    finally:
        conn.close()
    assert rows == [(1,)]
