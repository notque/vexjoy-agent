"""Tests for ci-merge-gate.py --admin and --force blocking.

Hermetic: the hook shells out to ``gh pr checks`` / ``gh pr view`` to inspect
live CI state. To keep tests deterministic and independent of ambient git/gh
state (issue #722), every ``run_hook`` call installs a fake ``gh`` executable
on ``PATH`` that returns a controlled CI-status result. This exercises the
hook's real subprocess boundary without depending on the surrounding repo.
"""

import ast
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = os.path.join(os.path.dirname(__file__), "..", "ci-merge-gate.py")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Deterministic CI-status payload the fake `gh pr checks` emits by default:
# a single passing check. The hook treats this as "all checks passed", so no
# CI-derived deny can fire and the --admin/--force bypass branches are isolated.
_FAKE_GH_CHECKS_PASS = '[{"name": "ci", "state": "SUCCESS", "bucket": "pass"}]'


def test_registered_timeout_exceeds_worst_subprocess_path():
    """The host timeout must cover every subprocess on the longest hook path."""
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
    registrations = [
        hook
        for group in settings["hooks"]["PreToolUse"]
        for hook in group["hooks"]
        if "ci-merge-gate.py" in hook["command"]
    ]
    assert len(registrations) == 1

    tree = ast.parse(Path(HOOK).read_text())
    subprocess_timeouts = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "run":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
            continue
        timeout = next((kw.value for kw in node.keywords if kw.arg == "timeout"), None)
        assert isinstance(timeout, ast.Constant) and isinstance(timeout.value, int)
        subprocess_timeouts.append(timeout.value)

    # With no PR number, both subprocess calls can run sequentially. Claude Code
    # reads the registered timeout in seconds, the same unit as subprocess.run.
    worst_path_s = sum(subprocess_timeouts)
    assert registrations[0]["timeout"] > worst_path_s


