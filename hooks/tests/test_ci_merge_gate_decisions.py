#!/usr/bin/env python3
"""Decision tests for ci-merge-gate, run end to end against a fake `gh`.

Added from the E2 mutation check. The existing suite never proved that:
- a non-merge command carrying a bypass flag is left alone,
- a merge typed with a double space is still gated,
- the PR number in the merge command picks which PR's checks are read,
- each fail-open path says why it let the merge through.

Run with: python3 -m pytest hooks/tests/test_ci_merge_gate_decisions.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "ci-merge-gate.py"

ADMIN = "--" + "admin"
FORCE = "--" + "force"

FAKE_GH = """#!/bin/sh
echo "$@" >> "$FAKE_GH_DIR/calls"
if [ "$1 $2" = "pr view" ]; then
  [ -f "$FAKE_GH_DIR/view_out" ] && cat "$FAKE_GH_DIR/view_out"
  [ -f "$FAKE_GH_DIR/view_rc" ] && exit "$(cat "$FAKE_GH_DIR/view_rc")"
  exit 0
fi
if [ "$1 $2" = "pr checks" ]; then
  [ -f "$FAKE_GH_DIR/checks_out" ] && cat "$FAKE_GH_DIR/checks_out"
  [ -f "$FAKE_GH_DIR/checks_err" ] && cat "$FAKE_GH_DIR/checks_err" >&2
  [ -f "$FAKE_GH_DIR/checks_rc" ] && exit "$(cat "$FAKE_GH_DIR/checks_rc")"
  exit 0
fi
exit 0
"""


class Gate:
    """Runs the hook with a fake gh whose answers the test sets."""

    def __init__(self, root: Path):
        self.dir = root / "gh"
        self.dir.mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.root = root
        self.bin = bin_dir

    def set(self, name: str, value: str) -> None:
        (self.dir / name).write_text(value, encoding="utf-8")

    def calls(self) -> list[str]:
        path = self.dir / "calls"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def run(self, command: str) -> tuple[bool, str]:
        env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_ADMIN_MERGE", "ALLOW_FORCE_MERGE")}
        env.update({"HOME": str(self.root), "PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '')}"})
        env["FAKE_GH_DIR"] = str(self.dir)
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        denied = False
        if proc.stdout.strip():
            denied = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
        return denied, proc.stderr


@pytest.fixture
def gate(tmp_path: Path) -> Gate:
    return Gate(tmp_path)


@pytest.mark.parametrize(
    "command",
    [f"git push {FORCE} origin topic", f"echo gh pr view {ADMIN}", f"ls {ADMIN}"],
)
def test_non_merge_command_with_bypass_flag_is_left_alone(gate, command):
    denied, stderr = gate.run(command)
    assert denied is False
    assert "ci-merge-gate" not in stderr
    assert gate.calls() == []


@pytest.mark.parametrize("flag", [ADMIN, FORCE])
def test_double_space_merge_with_bypass_flag_is_denied(gate, flag):
    denied, _ = gate.run(f"gh  pr merge 42 {flag}")
    assert denied is True


def test_merge_number_selects_which_pr_checks_are_read(gate):
    gate.set("checks_out", json.dumps([{"name": "lint", "state": "FAILURE", "bucket": "fail"}]))
    denied, _ = gate.run("gh pr merge 123 --squash --delete-branch")
    assert denied is True
    assert "pr checks 123 --json name,state,bucket" in gate.calls()
    assert not any(call.startswith("pr view") for call in gate.calls())


def test_merge_by_pull_url_reads_that_pr_checks(gate):
    gate.set("checks_out", json.dumps([{"name": "lint", "state": "FAILURE", "bucket": "fail"}]))
    denied, _ = gate.run("gh pr merge https://github.com/acme/widgets/pull/321 --squash")
    assert denied is True
    assert "pr checks 321 --json name,state,bucket" in gate.calls()


def test_pending_checks_deny_and_name_the_check(gate):
    gate.set("checks_out", json.dumps([{"name": "unit", "state": "PENDING", "bucket": "pending"}]))
    denied, stderr = gate.run("gh pr merge 7")
    assert denied is True
    assert "CI checks still running: unit" in stderr


def test_passing_checks_allow_the_merge(gate):
    gate.set("checks_out", json.dumps([{"name": "unit", "state": "SUCCESS", "bucket": "pass"}]))
    denied, stderr = gate.run("gh pr merge 7 --squash")
    assert denied is False
    assert "Merge allowed" in stderr


def test_no_checks_reported_allows_quietly(gate):
    gate.set("checks_rc", "1")
    gate.set("checks_err", "no checks reported on the 'topic' branch")
    denied, stderr = gate.run("gh pr merge 7")
    assert denied is False
    assert "WARNING" not in stderr


def test_other_gh_error_allows_and_reports_the_error(gate):
    gate.set("checks_rc", "1")
    gate.set("checks_err", "HTTP 502 bad gateway")
    denied, stderr = gate.run("gh pr merge 7")
    assert denied is False
    assert "Could not fetch CI checks: HTTP 502 bad gateway" in stderr


def test_unparseable_checks_allow_and_report_it(gate):
    gate.set("checks_out", "<html>not json</html>")
    denied, stderr = gate.run("gh pr merge 7")
    assert denied is False
    assert "Could not parse CI check results" in stderr
    assert "HOOK-CRASH" not in stderr


def test_unknown_pr_number_allows_and_reports_it(gate):
    gate.set("view_rc", "1")
    denied, stderr = gate.run("gh pr merge --squash")
    assert denied is False
    assert "Could not determine PR number" in stderr
    assert "HOOK-CRASH" not in stderr
    assert not any(call.startswith("pr checks") for call in gate.calls())
