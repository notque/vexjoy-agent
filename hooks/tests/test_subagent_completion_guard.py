#!/usr/bin/env python3
"""
Tests for the subagent-completion-guard hook.

Run with: python3 -m pytest hooks/tests/test_subagent_completion_guard.py -v
"""

import importlib.util
import json
import os
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
record_worktree_learning = mod.record_worktree_learning
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


class TestRecordWorktreeLearning:
    """Test learning DB recording (best-effort)."""

    def test_empty_meta_does_nothing(self):
        """No worktree metadata — should not attempt DB access."""
        # Should not raise
        record_worktree_learning({}, "some-agent")

    def test_no_branch_does_nothing(self):
        """Worktree detected but no branch (detached HEAD) — skip recording."""
        record_worktree_learning(
            {"is_worktree": True, "branch": "", "worktree_path": "/tmp/wt", "commits_ahead": 0, "uncommitted_files": 0},
            "some-agent",
        )

    def test_records_to_learning_db(self):
        """Verify record_learning is called with correct args."""
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt-feat",
            "branch": "feat/audit-impl",
            "commits_ahead": 3,
            "has_uncommitted": False,
            "uncommitted_files": 0,
        }
        mock_record = MagicMock()
        mock_module = MagicMock()
        mock_module.record_learning = mock_record

        with patch.dict("sys.modules", {"learning_db_v2": mock_module}):
            record_worktree_learning(meta, "golang-general-engineer")

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args
        assert call_kwargs[1]["topic"] == "worktree-branches"
        assert call_kwargs[1]["key"] == "worktree-feat/audit-impl"
        assert "path=/tmp/wt-feat" in call_kwargs[1]["value"]
        assert call_kwargs[1]["category"] == "effectiveness"
        assert call_kwargs[1]["confidence"] == 0.8
        assert "worktree" in call_kwargs[1]["tags"]
        assert "feat/audit-impl" in call_kwargs[1]["tags"]
        assert "golang-general-engineer" in call_kwargs[1]["tags"]
        assert call_kwargs[1]["source"] == "hook:subagent-completion-guard"

    def test_exception_in_db_does_not_raise(self):
        """Learning DB errors must be swallowed silently."""
        meta = {
            "is_worktree": True,
            "worktree_path": "/tmp/wt",
            "branch": "feat/test",
            "commits_ahead": 1,
            "has_uncommitted": False,
            "uncommitted_files": 0,
        }
        # Should not raise even if DB import fails
        record_worktree_learning(meta, "test-agent")


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
        assert result == "Write"

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
        assert result == "Write"

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

    def test_empty_protected_orgs_returns_false(self):
        with patch.dict(os.environ, {"PROTECTED_ORGS": ""}):
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