def _install_fake_gh(tmp_dir: str, checks_json: str) -> str:
    """Write a fake `gh` onto a bin dir and return that dir for PATH injection.

    The fake handles the two subcommands the hook invokes:
      * `gh pr checks <n> ...` -> prints ``checks_json`` (deterministic CI state)
      * `gh pr view ...`       -> prints a PR number (current-branch fallback)
    Any other invocation exits non-zero so unexpected calls surface loudly.
    """
    bin_dir = os.path.join(tmp_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    gh_path = os.path.join(bin_dir, "gh")
    # Validate the full argv contract the hook depends on, not just the
    # subcommand, so a regression in the hook's `gh` invocation (dropped
    # --json/--jq, wrong PR number) surfaces as a test failure instead of
    # being silently absorbed by the stub.
    script = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        f"CHECKS = {checks_json!r}\n"
        "if args[:2] == ['pr', 'checks']:\n"
        "    # Contract: gh pr checks <PR> --json name,state,bucket\n"
        "    if len(args) < 3 or not args[2].lstrip('#').isdigit():\n"
        "        sys.stderr.write('fake gh: pr checks missing PR number: %r\\n' % (args,))\n"
        "        sys.exit(2)\n"
        "    if '--json' not in args:\n"
        "        sys.stderr.write('fake gh: pr checks missing --json: %r\\n' % (args,))\n"
        "        sys.exit(2)\n"
        "    print(CHECKS)\n"
        "    sys.exit(0)\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    # Contract: gh pr view --json number --jq .number (no PR number)\n"
        "    if '--json' not in args:\n"
        "        sys.stderr.write('fake gh: pr view missing --json: %r\\n' % (args,))\n"
        "        sys.exit(2)\n"
        "    print('55')\n"
        "    sys.exit(0)\n"
        "sys.stderr.write('fake gh: unexpected args %r\\n' % (args,))\n"
        "sys.exit(2)\n"
    )
    with open(gh_path, "w") as f:
        f.write(script)
    os.chmod(gh_path, os.stat(gh_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def run_hook(
    command: str,
    env_overrides: dict | None = None,
    *,
    gh_checks_json: str = _FAKE_GH_CHECKS_PASS,
    tmp_path=None,
) -> subprocess.CompletedProcess:
    """Run the hook with a synthetic PreToolUse event and a stubbed `gh`.

    A fake `gh` is prepended to PATH so the hook's CI lookups are deterministic
    and never touch the real repo. ``gh_checks_json`` controls what the fake
    `gh pr checks` returns so individual tests can drive specific CI states.
    """
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = os.environ.copy()
    # Clear escape hatches by default
    env.pop("ALLOW_ADMIN_MERGE", None)
    env.pop("ALLOW_FORCE_MERGE", None)
    if env_overrides:
        env.update(env_overrides)
    if tmp_path is not None:
        bin_dir = _install_fake_gh(str(tmp_path), gh_checks_json)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [sys.executable, HOOK],
        input=event,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


class TestAdminBlock:
    def test_admin_flag_denied(self, tmp_path):
        r = run_hook("gh pr merge 55 --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_allowed_with_env(self, tmp_path):
        r = run_hook(
            "gh pr merge 55 --admin",
            env_overrides={"ALLOW_ADMIN_MERGE": "1"},
            tmp_path=tmp_path,
        )
        assert r.returncode == 0
        # Should NOT contain a deny decision
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
                assert decision != "deny", "Should not deny when ALLOW_ADMIN_MERGE=1"
        # Should warn on stderr
        assert "ALLOW_ADMIN_MERGE" in r.stderr


class TestForceBlock:
    def test_force_flag_denied(self, tmp_path):
        r = run_hook("gh pr merge 55 --force", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--force" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_force_allowed_with_env(self, tmp_path):
        r = run_hook(
            "gh pr merge 55 --force",
            env_overrides={"ALLOW_FORCE_MERGE": "1"},
            tmp_path=tmp_path,
        )
        assert r.returncode == 0
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
                assert decision != "deny", "Should not deny when ALLOW_FORCE_MERGE=1"
        assert "ALLOW_FORCE_MERGE" in r.stderr


class TestPassthrough:
    def test_non_merge_command_passes(self, tmp_path):
        """Non-merge commands should pass through completely."""
        r = run_hook("gh pr view 55", tmp_path=tmp_path)
        assert r.returncode == 0
        assert r.stdout.strip() == "" or "deny" not in r.stdout

    def test_merge_with_delete_branch_passes(self, tmp_path):
        """Normal merge flags should not trigger admin/force block."""
        r = run_hook("gh pr merge 55 --squash --delete-branch", tmp_path=tmp_path)
        assert r.returncode == 0
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                assert "--admin" not in reason
                assert "--force" not in reason


def _last_decision(stdout: str) -> str | None:
    """Return the permissionDecision of the last JSON line, or None."""
    for line in reversed(stdout.strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line).get("hookSpecificOutput", {}).get("permissionDecision")
    return None


class TestCIStatusGate:
    """Proves the stubbed `gh` drives the real CI-check path both directions.

    These guard against the stub silently becoming an always-pass no-op: a
    failing CI state MUST still produce a deny, confirming the hook's CI logic
    is exercised hermetically rather than bypassed.
    """

    def test_failing_check_denies(self, tmp_path):
        failing = '[{"name": "build", "state": "FAILURE", "bucket": "fail"}]'
        r = run_hook("gh pr merge 55 --squash", gh_checks_json=failing, tmp_path=tmp_path)
        assert r.returncode == 0
        assert _last_decision(r.stdout) == "deny", "Failing CI must block a normal merge"
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert "build" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_pending_check_denies(self, tmp_path):
        pending = '[{"name": "lint", "state": "PENDING", "bucket": "pending"}]'
        r = run_hook("gh pr merge 55 --squash", gh_checks_json=pending, tmp_path=tmp_path)
        assert r.returncode == 0
        assert _last_decision(r.stdout) == "deny", "Pending CI must block a normal merge"
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert "lint" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_passing_check_allows(self, tmp_path):
        passing = '[{"name": "ci", "state": "SUCCESS", "bucket": "pass"}]'
        r = run_hook("gh pr merge 55 --squash", gh_checks_json=passing, tmp_path=tmp_path)
        assert r.returncode == 0
        assert _last_decision(r.stdout) is None, "Passing CI must not produce a deny"
        assert r.stdout == "", "Allowed hooks must reserve stdout for protocol output"
        assert "Merge allowed" in r.stderr

    def test_pr_number_resolved_via_view_fallback(self, tmp_path):
        """No PR number in command -> hook resolves it via `gh pr view`, then gates CI."""
        failing = '[{"name": "build", "state": "FAILURE", "bucket": "fail"}]'
        r = run_hook("gh pr merge --squash", gh_checks_json=failing, tmp_path=tmp_path)
        assert r.returncode == 0
        # Fake `gh pr view` returns 55; failing CI for #55 must then deny.
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "#55" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_bypass_clears_admin_block_but_not_ci_gate(self, tmp_path):
        """ALLOW_ADMIN_MERGE=1 clears the --admin block only, not the CI gate.

        The bypass env lets execution fall past the --admin deny, but the hook
        then still evaluates CI. With failing CI the merge is denied on the CI
        gate (not the admin flag) -- proving the two gates are independent.
        """
        failing = '[{"name": "build", "state": "FAILURE", "bucket": "fail"}]'
        r = run_hook(
            "gh pr merge 55 --admin",
            env_overrides={"ALLOW_ADMIN_MERGE": "1"},
            gh_checks_json=failing,
            tmp_path=tmp_path,
        )
        assert r.returncode == 0
        assert "ALLOW_ADMIN_MERGE" in r.stderr  # admin block was bypassed
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "CI checks are failing" in reason  # denial is from the CI gate
        assert "--admin" not in reason


class TestFlagInQuotedText:
    """Flags inside quoted text (body, echo, etc.) must not trigger a block."""

    def test_admin_in_echo_not_blocked(self, tmp_path):
        r = run_hook('echo "--admin" && gh pr merge 12 --squash', tmp_path=tmp_path)
        assert r.returncode == 0
        stdout = r.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                if line.strip().startswith("{"):
                    data = json.loads(line)
                    reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                    assert "--admin" not in reason, "echo text must not trigger the --admin block"

    def test_admin_in_body_flag_not_blocked(self, tmp_path):
        r = run_hook('gh pr merge 12 --squash --body "--admin override"', tmp_path=tmp_path)
        assert r.returncode == 0
        stdout = r.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                if line.strip().startswith("{"):
                    data = json.loads(line)
                    reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                    assert "--admin" not in reason, "--body value must not trigger the --admin block"

    def test_real_admin_still_blocked(self, tmp_path):
        r = run_hook("gh pr merge 12 --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_in_chained_merge_blocked(self, tmp_path):
        r = run_hook("gh pr merge 10 --squash && gh pr merge 11 --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_c_admin_still_blocked(self, tmp_path):
        r = run_hook('bash -c "gh pr merge --admin 12"', tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]


class TestRedirectDoesNotEndSegment:
    """Flags after a redirect must still be caught."""

    def test_admin_after_stderr_redirect(self, tmp_path):
        r = run_hook("gh pr merge 12 2>&1 --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_after_stdout_redirect(self, tmp_path):
        r = run_hook("gh pr merge 12 >/dev/null --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_force_after_bare_redirect(self, tmp_path):
        r = run_hook("gh pr merge 12 > out.txt --force", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--force" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_after_stderr_file_redirect(self, tmp_path):
        r = run_hook("gh pr merge 12 --squash 2>/dev/null --admin", tmp_path=tmp_path)
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_variable_expansion_fallback(self, tmp_path):
        """Variable expansion in the merge segment triggers the fallback path."""
        r = run_hook("gh pr merge 12 $EXTRA", tmp_path=tmp_path)
        assert r.returncode == 0
        # Must not crash; stdout is either empty or a CI-gate decision.
        # The fallback path sees no --admin/--force in command.split(), so no flag block.

    def test_echo_admin_still_not_blocked(self, tmp_path):
        """Regression: the original not-blocked case stays not-blocked."""
        r = run_hook('echo "--admin" && gh pr merge 12 --squash', tmp_path=tmp_path)
        assert r.returncode == 0
        stdout = r.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                if line.strip().startswith("{"):
                    data = json.loads(line)
                    reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                    assert "--admin" not in reason


# ---------------------------------------------------------------------------
# Differential: every command the OLD implementation blocked must stay blocked.
# ---------------------------------------------------------------------------

# The old implementation used command.split() and checked `"--admin" in parts`
# or `"--force" in parts`. Build the set of commands it would block and assert
# the new implementation blocks every one of them.

_OLD_BLOCKED_COMMANDS = [
    # Plain flags
    ("gh pr merge 12 --admin", "--admin"),
    ("gh pr merge 12 --force", "--force"),
    ("gh pr merge 55 --admin", "--admin"),
    ("gh pr merge 55 --force", "--force"),
    # Flags before PR number
    ("gh pr merge --admin 12", "--admin"),
    ("gh pr merge --force 12", "--force"),
    # Flags with other options
    ("gh pr merge 12 --squash --admin", "--admin"),
    ("gh pr merge 12 --squash --force", "--force"),
    ("gh pr merge 12 --delete-branch --admin", "--admin"),
    ("gh pr merge 12 --merge --force", "--force"),
    ("gh pr merge 12 --rebase --admin", "--admin"),
    # Flags after redirects (the regression this fixes)
    ("gh pr merge 12 2>&1 --admin", "--admin"),
    ("gh pr merge 12 >/dev/null --admin", "--admin"),
    ("gh pr merge 12 > out.txt --force", "--force"),
    ("gh pr merge 12 2>/dev/null --admin", "--admin"),
    ("gh pr merge 12 --squash 2>/dev/null --admin", "--admin"),
    ("gh pr merge 12 2>/dev/null --force", "--force"),
    ("gh pr merge 12 >> log.txt --admin", "--admin"),
    ("gh pr merge 12 &> combined.log --admin", "--admin"),
    # Chained commands
    ("gh pr merge 10 --squash && gh pr merge 11 --admin", "--admin"),
    ("sleep 1 && gh pr merge 12 --admin", "--admin"),
    ("echo ok; gh pr merge 12 --force", "--force"),
    ("true || gh pr merge 12 --admin", "--admin"),
    # Tabs and extra whitespace
    ("gh pr merge\t12\t--admin", "--admin"),
    ("gh  pr  merge  12  --admin", "--admin"),
    # Both flags
    ("gh pr merge 12 --admin --force", "--admin"),
    ("gh pr merge 12 --force --admin", "--admin"),
    # Flags with body (body value is clean)
    ("gh pr merge 12 --body 'clean text' --admin", "--admin"),
    ("gh pr merge 12 -b 'clean text' --force", "--force"),
    # Flags with subject
    ("gh pr merge 12 --subject 'title' --admin", "--admin"),
    ("gh pr merge 12 -t 'title' --force", "--force"),
    # Flag after repo flag
    ("gh pr merge 12 --repo owner/repo --admin", "--admin"),
    ("gh pr merge 12 -R owner/repo --force", "--force"),
    # Bash -c (fallback path)
    ('bash -c "gh pr merge --admin 12"', "--admin"),
    ('bash -c "gh pr merge --force 12"', "--force"),
    # Eval (fallback path)
    ("eval gh pr merge 12 --admin", "--admin"),
    # Variable expansion (fallback path with actual flags)
    ("gh pr merge 12 $EXTRA --admin", "--admin"),
    # PR URL selector
    ("gh pr merge https://github.com/o/r/pull/12 --admin", "--admin"),
    # Flag at the very end
    ("gh pr merge 12 --squash --delete-branch --admin", "--admin"),
    ("gh pr merge 12 --squash --delete-branch --force", "--force"),
]


@pytest.mark.parametrize(
    ("command", "flag"),
    _OLD_BLOCKED_COMMANDS,
    ids=[f"{i:02d}-{c[:50]}" for i, (c, _) in enumerate(_OLD_BLOCKED_COMMANDS)],
)
def test_old_blocked_still_blocked(command: str, flag: str, tmp_path) -> None:
    """Every command the old split()-based check blocked must stay blocked."""
    r = run_hook(command, tmp_path=tmp_path)
    assert r.returncode == 0
    out = json.loads(r.stdout.strip().split("\n")[-1])
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny", f"Expected deny for {flag!r} in: {command}"
    assert flag in out["hookSpecificOutput"]["permissionDecisionReason"]
