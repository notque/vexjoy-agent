"""Tests for scripts/ensure-codex-feature-flag.py.

Covers: missing file, empty file, no [features] section, [features] without
key, already present, codex_hooks = false error, idempotency, section
preservation, --dry-run, backup creation, and CLI end-to-end via subprocess.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# tomllib is stdlib on Python 3.11+. On 3.10, skip the subset of tests that
# use it for post-write TOML validity checks. The write logic itself is pure
# string ops and works on 3.10+ unchanged.
try:
    import tomllib  # type: ignore[import-not-found,unused-ignore]

    _HAS_TOMLLIB = True
except ImportError:
    tomllib = None  # type: ignore[assignment]
    _HAS_TOMLLIB = False

requires_tomllib = pytest.mark.skipif(not _HAS_TOMLLIB, reason="tomllib requires Python 3.11+")

MODULE_PATH = Path(__file__).resolve().parent.parent / "ensure-codex-feature-flag.py"
_SPEC = importlib.util.spec_from_file_location("ensure_codex_feature_flag", MODULE_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)

read_config = _MOD.read_config
needs_update = _MOD.needs_update
apply_update = _MOD.apply_update

# A realistic config drawn from the ADR context.
REALISTIC_CONFIG = """\
[projects."/home/feedgen/claude-code-toolkit"]
trust_level = "trusted"

[projects."/home/feedgen/road-to-aew"]
trust_level = "trusted"

[plugins."github@openai-curated"]
enabled = true

[notice]
hide_rate_limit_model_nudge = true
"""


# ---------------------------------------------------------------------------
# needs_update / action-tag tests
# ---------------------------------------------------------------------------


class TestNeedsUpdate:
    """Unit tests for needs_update() logic."""

    def test_empty_string_returns_created_file(self) -> None:
        """Empty content (missing file) maps to created-file action."""
        write_needed, action = needs_update("")
        assert write_needed is True
        assert action == "created-file"

    def test_no_features_section_returns_added_section(self) -> None:
        """Content with no [features] header maps to added-section."""
        content = "[notice]\nhide_rate_limit_model_nudge = true\n"
        write_needed, action = needs_update(content)
        assert write_needed is True
        assert action == "added-section"

    def test_features_section_without_key_returns_added_key(self) -> None:
        """[features] section lacking codex_hooks maps to added-key."""
        content = "[features]\nother_flag = true\n"
        write_needed, action = needs_update(content)
        assert write_needed is True
        assert action == "added-key"

    def test_codex_hooks_true_returns_already_present(self) -> None:
        """codex_hooks = true means no write is needed."""
        content = "[features]\ncodex_hooks = true\n"
        write_needed, action = needs_update(content)
        assert write_needed is False
        assert action == "already-present"

    def test_codex_hooks_false_exits_2(self) -> None:
        """codex_hooks = false must exit with code 2."""
        content = "[features]\ncodex_hooks = false\n"
        with pytest.raises(SystemExit) as exc_info:
            needs_update(content)
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# apply_update tests
# ---------------------------------------------------------------------------


class TestApplyUpdate:
    """Unit tests for apply_update() content transformation."""

    @requires_tomllib
    def test_missing_file_produces_features_block(self) -> None:
        """Empty string yields a valid [features] block."""
        result = apply_update("")
        assert "[features]\ncodex_hooks = true\n" in result
        parsed = tomllib.loads(result)
        assert parsed["features"]["codex_hooks"] is True

    @requires_tomllib
    def test_no_features_section_appends_block(self) -> None:
        """Appending to non-empty content without [features] preserves original text."""
        original = "[notice]\nhide_rate_limit_model_nudge = true\n"
        result = apply_update(original)
        assert original in result
        assert "[features]\ncodex_hooks = true\n" in result
        parsed = tomllib.loads(result)
        assert parsed["notice"]["hide_rate_limit_model_nudge"] is True
        assert parsed["features"]["codex_hooks"] is True

    @requires_tomllib
    def test_existing_features_adds_key_after_header(self) -> None:
        """codex_hooks is injected directly after the [features] header line."""
        original = "[features]\nother_flag = true\n"
        result = apply_update(original)
        parsed = tomllib.loads(result)
        assert parsed["features"]["other_flag"] is True
        assert parsed["features"]["codex_hooks"] is True

    def test_already_present_returns_identical_content(self) -> None:
        """Content that already has the flag is returned unchanged."""
        original = "[features]\ncodex_hooks = true\n"
        result = apply_update(original)
        assert result == original

    @requires_tomllib
    def test_idempotent_second_call_is_noop(self) -> None:
        """Running apply_update twice yields identical output on the second call."""
        first = apply_update(REALISTIC_CONFIG)
        second = apply_update(first)
        assert first == second

    @requires_tomllib
    def test_realistic_config_preserved_byte_for_byte(self) -> None:
        """All original sections survive the merge unchanged."""
        result = apply_update(REALISTIC_CONFIG)
        assert REALISTIC_CONFIG in result
        parsed = tomllib.loads(result)
        assert parsed["projects"]["/home/feedgen/claude-code-toolkit"]["trust_level"] == "trusted"
        assert parsed["plugins"]["github@openai-curated"]["enabled"] is True
        assert parsed["notice"]["hide_rate_limit_model_nudge"] is True
        assert parsed["features"]["codex_hooks"] is True


# ---------------------------------------------------------------------------
# File I/O tests
# ---------------------------------------------------------------------------


class TestFileIO:
    """Integration tests for read_config and file-level behavior."""

    def test_read_config_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """read_config returns empty string when file does not exist."""
        missing = tmp_path / "config.toml"
        assert read_config(missing) == ""

    def test_read_config_returns_content(self, tmp_path: Path) -> None:
        """read_config returns file text verbatim."""
        cfg = tmp_path / "config.toml"
        cfg.write_text("[notice]\nfoo = true\n", encoding="utf-8")
        assert read_config(cfg) == "[notice]\nfoo = true\n"


# ---------------------------------------------------------------------------
# CLI tests via subprocess
# ---------------------------------------------------------------------------


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run the script as a subprocess and return the result."""
    return subprocess.run(
        [sys.executable, str(MODULE_PATH)] + args,
        capture_output=True,
        text=True,
    )


