#!/usr/bin/env python3
"""
Tests for the subagent-completion-guard hook.

Run with: python3 -m pytest hooks/tests/test_subagent_completion_guard.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "subagent-completion-guard.py"

spec = importlib.util.spec_from_file_location("subagent_completion_guard", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

capture_worktree_metadata = mod.capture_worktree_metadata
format_worktree_output = mod.format_worktree_output
check_branch_safety = mod.check_branch_safety
find_write_tool_in_transcript = mod.find_write_tool_in_transcript
check_readonly_violation = mod.check_readonly_violation
is_reviewer_agent = mod.is_reviewer_agent
is_protected_org_repo = mod.is_protected_org_repo
find_gated_command_in_transcript = mod.find_gated_command_in_transcript
check_protected_org_workflow = mod.check_protected_org_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transcript(lines: list[dict]) -> str:
    """Write NDJSON transcript lines to a temp file, return path string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for entry in lines:
            f.write(json.dumps(entry) + "\n")
        return f.name


def _subprocess_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a mock subprocess.CompletedProcess."""
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# Tier 0: Worktree Metadata Capture
# ---------------------------------------------------------------------------


class TestCaptureWorktreeMetadata:
    """Tier 0 — worktree detection and metadata capture."""

    def _mock_git_responses(self, responses: dict[str, MagicMock]):
        """
        Build a side_effect function that dispatches based on git subcommand.

        responses maps a key string (matched against the args) to a mock result.
        Keys are checked with substring matching against the joined args.
        """

        def _dispatch(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            cmd_str = " ".join(cmd)
            for key, result in responses.items():
                if key in cmd_str:
                    return result
            # Default: command not recognized, return failure
            return _subprocess_result(returncode=1)

        return _dispatch

    def test_not_a_git_repo_returns_empty(self):
        """Non-git directory returns empty dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _subprocess_result(returncode=128)
            result = capture_worktree_metadata("/not-a-repo")
        assert result == {}

    def test_main_repo_not_worktree_returns_empty(self):
        """Main repo (git_dir == common_dir) returns empty dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(stdout="/repo/.git\n"),
                    "--git-dir": _subprocess_result(stdout="/repo/.git\n"),
                }
            )
            result = capture_worktree_metadata("/repo")
        assert result == {}

    def test_worktree_detected_with_commits(self):
        """Worktree with commits and no uncommitted changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(stdout="/repo/.git\n"),
                    "--git-dir": _subprocess_result(stdout="/repo/.git/worktrees/feat-audit\n"),
                    "symbolic-ref": _subprocess_result(stdout="feat/audit-impl\n"),
                    "rev-list": _subprocess_result(stdout="3\n"),
                    "--porcelain": _subprocess_result(stdout=""),
                }
            )
            result = capture_worktree_metadata("/tmp/worktree-feat-audit")

        assert result["is_worktree"] is True
        assert result["worktree_path"] == "/tmp/worktree-feat-audit"
        assert result["branch"] == "feat/audit-impl"
        assert result["commits_ahead"] == 3
        assert result["has_uncommitted"] is False
        assert result["uncommitted_files"] == 0

    def test_worktree_with_uncommitted_files(self):
        """Worktree with uncommitted changes detected."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(stdout="/repo/.git\n"),
                    "--git-dir": _subprocess_result(stdout="/repo/.git/worktrees/wt\n"),
                    "symbolic-ref": _subprocess_result(stdout="feat/metrics\n"),
                    "rev-list": _subprocess_result(stdout="1\n"),
                    "--porcelain": _subprocess_result(stdout=" M file1.go\n M file2.go\n?? new.txt\n"),
                }
            )
            result = capture_worktree_metadata("/tmp/wt")

        assert result["is_worktree"] is True
        assert result["has_uncommitted"] is True
        assert result["uncommitted_files"] == 3

    def test_worktree_zero_commits_no_changes(self):
        """Worktree with no commits and no uncommitted changes (empty worktree)."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(stdout="/repo/.git\n"),
                    "--git-dir": _subprocess_result(stdout="/repo/.git/worktrees/empty\n"),
                    "symbolic-ref": _subprocess_result(stdout="feat/noop\n"),
                    "rev-list": _subprocess_result(stdout="0\n"),
                    "--porcelain": _subprocess_result(stdout=""),
                }
            )
            result = capture_worktree_metadata("/tmp/empty")

        assert result["is_worktree"] is True
        assert result["commits_ahead"] == 0
        assert result["has_uncommitted"] is False

    def test_detached_head_in_worktree(self):
        """Worktree with detached HEAD — branch is empty string."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(stdout="/repo/.git\n"),
                    "--git-dir": _subprocess_result(stdout="/repo/.git/worktrees/detached\n"),
                    "symbolic-ref": _subprocess_result(returncode=128, stdout=""),
                    "rev-list": _subprocess_result(returncode=128),
                    "--porcelain": _subprocess_result(stdout=""),
                }
            )
            result = capture_worktree_metadata("/tmp/detached")

        assert result["is_worktree"] is True
        assert result["branch"] == ""
        assert result["commits_ahead"] == 0

    def test_master_rev_list_fails_falls_back_to_main(self):
        """When master..HEAD fails, fall back to main..HEAD."""
        call_count = {"rev_list": 0}

        def _dispatch(*args, **kwargs):
            cmd_str = " ".join(args[0])
            if "--is-inside-work-tree" in cmd_str:
                return _subprocess_result(stdout="true\n")
            if "--git-common-dir" in cmd_str:
                return _subprocess_result(stdout="/repo/.git\n")
            if "--git-dir" in cmd_str:
                return _subprocess_result(stdout="/repo/.git/worktrees/wt\n")
            if "symbolic-ref" in cmd_str:
                return _subprocess_result(stdout="feat/test\n")
            if "rev-list" in cmd_str:
                call_count["rev_list"] += 1
                if "master..HEAD" in cmd_str:
                    return _subprocess_result(returncode=128)  # no master
                if "main..HEAD" in cmd_str:
                    return _subprocess_result(stdout="5\n")
            if "--porcelain" in cmd_str:
                return _subprocess_result(stdout="")
            return _subprocess_result(returncode=1)

        with patch("subprocess.run", side_effect=_dispatch):
            result = capture_worktree_metadata("/tmp/wt")

        assert result["commits_ahead"] == 5
        assert call_count["rev_list"] == 2

    def test_git_timeout_returns_empty(self):
        """subprocess.TimeoutExpired returns empty dict gracefully."""
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="git", timeout=2)):
            result = capture_worktree_metadata("/tmp/slow")
        assert result == {}

    def test_common_dir_failure_returns_empty(self):
        """If --git-common-dir fails, return empty."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_git_responses(
                {
                    "--is-inside-work-tree": _subprocess_result(stdout="true\n"),
                    "--git-common-dir": _subprocess_result(returncode=1),
                    "--git-dir": _subprocess_result(stdout="/repo/.git\n"),
                }
            )
            result = capture_worktree_metadata("/repo")
        assert result == {}


