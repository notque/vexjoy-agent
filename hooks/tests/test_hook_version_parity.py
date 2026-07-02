#!/usr/bin/env python3
"""Tests for the hook-version-parity-check SessionStart hook.

Covers:
- Warns (context injection) when a deployed hook's version header differs.
- Missing deployed file counts as drift.
- Silent on full parity, outside the toolkit repo, and when the deployed dir
  resolves to the checkout's hooks/ dir (symlink install).
- Header-less repo files are skipped (nothing to compare).
- Always exits 0 (subprocess, empty stdin).

Run with: python3 -m pytest hooks/tests/test_hook_version_parity.py -v
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

HOOK_PATH = Path(__file__).parent.parent / "hook-version-parity-check.py"

spec = importlib.util.spec_from_file_location("hook_version_parity_check", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _hook_file(path: Path, version: str | None) -> None:
    """Write a minimal hook file, optionally carrying a version header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"# hook-version: {version}\n" if version else ""
    path.write_text(f"#!/usr/bin/env python3\n{header}pass\n")


def _toolkit_repo(root: Path) -> Path:
    """Make root look like the toolkit repo; return its hooks dir."""
    repo_hooks = root / "hooks"
    _hook_file(repo_hooks / "sync-to-user-claude.py", "1.0.0")
    return repo_hooks


def _run_main(project_dir: Path, deployed_dir: Path) -> str:
    """Run mod.main() with dirs pointed at tmp; return captured stdout."""
    stdout = io.StringIO()
    with (
        patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(project_dir)}),
        patch.object(mod, "DEPLOYED_HOOKS_DIR", deployed_dir),
        patch("sys.stdout", stdout),
    ):
        try:
            mod.main()
        except SystemExit:
            pass
    return stdout.getvalue()


def _context(output: str) -> str:
    """Extract additionalContext from the hook's JSON stdout, or ""."""
    if not output.strip():
        return ""
    parsed = json.loads(output.strip())
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "") or ""


class TestFindDriftedHooks:
    def test_version_mismatch_is_drift(self, tmp_path):
        repo = tmp_path / "repo-hooks"
        deployed = tmp_path / "deployed"
        _hook_file(repo / "recorder.py", "1.2.0")
        _hook_file(deployed / "recorder.py", "1.1.0")
        assert mod.find_drifted_hooks(repo, deployed) == ["recorder.py"]

    def test_missing_deployed_file_is_drift(self, tmp_path):
        repo = tmp_path / "repo-hooks"
        deployed = tmp_path / "deployed"
        deployed.mkdir()
        _hook_file(repo / "brand-new.py", "1.0.0")
        assert mod.find_drifted_hooks(repo, deployed) == ["brand-new.py"]

    def test_matching_versions_no_drift(self, tmp_path):
        repo = tmp_path / "repo-hooks"
        deployed = tmp_path / "deployed"
        _hook_file(repo / "recorder.py", "1.2.0")
        _hook_file(deployed / "recorder.py", "1.2.0")
        assert mod.find_drifted_hooks(repo, deployed) == []

    def test_headerless_repo_file_skipped(self, tmp_path):
        # No version header => nothing to compare => never reported.
        repo = tmp_path / "repo-hooks"
        deployed = tmp_path / "deployed"
        deployed.mkdir()
        _hook_file(repo / "legacy.py", None)
        assert mod.find_drifted_hooks(repo, deployed) == []

    def test_tests_and_pycache_excluded(self, tmp_path):
        repo = tmp_path / "repo-hooks"
        deployed = tmp_path / "deployed"
        deployed.mkdir()
        _hook_file(repo / "tests" / "test_x.py", "9.9.9")
        _hook_file(repo / "__pycache__" / "junk.py", "9.9.9")
        _hook_file(repo / "lib" / "helper.py", "1.0.0")  # lib IS compared
        assert mod.find_drifted_hooks(repo, deployed) == ["lib/helper.py"]


class TestMainBehavior:
    def test_warns_on_mismatch(self, tmp_path):
        repo_hooks = _toolkit_repo(tmp_path / "repo")
        deployed = tmp_path / "deployed"
        _hook_file(repo_hooks / "drifty.py", "2.0.0")
        _hook_file(deployed / "drifty.py", "1.0.0")
        _hook_file(deployed / "sync-to-user-claude.py", "1.0.0")
        ctx = _context(_run_main(tmp_path / "repo", deployed))
        assert "[hook-parity] WARNING" in ctx
        assert "drifty.py" in ctx
        assert "sync-to-user-claude.py" in ctx  # the fix command names the sync script
        assert "python3 ~/.claude/hooks/sync-to-user-claude.py" in ctx

    def test_silent_on_parity(self, tmp_path):
        repo_hooks = _toolkit_repo(tmp_path / "repo")
        deployed = tmp_path / "deployed"
        _hook_file(repo_hooks / "steady.py", "1.0.0")
        _hook_file(deployed / "steady.py", "1.0.0")
        _hook_file(deployed / "sync-to-user-claude.py", "1.0.0")
        assert _context(_run_main(tmp_path / "repo", deployed)) == ""

    def test_silent_outside_toolkit_repo(self, tmp_path):
        # No hooks/sync-to-user-claude.py in the checkout => not the toolkit.
        (tmp_path / "repo" / "hooks").mkdir(parents=True)
        deployed = tmp_path / "deployed"
        _hook_file(deployed / "anything.py", "1.0.0")
        assert _context(_run_main(tmp_path / "repo", deployed)) == ""

    def test_silent_when_deployed_is_symlink_to_checkout(self, tmp_path):
        # Symlink install: ~/.claude/hooks -> <repo>/hooks. Drift impossible.
        repo_hooks = _toolkit_repo(tmp_path / "repo")
        _hook_file(repo_hooks / "any.py", "1.0.0")
        deployed = tmp_path / "deployed-link"
        deployed.symlink_to(repo_hooks)
        assert _context(_run_main(tmp_path / "repo", deployed)) == ""

    def test_silent_when_no_deployed_dir(self, tmp_path):
        _toolkit_repo(tmp_path / "repo")
        assert _context(_run_main(tmp_path / "repo", tmp_path / "missing")) == ""


class TestNonBlocking:
    def test_exit_zero_on_empty_stdin(self):
        p = subprocess.run([sys.executable, str(HOOK_PATH)], input="", capture_output=True, text=True)
        assert p.returncode == 0

    def test_exit_zero_with_unreadable_project_dir(self, tmp_path):
        p = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            env={"CLAUDE_PROJECT_DIR": str(tmp_path / "nope"), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        )
        assert p.returncode == 0
