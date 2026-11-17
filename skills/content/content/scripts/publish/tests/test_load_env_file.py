"""Tests for load_env_file quote stripping in the three WordPress publish scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PUBLISH_DIR = Path(__file__).parent.parent

# Load all three modules to test their individual load_env_file implementations.

_upload_spec = importlib.util.spec_from_file_location(
    "wordpress_upload",
    PUBLISH_DIR / "wordpress-upload.py",
)
_upload_mod = importlib.util.module_from_spec(_upload_spec)
_upload_spec.loader.exec_module(_upload_mod)

_media_spec = importlib.util.spec_from_file_location(
    "wordpress_media_upload",
    PUBLISH_DIR / "wordpress-media-upload.py",
)
_media_mod = importlib.util.module_from_spec(_media_spec)
_media_spec.loader.exec_module(_media_mod)

requests = pytest.importorskip("requests")

_edit_spec = importlib.util.spec_from_file_location(
    "wordpress_edit_post",
    PUBLISH_DIR / "wordpress-edit-post.py",
)
_edit_mod = importlib.util.module_from_spec(_edit_spec)
_edit_spec.loader.exec_module(_edit_mod)


_LOADERS = [
    pytest.param(_upload_mod.load_env_file, id="upload"),
    pytest.param(_edit_mod.load_env_file, id="edit-post"),
    pytest.param(_media_mod.load_env_file, id="media-upload"),
]


class TestLoadEnvFileQuoteStripping:
    """All three WordPress loaders strip one pair of matching surrounding quotes."""

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_double_quoted_value(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Double-quoted values have quotes removed."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="hello"\n')
        result = loader(env_file)
        assert result["KEY"] == "hello"

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_single_quoted_value(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Single-quoted values have quotes removed."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY='hello'\n")
        result = loader(env_file)
        assert result["KEY"] == "hello"

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_unquoted_value(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Unquoted values pass through unchanged."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=hello\n")
        result = loader(env_file)
        assert result["KEY"] == "hello"

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_mismatched_quotes_kept(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Mismatched quotes are not stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=\"hello'\n")
        result = loader(env_file)
        assert result["KEY"] == "\"hello'"

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_internal_quotes_kept(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Quotes inside the value are preserved."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="say \\"hi\\""\n')
        # After stripping outer quotes: say \"hi\"
        result = loader(env_file)
        assert "say" in result["KEY"]

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_empty_quoted_value(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Empty quoted string becomes empty."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY=""\n')
        result = loader(env_file)
        assert result["KEY"] == ""

    @pytest.mark.parametrize("loader", _LOADERS)
    def test_comment_and_blank_lines_skipped(self, loader, tmp_path: Path) -> None:  # type: ignore[type-arg]
        """Comments and blank lines are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=value\n")
        result = loader(env_file)
        assert result == {"KEY": "value"}