class TestFormatWorktreeOutput:
    """Test output formatting for worktree metadata."""

    def test_empty_meta_returns_empty(self):
        assert format_worktree_output({}) == []

    def test_non_worktree_meta_returns_empty(self):
        assert format_worktree_output({"is_worktree": False}) == []

    def test_worktree_with_commits_emits_result(self):
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt",
            "branch": "feat/audit",
            "commits_ahead": 3,
            "has_uncommitted": False,
            "uncommitted_files": 0,
        }
        lines = format_worktree_output(meta)
        assert len(lines) == 1
        assert lines[0].startswith("[worktree-result]")
        assert "branch=feat/audit" in lines[0]
        assert "commits=3" in lines[0]
        assert "uncommitted=0" in lines[0]

    def test_worktree_with_uncommitted_emits_warning(self):
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt",
            "branch": "feat/metrics",
            "commits_ahead": 2,
            "has_uncommitted": True,
            "uncommitted_files": 5,
        }
        lines = format_worktree_output(meta)
        assert len(lines) == 2
        assert lines[0].startswith("[worktree-result]")
        assert lines[1].startswith("[worktree-warning]")
        assert "5 uncommitted" in lines[1]
        assert "work may be lost" in lines[1]

    def test_empty_worktree_emits_safe_to_remove(self):
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt",
            "branch": "feat/noop",
            "commits_ahead": 0,
            "has_uncommitted": False,
            "uncommitted_files": 0,
        }
        lines = format_worktree_output(meta)
        assert len(lines) == 2
        assert lines[0].startswith("[worktree-result]")
        assert lines[1].startswith("[worktree-empty]")
        assert "safe to remove" in lines[1]

    def test_commits_but_no_uncommitted_no_warning_no_empty(self):
        """Has commits but no uncommitted files: result line only."""
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt",
            "branch": "feat/work",
            "commits_ahead": 7,
            "has_uncommitted": False,
            "uncommitted_files": 0,
        }
        lines = format_worktree_output(meta)
        assert len(lines) == 1
        assert "[worktree-result]" in lines[0]


