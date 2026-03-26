#!/usr/bin/env python3
"""
Tests for the pretool-config-protection hook.

Run with: python3 -m pytest hooks/tests/test_config_protection.py -v
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-config-protection.py"

spec = importlib.util.spec_from_file_location("pretool_config_protection", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_is_protected = mod._is_protected
_PROTECTED_CONFIGS = mod._PROTECTED_CONFIGS
_MAX_STDIN_BYTES = mod._MAX_STDIN_BYTES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(tool_name: str, file_path: str | None = None, edits: list | None = None) -> str:
    """Build a JSON hook event payload."""
    tool_input: dict = {}
    if file_path is not None:
        tool_input["file_path"] = file_path
    if edits is not None:
        tool_input["edits"] = edits
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input})


def _run_main(stdin_payload: str, env: dict | None = None) -> int:
    """
    Invoke mod.main() in-process, capturing the exit code.

    Returns the integer exit code (0 = allow, 2 = block).
    """
    base_env = {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}
    if env:
        base_env.update(env)

    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
    ):
        try:
            mod.main()
            return 0
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0


# ---------------------------------------------------------------------------
# Unit tests: _is_protected
# ---------------------------------------------------------------------------


class TestIsProtected:
    """Unit tests for the _is_protected helper (basename matching)."""

    def test_eslintrc_js_is_protected(self):
        assert _is_protected(".eslintrc.js") is True

    def test_eslintrc_with_full_path_is_protected(self):
        assert _is_protected("/project/frontend/.eslintrc.js") is True

    def test_eslint_config_flat_is_protected(self):
        assert _is_protected("eslint.config.mjs") is True

    def test_prettierrc_is_protected(self):
        assert _is_protected(".prettierrc") is True

    def test_prettierrc_json_is_protected(self):
        assert _is_protected("/app/.prettierrc.json") is True

    def test_biome_json_is_protected(self):
        assert _is_protected("biome.json") is True

    def test_biome_jsonc_is_protected(self):
        assert _is_protected("biome.jsonc") is True

    def test_ruff_toml_is_protected(self):
        assert _is_protected("ruff.toml") is True

    def test_dot_ruff_toml_is_protected(self):
        assert _is_protected(".ruff.toml") is True

    def test_golangci_yml_is_protected(self):
        assert _is_protected(".golangci.yml") is True

    def test_golangci_yaml_is_protected(self):
        assert _is_protected(".golangci.yaml") is True

    def test_golangci_json_is_protected(self):
        assert _is_protected(".golangci.json") is True

    def test_golangci_toml_is_protected(self):
        assert _is_protected(".golangci.toml") is True

    def test_setup_cfg_is_protected(self):
        assert _is_protected("setup.cfg") is True

    def test_shellcheckrc_is_protected(self):
        assert _is_protected(".shellcheckrc") is True

    def test_stylelintrc_is_protected(self):
        assert _is_protected(".stylelintrc") is True

    def test_markdownlint_json_is_protected(self):
        assert _is_protected(".markdownlint.json") is True

    def test_markdownlintrc_is_protected(self):
        assert _is_protected(".markdownlintrc") is True

    def test_normal_py_file_not_protected(self):
        assert _is_protected("main.py") is False

    def test_normal_go_file_not_protected(self):
        assert _is_protected("handler.go") is False

    def test_pyproject_toml_not_protected(self):
        """pyproject.toml is intentionally excluded — it's a project metadata file."""
        assert _is_protected("pyproject.toml") is False

    def test_env_file_not_protected(self):
        """Env files are handled by sensitive-file-guard, not this hook."""
        assert _is_protected(".env") is False

    def test_gitignore_not_protected(self):
        assert _is_protected(".gitignore") is False

    def test_settings_json_not_protected(self):
        """.claude/settings.json is handled by sensitive-file-guard."""
        assert _is_protected("settings.json") is False

    def test_partial_name_not_matched(self):
        """'myeslintrc.js' is not the same as '.eslintrc.js'."""
        assert _is_protected("myeslintrc.js") is False

    def test_subdirectory_eslintrc_still_blocked(self):
        """Deep path — only the basename is checked."""
        assert _is_protected("/a/b/c/d/.eslintrc.yml") is True


