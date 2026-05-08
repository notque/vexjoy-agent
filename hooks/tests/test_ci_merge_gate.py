"""Tests for ci-merge-gate.py --admin and --force blocking."""

import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(__file__), "..", "ci-merge-gate.py")


def run_hook(command: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook with a synthetic PreToolUse event."""
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = os.environ.copy()
    # Clear escape hatches by default
    env.pop("ALLOW_ADMIN_MERGE", None)
    env.pop("ALLOW_FORCE_MERGE", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, HOOK],
        input=event,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


class TestAdminBlock:
    def test_admin_flag_denied(self):
        r = run_hook("gh pr merge 55 --admin")
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--admin" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_admin_allowed_with_env(self):
        r = run_hook("gh pr merge 55 --admin", env_overrides={"ALLOW_ADMIN_MERGE": "1"})
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
    def test_force_flag_denied(self):
        r = run_hook("gh pr merge 55 --force")
        assert r.returncode == 0
        out = json.loads(r.stdout.strip().split("\n")[-1])
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "--force" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_force_allowed_with_env(self):
        r = run_hook("gh pr merge 55 --force", env_overrides={"ALLOW_FORCE_MERGE": "1"})
        assert r.returncode == 0
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                decision = data.get("hookSpecificOutput", {}).get("permissionDecision")
                assert decision != "deny", "Should not deny when ALLOW_FORCE_MERGE=1"
        assert "ALLOW_FORCE_MERGE" in r.stderr


class TestPassthrough:
    def test_normal_merge_passes(self):
        """Normal merge should not be blocked by admin/force checks."""
        r = run_hook("gh pr merge 55 --squash")
        assert r.returncode == 0
        # Should not have a deny from admin/force (CI check may still fire but that's separate)
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                assert "--admin" not in reason
                assert "--force" not in reason

    def test_non_merge_command_passes(self):
        """Non-merge commands should pass through completely."""
        r = run_hook("gh pr view 55")
        assert r.returncode == 0
        assert r.stdout.strip() == "" or "deny" not in r.stdout

    def test_merge_with_delete_branch_passes(self):
        """Normal merge flags should not trigger admin/force block."""
        r = run_hook("gh pr merge 55 --squash --delete-branch")
        assert r.returncode == 0
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                reason = data.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
                assert "--admin" not in reason
                assert "--force" not in reason