class TestCLI:
    """End-to-end CLI tests that invoke the script as a subprocess."""

    @requires_tomllib
    def test_missing_file_creates_and_prints_created_file(self, tmp_path: Path) -> None:
        """Missing config is created; stdout reports created-file."""
        cfg = tmp_path / "config.toml"
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 0
        assert result.stdout.strip() == "created-file"
        assert cfg.exists()
        parsed = tomllib.loads(cfg.read_text())
        assert parsed["features"]["codex_hooks"] is True

    @requires_tomllib
    def test_empty_file_adds_section(self, tmp_path: Path) -> None:
        """Empty config gets a [features] section; stdout reports added-section."""
        cfg = tmp_path / "config.toml"
        cfg.write_text("", encoding="utf-8")
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 0
        assert result.stdout.strip() == "added-section"
        parsed = tomllib.loads(cfg.read_text())
        assert parsed["features"]["codex_hooks"] is True

    @requires_tomllib
    def test_existing_features_without_key_adds_key(self, tmp_path: Path) -> None:
        """[features] section without the key gets it added; stdout reports added-key."""
        cfg = tmp_path / "config.toml"
        cfg.write_text("[features]\nother_flag = true\n", encoding="utf-8")
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 0
        assert result.stdout.strip() == "added-key"
        parsed = tomllib.loads(cfg.read_text())
        assert parsed["features"]["codex_hooks"] is True
        assert parsed["features"]["other_flag"] is True

    def test_already_present_is_noop(self, tmp_path: Path) -> None:
        """Pre-existing flag produces no file change and reports already-present."""
        cfg = tmp_path / "config.toml"
        original = "[features]\ncodex_hooks = true\n"
        cfg.write_text(original, encoding="utf-8")
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 0
        assert result.stdout.strip() == "already-present"
        assert cfg.read_text() == original

    def test_codex_hooks_false_exits_2(self, tmp_path: Path) -> None:
        """codex_hooks = false causes exit code 2 with stderr guidance."""
        cfg = tmp_path / "config.toml"
        cfg.write_text("[features]\ncodex_hooks = false\n", encoding="utf-8")
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 2
        assert "manually" in result.stderr.lower() or "manual" in result.stderr.lower()

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        """--dry-run prints new content to stdout but leaves the file unchanged."""
        cfg = tmp_path / "config.toml"
        original = "[notice]\nfoo = true\n"
        cfg.write_text(original, encoding="utf-8")
        result = _run(["--config", str(cfg), "--dry-run", "--no-backup"])
        assert result.returncode == 0
        # File must be untouched.
        assert cfg.read_text() == original
        # Printed content must contain the flag.
        assert "codex_hooks = true" in result.stdout

    def test_backup_is_created(self, tmp_path: Path) -> None:
        """A .bak timestamped file is created from the original before writing."""
        cfg = tmp_path / "config.toml"
        original = "[notice]\nfoo = true\n"
        cfg.write_text(original, encoding="utf-8")
        result = _run(["--config", str(cfg)])
        assert result.returncode == 0
        bak_files = list(tmp_path.glob("config.toml.bak.*"))
        assert len(bak_files) == 1
        assert bak_files[0].read_text() == original

    @requires_tomllib
    def test_realistic_config_survives_round_trip(self, tmp_path: Path) -> None:
        """Full realistic config from ADR example parses correctly after merge."""
        cfg = tmp_path / "config.toml"
        cfg.write_text(REALISTIC_CONFIG, encoding="utf-8")
        result = _run(["--config", str(cfg), "--no-backup"])
        assert result.returncode == 0
        parsed = tomllib.loads(cfg.read_text())
        assert parsed["projects"]["/home/feedgen/road-to-aew"]["trust_level"] == "trusted"
        assert parsed["plugins"]["github@openai-curated"]["enabled"] is True
        assert parsed["notice"]["hide_rate_limit_model_nudge"] is True
        assert parsed["features"]["codex_hooks"] is True
