"""Tests for wordpress-scraper.py frontmatter and image-size safety."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

PUBLISH_DIR = Path(__file__).parent.parent

requests = pytest.importorskip("requests")

_spec = importlib.util.spec_from_file_location(
    "wordpress_scraper",
    PUBLISH_DIR / "wordpress-scraper.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_frontmatter = _mod.build_frontmatter
download_image = _mod.download_image
MAX_IMAGE_BYTES = _mod.MAX_IMAGE_BYTES


# -- Frontmatter title tests --------------------------------------------------


class TestBuildFrontmatterTitle:
    """Tests for control-character handling in build_frontmatter."""

    def _post(self, title: str) -> dict:
        """Build a minimal post dict with the given title."""
        return {
            "title": title,
            "date": "2024-01-01",
            "slug": "test",
            "author": {"name": "Test"},
            "URL": "https://example.com/test/",
            "categories": {},
            "tags": {},
        }

    def test_newline_in_title_no_extra_key(self) -> None:
        """A title with a newline followed by 'slug:' must not inject a key."""
        post = self._post("Hello\nslug: injected")
        fm = build_frontmatter(post, "https://example.com")
        lines = fm.strip().split("\n")
        # Count how many lines start with 'slug:'
        slug_lines = [ln for ln in lines if ln.startswith("slug:")]
        assert len(slug_lines) == 1, f"Expected 1 slug line, got {len(slug_lines)}: {slug_lines}"

    def test_cr_lf_collapsed(self) -> None:
        """CR and LF inside a title become a space."""
        post = self._post("A\r\nB")
        fm = build_frontmatter(post, "https://example.com")
        assert "A B" in fm

    def test_tab_collapsed(self) -> None:
        """Tab characters collapse to a space."""
        post = self._post("A\tB")
        fm = build_frontmatter(post, "https://example.com")
        assert "A B" in fm

    def test_plain_title_unchanged(self) -> None:
        """A normal title passes through without mangling."""
        post = self._post("Hello World")
        fm = build_frontmatter(post, "https://example.com")
        assert 'title: "Hello World"' in fm


# -- Image size limit tests ----------------------------------------------------


class _FakeResponse:
    """Minimal fake requests.Response for download_image tests."""

    def __init__(self, content: bytes, status_code: int = 200, content_length: str | None = None) -> None:
        self.content = content
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length


class TestDownloadImageSizeLimit:
    """Tests for MAX_IMAGE_BYTES enforcement in download_image."""

    def test_small_image_downloads(self, tmp_path: Path) -> None:
        """An image under the limit is saved."""
        fake_resp = _FakeResponse(b"\x89PNG" + b"\x00" * 100)
        with patch.object(_mod, "_rate_limited_get", return_value=fake_resp):
            result = download_image("https://example.com/small.png", tmp_path)
        assert result is not None
        assert (tmp_path / result).exists()

    def test_large_content_length_skipped(self, tmp_path: Path) -> None:
        """An image whose Content-Length exceeds the limit is skipped."""
        fake_resp = _FakeResponse(b"", content_length=str(MAX_IMAGE_BYTES + 1))
        with patch.object(_mod, "_rate_limited_get", return_value=fake_resp):
            result = download_image("https://example.com/huge.png", tmp_path)
        assert result is None

    def test_large_body_skipped(self, tmp_path: Path) -> None:
        """An image whose body exceeds the limit (no Content-Length) is skipped."""
        big_body = b"\x00" * (MAX_IMAGE_BYTES + 1)
        fake_resp = _FakeResponse(big_body)
        with patch.object(_mod, "_rate_limited_get", return_value=fake_resp):
            result = download_image("https://example.com/huge.png", tmp_path)
        assert result is None
