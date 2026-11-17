"""Tests for wordpress-media-upload.py header sanitization."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PUBLISH_DIR = Path(__file__).parent.parent

_spec = importlib.util.spec_from_file_location(
    "wordpress_media_upload",
    PUBLISH_DIR / "wordpress-media-upload.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_sanitize = _mod._sanitize_header_filename


class TestSanitizeHeaderFilename:
    """Tests for _sanitize_header_filename."""

    def test_plain_filename_unchanged(self) -> None:
        """Normal filenames pass through unmodified."""
        assert _sanitize("photo.jpg") == "photo.jpg"

    def test_strips_double_quote(self) -> None:
        """Double quotes are removed to prevent header breakout."""
        assert _sanitize('file"name.jpg') == "filename.jpg"

    def test_strips_cr_lf(self) -> None:
        """CR and LF are removed to prevent header injection."""
        assert _sanitize("file\r\nname.jpg") == "filename.jpg"

    def test_strips_backslash(self) -> None:
        """Backslashes are removed."""
        assert _sanitize("file\\name.jpg") == "filename.jpg"

    def test_combined_dangerous_chars(self) -> None:
        """All dangerous characters stripped in one pass."""
        assert _sanitize('a"\r\n\\b.png') == "ab.png"

    def test_empty_after_strip(self) -> None:
        """Edge case: everything stripped leaves empty string."""
        assert _sanitize('"\r\n\\') == ""