# ---------------------------------------------------------------------------
# Protected set completeness
# ---------------------------------------------------------------------------


class TestProtectedSetCompleteness:
    """Verify the protected set matches the ADR spec exactly."""

    def test_protected_set_has_38_entries(self):
        """Protected set: ESLint(12) + Prettier(10) + Biome(2) + Ruff(2) + Shell/Style/MD(7) + golangci(4) + setup.cfg(1) = 38."""
        assert len(_PROTECTED_CONFIGS) == 38

    def test_all_eslint_variants_present(self):
        eslint_files = [
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.cjs",
            ".eslintrc.json",
            ".eslintrc.yml",
            ".eslintrc.yaml",
            "eslint.config.js",
            "eslint.config.mjs",
            "eslint.config.cjs",
            "eslint.config.ts",
            "eslint.config.mts",
            "eslint.config.cts",
        ]
        for f in eslint_files:
            assert f in _PROTECTED_CONFIGS, f"Missing ESLint config: {f}"

    def test_all_prettier_variants_present(self):
        prettier_files = [
            ".prettierrc",
            ".prettierrc.js",
            ".prettierrc.cjs",
            ".prettierrc.mjs",
            ".prettierrc.json",
            ".prettierrc.yml",
            ".prettierrc.yaml",
            "prettier.config.js",
            "prettier.config.cjs",
            "prettier.config.mjs",
        ]
        for f in prettier_files:
            assert f in _PROTECTED_CONFIGS, f"Missing Prettier config: {f}"

    def test_all_shell_style_md_variants_present(self):
        shell_style_md_files = [
            ".shellcheckrc",
            ".stylelintrc",
            ".stylelintrc.json",
            ".stylelintrc.yml",
            ".markdownlint.json",
            ".markdownlint.yaml",
            ".markdownlintrc",
        ]
        for f in shell_style_md_files:
            assert f in _PROTECTED_CONFIGS, f"Missing Shell/Style/MD config: {f}"

    def test_all_golangci_variants_present(self):
        go_files = [".golangci.yml", ".golangci.yaml", ".golangci.json", ".golangci.toml"]
        for f in go_files:
            assert f in _PROTECTED_CONFIGS, f"Missing golangci config: {f}"


# ---------------------------------------------------------------------------
# Integration tests: main() via _run_main
# ---------------------------------------------------------------------------


class TestWriteToolBlocked:
    """Write tool targeting a protected config file must be blocked (exit 2)."""

    def test_write_eslintrc_js_blocked(self):
        payload = _make_event("Write", file_path=".eslintrc.js")
        assert _run_main(payload) == 2

    def test_write_eslintrc_js_full_path_blocked(self):
        payload = _make_event("Write", file_path="/project/.eslintrc.js")
        assert _run_main(payload) == 2

    def test_write_ruff_toml_blocked(self):
        payload = _make_event("Write", file_path="ruff.toml")
        assert _run_main(payload) == 2

    def test_write_golangci_yml_blocked(self):
        payload = _make_event("Write", file_path=".golangci.yml")
        assert _run_main(payload) == 2

    def test_write_biome_json_blocked(self):
        payload = _make_event("Write", file_path="biome.json")
        assert _run_main(payload) == 2

    def test_write_setup_cfg_blocked(self):
        payload = _make_event("Write", file_path="setup.cfg")
        assert _run_main(payload) == 2

    def test_write_prettierrc_blocked(self):
        payload = _make_event("Write", file_path=".prettierrc")
        assert _run_main(payload) == 2


class TestEditToolBlocked:
    """Edit tool targeting a protected config file must be blocked (exit 2)."""

    def test_edit_eslintrc_blocked(self):
        payload = _make_event("Edit", file_path=".eslintrc")
        assert _run_main(payload) == 2

    def test_edit_golangci_toml_blocked(self):
        payload = _make_event("Edit", file_path=".golangci.toml")
        assert _run_main(payload) == 2

    def test_edit_markdownlint_json_blocked(self):
        payload = _make_event("Edit", file_path=".markdownlint.json")
        assert _run_main(payload) == 2