# ---------------------------------------------------------------------------
# Tier 1: Branch Safety
# ---------------------------------------------------------------------------


class TestCheckBranchSafety:
    """Tier 1 — branch safety guard."""

    def test_feature_branch_returns_none(self):
        """On a feature branch, the check should pass (return None)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _subprocess_result(stdout="fix/my-feature\n")
            result = check_branch_safety("/repo")

        assert result is None
        # Should have stopped after the symbolic-ref call — no log call
        assert mock_run.call_count == 1

    def test_master_with_no_unpushed_commits_returns_none(self):
        """master branch with no commits ahead of origin/master — pass."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),  # symbolic-ref
                _subprocess_result(stdout=""),  # git log (empty)
            ]
            result = check_branch_safety("/repo")

        assert result is None

    def test_master_with_unapproved_commits_blocks(self):
        """master with new commits that lack [APPROVED-DIRECT] → block."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),
                _subprocess_result(stdout="abc1234 my bad commit\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is not None
        assert "BLOCKED" in result
        assert "master" in result
        assert "abc1234 my bad commit" in result

    def test_main_branch_with_unapproved_commits_blocks(self):
        """Same for 'main' branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="main\n"),
                _subprocess_result(stdout="def5678 oops\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is not None
        assert "BLOCKED" in result
        assert "main" in result

    def test_master_with_approved_direct_marker_returns_none(self, capsys):
        """All commits carry [APPROVED-DIRECT] — escape hatch, no block."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),
                _subprocess_result(stdout="abc1234 hotfix [APPROVED-DIRECT]\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is None
        captured = capsys.readouterr()
        assert "escape hatch used" in captured.err

    def test_master_with_mixed_commits_blocks_unapproved_only(self):
        """Some approved, some not — still blocks, only unapproved listed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),
                _subprocess_result(stdout="aaa hotfix [APPROVED-DIRECT]\nbbb bad commit\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is not None
        assert "bbb bad commit" in result
        assert "aaa hotfix" not in result

    def test_mixed_commits_recovery_targets_upstream_not_filtered_count(self):
        """Issue #1021: approved commit newer than unapproved one.

        git log is newest-first. A HEAD~N count built from the filtered list
        would drop the approved commit and leave the unapproved one on main.
        Recovery must name the upstream ref and the full range.
        """
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="main\n"),
                _subprocess_result(stdout="aaa hotfix [APPROVED-DIRECT]\nbbb bad commit\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is not None
        assert "HEAD~" not in result
        assert "git branch <feature-branch> HEAD" in result
        assert "git reset --keep origin/main" in result
        assert "all 2 commit(s)" in result

    def test_recovery_uses_current_branch_upstream(self):
        """master repos get origin/master as the reset target."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),
                _subprocess_result(stdout="ccc one\nddd two\n"),
            ]
            result = check_branch_safety("/repo")

        assert result is not None
        assert "git reset --keep origin/master" in result
        assert "HEAD~" not in result

    def test_detached_head_returns_none(self):
        """Detached HEAD (symbolic-ref fails) — skip silently."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _subprocess_result(returncode=128, stdout="")
            result = check_branch_safety("/repo")

        assert result is None

    def test_git_log_failure_returns_none(self):
        """git log returns non-zero (no remote) — skip silently."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _subprocess_result(stdout="master\n"),
                _subprocess_result(returncode=128, stdout=""),
            ]
            result = check_branch_safety("/repo")

        assert result is None

    def test_timeout_returns_none(self):
        """subprocess.TimeoutExpired — skip silently."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=2)):
            result = check_branch_safety("/repo")

        assert result is None


# ---------------------------------------------------------------------------
# Tier 2: READ-ONLY Violation Guard
# ---------------------------------------------------------------------------


class TestFindWriteToolInTranscript:
    """Unit tests for the transcript scanner (find_write_tool_in_transcript)."""

    def test_empty_transcript_returns_none(self):
        path = _make_transcript([])
        assert find_write_tool_in_transcript(path) is None

    def test_no_write_tool_returns_none(self):
        path = _make_transcript([{"tool_name": "Read", "tool_input": {"file_path": "/foo"}}])
        assert find_write_tool_in_transcript(path) is None

    def test_write_tool_via_tool_name_field_detected(self):
        path = _make_transcript([{"tool_name": "Write", "tool_input": {"file_path": "/out.txt"}}])
        result = find_write_tool_in_transcript(path)
        assert result == "Write(/out.txt)"

    def test_edit_tool_detected(self):
        path = _make_transcript([{"tool_name": "Edit", "tool_input": {"file_path": "/src.py"}}])
        result = find_write_tool_in_transcript(path)
        assert result == "Edit(/src.py)"

    def test_notebookedit_detected(self):
        path = _make_transcript([{"tool_name": "NotebookEdit", "tool_input": {}}])
        result = find_write_tool_in_transcript(path)
        assert result == "NotebookEdit"

    def test_write_tool_at_content_block_index_0(self):
        """Write tool embedded in content[0] block."""
        path = _make_transcript(
            [
                {
                    "content": [
                        {"type": "tool_use", "name": "Write", "input": {"file_path": "/a.txt"}},
                    ]
                }
            ]
        )
        result = find_write_tool_in_transcript(path)
        assert result == "Write(/a.txt)"

    def test_write_tool_at_content_block_index_1_detected(self):
        """Write tool at content[1] — the original bug would miss this."""
        path = _make_transcript(
            [
                {
                    "content": [
                        {"type": "text", "text": "Some reasoning here"},
                        {"type": "tool_use", "name": "Write", "input": {"file_path": "/b.txt"}},
                    ]
                }
            ]
        )
        result = find_write_tool_in_transcript(path)
        assert result == "Write(/b.txt)"

    def test_empty_content_list_no_crash(self):
        """content=[] must not raise IndexError."""
        path = _make_transcript([{"content": []}])
        result = find_write_tool_in_transcript(path)
        assert result is None

    def test_non_write_tool_in_content_blocks_ignored(self):
        path = _make_transcript(
            [
                {
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {}},
                        {"type": "tool_use", "name": "Read", "input": {}},
                    ]
                }
            ]
        )
        assert find_write_tool_in_transcript(path) is None

    def test_missing_transcript_path_returns_none(self):
        assert find_write_tool_in_transcript("") is None

    def test_nonexistent_file_returns_none(self):
        assert find_write_tool_in_transcript("/tmp/does_not_exist_xyz.jsonl") is None

    def test_malformed_json_lines_skipped(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not json\n")
            f.write(json.dumps({"tool_name": "Read"}) + "\n")
            path = f.name
        assert find_write_tool_in_transcript(path) is None


class TestCheckReadonlyViolation:
    """Integration of is_reviewer_agent + find_write_tool_in_transcript."""

    def test_reviewer_agent_with_write_tool_blocks(self):
        path = _make_transcript([{"tool_name": "Write", "tool_input": {"file_path": "/x"}}])
        result = check_readonly_violation("reviewer-code-quality", path)
        assert result is not None
        assert "BLOCKED" in result
        assert "reviewer-code-quality" in result

    def test_reviewer_agent_without_write_tool_passes(self):
        path = _make_transcript([{"tool_name": "Read", "tool_input": {}}])
        result = check_readonly_violation("reviewer-code-quality", path)
        assert result is None

    def test_non_reviewer_agent_with_write_tool_passes(self):
        """Non-reviewer agents are allowed to write — no block."""
        path = _make_transcript([{"tool_name": "Write", "tool_input": {"file_path": "/x"}}])
        result = check_readonly_violation("python-general-engineer", path)
        assert result is None

    def test_empty_agent_type_passes(self):
        path = _make_transcript([{"tool_name": "Write", "tool_input": {}}])
        result = check_readonly_violation("", path)
        assert result is None


# ---------------------------------------------------------------------------
# Tier 3: Protected-Org Workflow Guard
# ---------------------------------------------------------------------------


class TestIsProtectedOrgRepo:
    """Unit tests for is_protected_org_repo."""

    def test_matching_org_detected(self):
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company,acme-corp"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:my-company/my-repo.git")
            assert is_protected_org_repo("/repo") is True

    def test_case_insensitive_match(self):
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "My-Company"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:my-company/my-repo.git")
            assert is_protected_org_repo("/repo") is True

    def test_non_matching_org_not_detected(self):
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:other-org/my-repo.git")
            assert is_protected_org_repo("/repo") is False

    def test_no_protected_orgs_configured_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_protected_org_repo("/repo") is False

    def test_git_failure_returns_false(self):
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}):
            mock_run.return_value = _subprocess_result(returncode=128)
            assert is_protected_org_repo("/repo") is False

    def test_timeout_returns_false(self):
        import subprocess

        with (
            patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1)),
        ):
            assert is_protected_org_repo("/repo") is False


