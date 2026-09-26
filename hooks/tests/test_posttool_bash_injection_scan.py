"""
Tests for hooks/posttool-bash-injection-scan.py -- PostToolUse Bash injection scanner.

Run with: python3 -m pytest hooks/tests/test_posttool_bash_injection_scan.py -v

Covers:
- _extract_written_paths() detection of write patterns
- Known non-matches (plain commands without a write)
"""

import importlib.util
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "posttool-bash-injection-scan.py"

spec = importlib.util.spec_from_file_location("posttool_bash_injection_scan", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_extract_written_paths = mod._extract_written_paths


# ---------------------------------------------------------------------------
# _extract_written_paths: positive matches
# ---------------------------------------------------------------------------


class TestExtractWrittenPathsPositive:
    def test_redirect_single(self):
        paths = _extract_written_paths("echo hello > /project/agents/evil.md")
        assert "/project/agents/evil.md" in paths

    def test_redirect_append(self):
        paths = _extract_written_paths("echo hello >> /project/agents/evil.md")
        assert "/project/agents/evil.md" in paths

    def test_tee(self):
        paths = _extract_written_paths("echo hello | tee /project/CLAUDE.md")
        assert "/project/CLAUDE.md" in paths

    def test_tee_append(self):
        paths = _extract_written_paths("echo hello | tee -a /project/CLAUDE.md")
        assert "/project/CLAUDE.md" in paths

    def test_cp(self):
        paths = _extract_written_paths("cp /tmp/evil.md /project/agents/target.md")
        assert "/project/agents/target.md" in paths

    def test_multiple_writes(self):
        paths = _extract_written_paths("echo a > file1.md && echo b >> file2.md")
        assert "file1.md" in paths
        assert "file2.md" in paths

    def test_redirect_with_quotes(self):
        """Quotes around the path are stripped."""
        paths = _extract_written_paths("echo x > 'agents/test.md'")
        assert "agents/test.md" in paths

    def test_redirect_with_double_quotes(self):
        paths = _extract_written_paths('echo x > "agents/test.md"')
        assert "agents/test.md" in paths


# ---------------------------------------------------------------------------
# _extract_written_paths: negative matches
# ---------------------------------------------------------------------------


class TestExtractWrittenPathsNegative:
    def test_no_redirect(self):
        paths = _extract_written_paths("ls -la /tmp")
        assert paths == []

    def test_echo_without_redirect(self):
        paths = _extract_written_paths("echo hello world")
        assert paths == []