class TestMultiEditToolBlocked:
    """MultiEdit targeting any protected config file must be blocked (exit 2)."""

    def test_multiedit_single_protected_file_blocked(self):
        edits = [{"file_path": ".eslintrc.js", "old_string": "error", "new_string": "warn"}]
        payload = _make_event("MultiEdit", edits=edits)
        assert _run_main(payload) == 2

    def test_multiedit_mixed_files_blocked_if_any_protected(self):
        """If any edit in the list targets a protected file, the whole call is blocked."""
        edits = [
            {"file_path": "main.py", "old_string": "x", "new_string": "y"},
            {"file_path": ".eslintrc.json", "old_string": "error", "new_string": "warn"},
            {"file_path": "README.md", "old_string": "a", "new_string": "b"},
        ]
        payload = _make_event("MultiEdit", edits=edits)
        assert _run_main(payload) == 2

    def test_multiedit_all_safe_files_allowed(self):
        edits = [
            {"file_path": "main.py", "old_string": "x", "new_string": "y"},
            {"file_path": "handler.go", "old_string": "a", "new_string": "b"},
        ]
        payload = _make_event("MultiEdit", edits=edits)
        assert _run_main(payload) == 0

    def test_multiedit_empty_edits_list_allowed(self):
        payload = _make_event("MultiEdit", edits=[])
        assert _run_main(payload) == 0

    def test_multiedit_golangci_json_blocked(self):
        edits = [{"file_path": "/repo/.golangci.json", "old_string": "enable", "new_string": "disable"}]
        payload = _make_event("MultiEdit", edits=edits)
        assert _run_main(payload) == 2


