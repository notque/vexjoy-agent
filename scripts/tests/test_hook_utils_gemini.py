"""Tests for Gemini CLI detection and input normalization in hooks/lib/hook_utils.py."""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

_HOOK_UTILS_PATH = Path(__file__).resolve().parent.parent.parent / "hooks" / "lib" / "hook_utils.py"


def _load_module():
    """Load hook_utils.py as a module."""
    spec = importlib.util.spec_from_file_location("hook_utils", _HOOK_UTILS_PATH)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
detect_cli = _mod.detect_cli
normalize_input = _mod.normalize_input


# ---------------------------------------------------------------------------
# detect_cli tests
# ---------------------------------------------------------------------------


class TestDetectCli:
    """Tests for the detect_cli() function."""

    @staticmethod
    def _clean_env() -> dict[str, str]:
        """Return env dict stripped of Gemini/Codex/_ vars."""
        return {k: v for k, v in os.environ.items() if not k.startswith(("GEMINI_", "CODEX_")) and k != "_"}

    def test_detects_gemini_via_gemini_cli_env(self):
        """detect_cli returns 'gemini' when GEMINI_CLI is set."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["GEMINI_CLI"] = "1"
            assert detect_cli() == "gemini"

    def test_detects_gemini_via_underscore_var(self):
        """detect_cli returns 'gemini' when _ contains 'gemini'."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["_"] = "/usr/local/bin/gemini"
            assert detect_cli() == "gemini"

    def test_detects_codex_via_underscore_var(self):
        """detect_cli returns 'codex' when _ contains 'codex'."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["_"] = "/usr/local/bin/codex"
            assert detect_cli() == "codex"

    def test_detects_codex_via_codex_home(self):
        """detect_cli returns 'codex' when CODEX_HOME is set."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["CODEX_HOME"] = "/home/user/.codex"
            assert detect_cli() == "codex"

    def test_detects_codex_via_hooks_dir(self):
        """detect_cli returns 'codex' when CODEX_HOOKS_DIR is set."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["CODEX_HOOKS_DIR"] = "/home/user/.codex/hooks"
            assert detect_cli() == "codex"

    def test_defaults_to_claude(self):
        """detect_cli returns 'claude' when no Gemini or Codex vars are set."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            assert detect_cli() == "claude"

    def test_gemini_cli_env_takes_precedence_over_codex(self):
        """When both GEMINI_CLI and Codex vars are set, Gemini wins."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["GEMINI_CLI"] = "1"
            os.environ["CODEX_HOME"] = "/home/user/.codex"
            assert detect_cli() == "gemini"

    def test_gemini_api_key_alone_does_not_trigger_gemini(self):
        """GEMINI_API_KEY alone should NOT cause detection as gemini (false positive)."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["GEMINI_API_KEY"] = "test-key"
            assert detect_cli() == "claude"

    def test_underscore_var_case_insensitive(self):
        """_ var detection is case-insensitive."""
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            os.environ["_"] = "/opt/Gemini-CLI/bin/Gemini"
            assert detect_cli() == "gemini"


# ---------------------------------------------------------------------------
# normalize_input tests
# ---------------------------------------------------------------------------


class TestNormalizeInput:
    """Tests for the normalize_input() function."""

    def test_translates_tool_input_to_input(self):
        """tool_input is copied to input."""
        data = {"tool_input": "ls -la", "other": "value"}
        result = normalize_input(data)
        assert result["input"] == "ls -la"
        assert result["tool_input"] == "ls -la"  # Original preserved
        assert result["other"] == "value"

    def test_translates_tool_name_to_tool(self):
        """tool_name is copied to tool."""
        data = {"tool_name": "run_shell_command", "other": "value"}
        result = normalize_input(data)
        assert result["tool"] == "run_shell_command"
        assert result["tool_name"] == "run_shell_command"  # Original preserved

    def test_does_not_overwrite_existing_input(self):
        """If 'input' already exists, tool_input does not overwrite it."""
        data = {"tool_input": "gemini-value", "input": "claude-value"}
        result = normalize_input(data)
        assert result["input"] == "claude-value"

    def test_does_not_overwrite_existing_tool(self):
        """If 'tool' already exists, tool_name does not overwrite it."""
        data = {"tool_name": "run_shell_command", "tool": "Bash"}
        result = normalize_input(data)
        assert result["tool"] == "Bash"

    def test_passthrough_claude_format(self):
        """Claude/Codex format data passes through unchanged."""
        data = {"input": "ls -la", "tool": "Bash"}
        result = normalize_input(data)
        assert result == {"input": "ls -la", "tool": "Bash"}

    def test_empty_dict(self):
        """Empty dict passes through unchanged."""
        data: dict = {}
        result = normalize_input(data)
        assert result == {}

    def test_mutates_in_place(self):
        """normalize_input mutates the dict in place and returns it."""
        data = {"tool_input": "test"}
        result = normalize_input(data)
        assert result is data  # Same object
        assert data["input"] == "test"

    def test_both_gemini_fields_translated(self):
        """Both tool_input and tool_name are translated in one call."""
        data = {"tool_input": "ls", "tool_name": "run_shell_command"}
        result = normalize_input(data)
        assert result["input"] == "ls"
        assert result["tool"] == "run_shell_command"
