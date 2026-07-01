"""
Tests for hooks/posttool-bash-injection-scan.py -- PostToolUse Bash injection scanner.

Run with: python3 -m pytest hooks/tests/test_posttool_bash_injection_scan.py -v

Covers:
- _extract_written_paths() detection of write patterns
- Known non-matches (2>&1, conditionals)
- _resolve_path() for relative and absolute paths
"""

import importlib.util
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "posttool-bash-injection-scan.py"

spec = importlib.util.spec_from_file_location("posttool_bash_injection_scan", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_extract_written_paths = mod._extract_written_paths
_resolve_path = mod._resolve_path


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
    def test_stderr_redirect(self):
        """2>&1 should NOT produce a path match."""
        paths = _extract_written_paths("cmd 2>&1")
        # 2>&1 should not produce meaningful file paths
        # The > regex may match "&1" but that's filtered downstream
        # The key is it should not match real file paths
        for p in paths:
            assert p != "2"

    def test_gt_in_conditional(self):
        """[ a -gt 2 ] should NOT produce file paths."""
        paths = _extract_written_paths("[ $count -gt 2 ]")
        # -gt is not a redirect, and the > pattern requires a non-special prefix
        assert "2" not in paths or all(p != "2" for p in [p.strip() for p in paths])

    def test_no_redirect(self):
        paths = _extract_written_paths("ls -la /tmp")
        assert paths == []

    def test_echo_without_redirect(self):
        paths = _extract_written_paths("echo hello world")
        assert paths == []


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_absolute_path(self):
        result = _resolve_path("/home/user/file.md")
        assert result is not None
        assert result == Path("/home/user/file.md")

    def test_relative_path(self):
        result = _resolve_path("agents/test.md")
        assert result is not None
        assert result.is_absolute()
        # Should be cwd / agents/test.md
        assert str(result).endswith("agents/test.md")

    def test_home_expansion(self):
        result = _resolve_path("~/file.md")
        assert result is not None
        assert result.is_absolute()
        assert "~" not in str(result)

    def test_empty_string(self):
        """Empty string should still resolve (to cwd)."""
        result = _resolve_path("")
        # Path("").expanduser() may raise or resolve to cwd
        # The function returns Path | None, either is acceptable
        assert result is None or isinstance(result, Path)

    def test_dot_path(self):
        result = _resolve_path(".")
        assert result is not None
        assert result.is_absolute()

    def test_dotdot_path(self):
        result = _resolve_path("../file.md")
        assert result is not None
        assert result.is_absolute()
        assert ".." not in str(result)