class TestAllowedSourceFiles:
    """Normal source files must pass through unaffected (exit 0)."""

    def test_write_py_source_allowed(self):
        payload = _make_event("Write", file_path="src/main.py")
        assert _run_main(payload) == 0

    def test_write_go_source_allowed(self):
        payload = _make_event("Write", file_path="cmd/server/main.go")
        assert _run_main(payload) == 0

    def test_write_ts_source_allowed(self):
        payload = _make_event("Write", file_path="src/index.ts")
        assert _run_main(payload) == 0

    def test_write_pyproject_toml_allowed(self):
        """pyproject.toml is intentionally excluded from protection."""
        payload = _make_event("Write", file_path="pyproject.toml")
        assert _run_main(payload) == 0

    def test_edit_readme_allowed(self):
        payload = _make_event("Edit", file_path="README.md")
        assert _run_main(payload) == 0

    def test_write_dockerfile_allowed(self):
        payload = _make_event("Write", file_path="Dockerfile")
        assert _run_main(payload) == 0

    def test_write_env_example_allowed(self):
        """.env.example is NOT a linter config — allowed through."""
        payload = _make_event("Write", file_path=".env.example")
        assert _run_main(payload) == 0

    def test_bash_tool_ignored(self):
        """This hook only checks Write/Edit/MultiEdit — Bash is ignored."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "cat .eslintrc.js"}})
        assert _run_main(payload) == 0

    def test_read_tool_ignored(self):
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": ".eslintrc.js"}})
        assert _run_main(payload) == 0


class TestBypassMechanism:
    """CONFIG_PROTECTION_BYPASS=1 must allow any write through."""

    def test_bypass_allows_eslintrc_write(self):
        payload = _make_event("Write", file_path=".eslintrc.js")
        assert _run_main(payload, env={"CONFIG_PROTECTION_BYPASS": "1"}) == 0

    def test_bypass_allows_golangci_edit(self):
        payload = _make_event("Edit", file_path=".golangci.yml")
        assert _run_main(payload, env={"CONFIG_PROTECTION_BYPASS": "1"}) == 0

    def test_bypass_allows_multiedit_with_protected_files(self):
        edits = [{"file_path": "ruff.toml", "old_string": "a", "new_string": "b"}]
        payload = _make_event("MultiEdit", edits=edits)
        assert _run_main(payload, env={"CONFIG_PROTECTION_BYPASS": "1"}) == 0

    def test_bypass_value_zero_does_not_bypass(self):
        """Only '1' triggers the bypass — '0' must still block."""
        payload = _make_event("Write", file_path=".eslintrc.js")
        assert _run_main(payload, env={"CONFIG_PROTECTION_BYPASS": "0"}) == 2

    def test_bypass_value_true_does_not_bypass(self):
        """Only the exact string '1' triggers the bypass."""
        payload = _make_event("Write", file_path=".eslintrc.js")
        assert _run_main(payload, env={"CONFIG_PROTECTION_BYPASS": "true"}) == 2


class TestTruncationSafety:
    """Oversized stdin must block rather than fail open."""

    def test_oversized_payload_blocks(self):
        """A payload larger than _MAX_STDIN_BYTES must exit 2."""
        # Generate a payload that just exceeds 1 MB
        oversized = "x" * (_MAX_STDIN_BYTES + 1)
        with (
            patch.dict(
                os.environ, {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}, clear=True
            ),
            patch.object(mod, "read_stdin", return_value=oversized),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
        assert result == 2

    def test_exactly_at_limit_is_allowed(self):
        """A payload exactly at _MAX_STDIN_BYTES bytes is valid JSON → process normally."""
        # Use a valid JSON payload that happens to be at the limit — we just
        # need to verify the size check itself does not block at the boundary.
        # Since a 1 MB well-formed JSON payload is impractical to construct,
        # we test the boundary indirectly by mocking:
        safe_payload = _make_event("Write", file_path="main.py")
        assert len(safe_payload.encode("utf-8")) < _MAX_STDIN_BYTES
        assert _run_main(safe_payload) == 0

    def test_exactly_max_stdin_bytes_boundary(self):
        """A payload of exactly _MAX_STDIN_BYTES UTF-8 bytes must not be blocked by the size check."""
        # Build a string whose UTF-8 encoding is exactly _MAX_STDIN_BYTES bytes.
        # All ASCII characters are 1 byte each, so we pad with 'x'.
        base = _make_event("Write", file_path="main.py")
        base_bytes = base.encode("utf-8")
        padding_needed = _MAX_STDIN_BYTES - len(base_bytes)
        assert padding_needed >= 0, "Base payload already exceeds _MAX_STDIN_BYTES"
        # Wrap in a JSON string field that soaks up the padding so the total
        # byte length is exactly _MAX_STDIN_BYTES. We construct the payload
        # manually to hit the exact byte boundary.
        exact_payload = "x" * _MAX_STDIN_BYTES
        assert len(exact_payload.encode("utf-8")) == _MAX_STDIN_BYTES
        # The size check is `> _MAX_STDIN_BYTES`, so exactly at the limit must
        # NOT exit 2 due to the size guard (it will exit 0 because the string
        # is not valid JSON for the hook's purposes).
        with (
            patch.dict(
                os.environ, {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}, clear=True
            ),
            patch.object(mod, "read_stdin", return_value=exact_payload),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
        # Must fail open (0), not block (2) — size is at the limit, not over it.
        assert result == 0


class TestMalformedInput:
    """Malformed or empty input must fail open (exit 0)."""

    def test_empty_stdin_allows(self):
        with (
            patch.dict(
                os.environ, {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}, clear=True
            ),
            patch.object(mod, "read_stdin", return_value=""),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
        assert result == 0

    def test_invalid_json_allows(self):
        with (
            patch.dict(
                os.environ, {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}, clear=True
            ),
            patch.object(mod, "read_stdin", return_value="not valid json {{{"),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
        assert result == 0

    def test_missing_tool_input_allows(self):
        payload = json.dumps({"tool_name": "Write"})
        assert _run_main(payload) == 0

    def test_empty_file_path_allows(self):
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": ""}})
        assert _run_main(payload) == 0


class TestBlockMessageContent:
    """Verify the block message directs the agent to fix source, not config."""

    def test_block_message_mentions_source_code(self, capsys):
        payload = _make_event("Write", file_path=".eslintrc.js")
        with (
            patch.dict(
                os.environ, {k: v for k, v in os.environ.items() if k != "CONFIG_PROTECTION_BYPASS"}, clear=True
            ),
            patch.object(mod, "read_stdin", return_value=payload),
        ):
            try:
                mod.main()
            except SystemExit:
                pass

        captured = capsys.readouterr()
        assert "BLOCKED" in captured.err
        assert ".eslintrc.js" in captured.err
        assert "source code" in captured.err
        assert "CONFIG_PROTECTION_BYPASS=1" in captured.err