class TestFindGatedCommandInTranscript:
    """Unit tests for the organization gated-command scanner."""

    def test_git_push_detected(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}])
        result = find_gated_command_in_transcript(path)
        assert result == "git push origin main"

    def test_gh_pr_merge_detected(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "gh pr merge 42 --squash"}}])
        result = find_gated_command_in_transcript(path)
        assert result is not None
        assert "gh pr merge" in result

    def test_gh_pr_create_detected(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "gh pr create --title 'foo'"}}])
        result = find_gated_command_in_transcript(path)
        assert result is not None
        assert "gh pr create" in result

    def test_safe_bash_command_not_detected(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git status"}}])
        assert find_gated_command_in_transcript(path) is None

    def test_tool_name_case_insensitive_bash(self):
        """tool_name='bash' (lowercase) should still be detected."""
        path = _make_transcript([{"tool_name": "bash", "tool_input": {"command": "git push origin main"}}])
        result = find_gated_command_in_transcript(path)
        assert result is not None

    def test_non_bash_tool_not_checked(self):
        path = _make_transcript([{"tool_name": "Read", "tool_input": {"command": "git push"}}])
        assert find_gated_command_in_transcript(path) is None

    def test_empty_transcript_returns_none(self):
        path = _make_transcript([])
        assert find_gated_command_in_transcript(path) is None

    def test_missing_path_returns_none(self):
        assert find_gated_command_in_transcript("") is None


class TestCheckProtectedOrgWorkflow:
    """Integration of is_protected_org_repo + find_gated_command_in_transcript."""

    def test_protected_org_repo_with_git_push_blocks(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}])
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:my-company/repo.git")
            result = check_protected_org_workflow("/repo", path)

        assert result is not None
        assert "BLOCKED" in result
        assert "git push" in result

    def test_non_protected_org_repo_with_git_push_passes(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}])
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:other-org/repo.git")
            result = check_protected_org_workflow("/repo", path)

        assert result is None

    def test_protected_org_repo_without_gated_command_passes(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git status"}}])
        with patch("subprocess.run") as mock_run, patch.dict(os.environ, {"PROTECTED_ORGS": "my-company"}):
            mock_run.return_value = _subprocess_result(stdout="git@github.com:my-company/repo.git")
            result = check_protected_org_workflow("/repo", path)

        assert result is None

    def test_no_protected_orgs_configured_passes(self):
        path = _make_transcript([{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}])
        with patch.dict(os.environ, {}, clear=True):
            result = check_protected_org_workflow("/repo", path)

        assert result is None


# ---------------------------------------------------------------------------
# Real transcript shape (Claude Code nests tool_use under message.content)
# ---------------------------------------------------------------------------
#
# Synthesized fixtures in the line shape Claude Code writes to a subagent
# transcript. No real session data.


def _user_text(text: str) -> dict:
    return {"type": "user", "isSidechain": True, "uuid": "u-1", "message": {"role": "user", "content": text}}


def _assistant_tool_use(name: str, tool_input: dict, tool_use_id: str, text: str = "") -> dict:
    blocks = []
    if text:
        blocks.append({"type": "text", "text": text})
    blocks.append({"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input})
    return {
        "type": "assistant",
        "isSidechain": True,
        "uuid": f"a-{tool_use_id}",
        "message": {
            "id": f"msg_{tool_use_id}",
            "type": "message",
            "role": "assistant",
            "model": "claude-test",
            "content": blocks,
            "stop_reason": "tool_use",
        },
    }


def _user_tool_result(tool_use_id: str, text: str, is_error: bool = False) -> dict:
    return {
        "type": "user",
        "isSidechain": True,
        "uuid": f"r-{tool_use_id}",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": text, "is_error": is_error}],
        },
        "toolUseResult": {"type": "text"},
    }


def _assistant_text(text: str) -> dict:
    return {
        "type": "assistant",
        "isSidechain": True,
        "uuid": "a-final",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}], "stop_reason": "end_turn"},
    }


def _old_find_write_tool_in_transcript(transcript_path: str) -> str | None:
    """The pre-fix scanner (hook-version 1.0.3), kept for the regression test."""
    for line in Path(transcript_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        tool_name = entry.get("tool_name")
        if not tool_name and isinstance(entry.get("content"), list):
            for block in entry["content"]:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") in mod._WRITE_TOOLS
                ):
                    tool_name = block["name"]
                    break
        if tool_name in mod._WRITE_TOOLS:
            return tool_name
    return None


def _reviewer_wrote_transcript() -> list[dict]:
    """A reviewer that reads a file, edits it, then reports."""
    return [
        _user_text("Review /repo/src/app.py for correctness."),
        _assistant_tool_use("Read", {"file_path": "/repo/src/app.py"}, "toolu_01", text="Reading the file."),
        _user_tool_result("toolu_01", "1\tdef main():\n2\t    return 1\n"),
        _assistant_tool_use(
            "Edit",
            {"file_path": "/repo/src/app.py", "old_string": "return 1", "new_string": "return 0"},
            "toolu_02",
            text="I will fix it.",
        ),
        _user_tool_result("toolu_02", "The file has been updated."),
        _assistant_text("Fixed the return value."),
    ]


def _reviewer_readonly_transcript() -> list[dict]:
    return [
        _user_text("Review /repo/src/app.py for correctness."),
        _assistant_tool_use("Read", {"file_path": "/repo/src/app.py"}, "toolu_01"),
        _user_tool_result("toolu_01", "1\tdef main():\n"),
        _assistant_tool_use("Grep", {"pattern": "main", "path": "/repo"}, "toolu_02"),
        _user_tool_result("toolu_02", "src/app.py"),
        _assistant_tool_use("Bash", {"command": "git log --oneline -3"}, "toolu_03"),
        _user_tool_result("toolu_03", "abc123 init"),
        _assistant_text("No issues found."),
    ]


class TestRealTranscriptShape:
    """Tier 2 and Tier 3 scanners on the nested message.content shape."""

    def test_regression_old_scanner_missed_nested_tool_use(self):
        """The 1.0.3 scanner read only top-level fields and missed this Edit."""
        path = _make_transcript(_reviewer_wrote_transcript())
        assert _old_find_write_tool_in_transcript(path) is None
        assert find_write_tool_in_transcript(path) == "Edit(/repo/src/app.py)"

    def test_nested_write_detected(self):
        path = _make_transcript(
            [
                _user_text("Review the plan."),
                _assistant_tool_use("Write", {"file_path": "/repo/notes.md", "content": "x"}, "toolu_01"),
                _user_tool_result("toolu_01", "File created successfully"),
            ]
        )
        assert find_write_tool_in_transcript(path) == "Write(/repo/notes.md)"

    def test_nested_notebookedit_reports_notebook_path(self):
        path = _make_transcript(
            [_assistant_tool_use("NotebookEdit", {"notebook_path": "/repo/a.ipynb", "new_source": "x"}, "toolu_01")]
        )
        assert find_write_tool_in_transcript(path) == "NotebookEdit(/repo/a.ipynb)"

    def test_nested_write_after_text_block_detected(self):
        """A tool_use after a text block in the same message still counts."""
        path = _make_transcript(
            [_assistant_tool_use("Write", {"file_path": "/repo/x.txt"}, "toolu_01", text="Writing now.")]
        )
        assert find_write_tool_in_transcript(path) == "Write(/repo/x.txt)"

    def test_nested_readonly_transcript_clean(self):
        path = _make_transcript(_reviewer_readonly_transcript())
        assert find_write_tool_in_transcript(path) is None

    def test_text_naming_a_write_tool_not_counted(self):
        """Only tool_use blocks count, not prompt or result text that names a write tool."""
        path = _make_transcript(
            [
                _user_text('Do not call {"type": "tool_use", "name": "Write"}.'),
                _assistant_tool_use("Bash", {"command": "echo Write"}, "toolu_01"),
                _user_tool_result("toolu_01", '{"type": "tool_use", "name": "Edit", "input": {}}'),
            ]
        )
        assert find_write_tool_in_transcript(path) is None

    def test_string_message_content_no_crash(self):
        path = _make_transcript([_user_text("plain prompt"), {"type": "assistant", "message": {"content": "done"}}])
        assert find_write_tool_in_transcript(path) is None

    def test_malformed_lines_and_blocks_skipped(self):
        path = _make_transcript(
            [
                ["not", "an", "object"],
                {"type": "assistant", "message": {"content": ["text", None, {"type": "tool_use"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": "bad"}]}},
            ]
        )
        assert find_write_tool_in_transcript(path) == "Edit"

    def test_flat_shape_still_detected(self):
        """The old flat shape stays supported as a fallback."""
        path = _make_transcript([{"tool_name": "Edit", "tool_input": {"file_path": "/src.py"}}])
        assert find_write_tool_in_transcript(path) == "Edit(/src.py)"

    def test_mixed_shapes_in_one_transcript(self):
        path = _make_transcript(
            [
                {"tool_name": "Read", "tool_input": {"file_path": "/a"}},
                _assistant_tool_use("Read", {"file_path": "/b"}, "toolu_01"),
                _assistant_tool_use("Edit", {"file_path": "/c"}, "toolu_02"),
            ]
        )
        assert find_write_tool_in_transcript(path) == "Edit(/c)"

    def test_reviewer_with_nested_edit_blocks(self):
        path = _make_transcript(_reviewer_wrote_transcript())
        result = check_readonly_violation("reviewer-code", path)
        assert result is not None
        assert "Edit(/repo/src/app.py)" in result

    def test_nested_git_push_detected(self):
        path = _make_transcript(
            [
                _assistant_tool_use("Bash", {"command": "git status"}, "toolu_01"),
                _assistant_tool_use("Bash", {"command": "git push origin feature"}, "toolu_02"),
            ]
        )
        assert find_gated_command_in_transcript(path) == "git push origin feature"

    def test_nested_safe_bash_not_detected(self):
        path = _make_transcript(_reviewer_readonly_transcript())
        assert find_gated_command_in_transcript(path) is None


# ---------------------------------------------------------------------------
# main(): which transcript the guard scans
# ---------------------------------------------------------------------------


def _run_hook(event: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PROTECTED_ORGS", mod._BYPASS_ENV)}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=10,
    )


def _stop_event(tmp_path: Path, agent_type: str, **paths: str) -> dict:
    return {
        "session_id": "test-session",
        "hook_event_name": "SubagentStop",
        "cwd": str(tmp_path),
        "agent_id": "agent-test",
        "agent_type": agent_type,
        "stop_hook_active": False,
        **paths,
    }


class TestMainTranscriptSelection:
    def test_agent_transcript_with_nested_edit_denies(self, tmp_path):
        agent = _make_transcript(_reviewer_wrote_transcript())
        result = _run_hook(_stop_event(tmp_path, "reviewer-code", agent_transcript_path=agent), tmp_path)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["permissionDecision"] == "deny"
        assert "Edit(/repo/src/app.py)" in out["permissionDecisionReason"]

    def test_parent_transcript_writes_not_charged_to_reviewer(self, tmp_path):
        """transcript_path is the parent session on SubagentStop; its writes are not the reviewer's."""
        parent = _make_transcript(_reviewer_wrote_transcript())
        agent = _make_transcript(_reviewer_readonly_transcript())
        event = _stop_event(tmp_path, "reviewer-code", transcript_path=parent, agent_transcript_path=agent)
        result = _run_hook(event, tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_missing_agent_transcript_skips_with_note(self, tmp_path):
        parent = _make_transcript(_reviewer_wrote_transcript())
        result = _run_hook(_stop_event(tmp_path, "reviewer-code", transcript_path=parent), tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "[readonly-guard] skipped for reviewer-code" in result.stderr

    def test_non_reviewer_with_nested_edit_passes(self, tmp_path):
        agent = _make_transcript(_reviewer_wrote_transcript())
        result = _run_hook(_stop_event(tmp_path, "general-purpose", agent_transcript_path=agent), tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert "[readonly-guard]" not in result.stderr
