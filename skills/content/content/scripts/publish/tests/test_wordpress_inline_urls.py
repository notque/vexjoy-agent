"""Tests for URL escaping in wordpress-upload.py and wordpress-edit-post.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PUBLISH_DIR = Path(__file__).parent.parent

# -- Load wordpress-upload.py (no requests dependency at top level) -----------

_upload_spec = importlib.util.spec_from_file_location(
    "wordpress_upload",
    PUBLISH_DIR / "wordpress-upload.py",
)
_upload_mod = importlib.util.module_from_spec(_upload_spec)
_upload_spec.loader.exec_module(_upload_mod)

_apply_inline = _upload_mod._apply_inline_formatting

# -- Load wordpress-edit-post.py (needs requests at import time) --------------

requests = pytest.importorskip("requests")

_edit_spec = importlib.util.spec_from_file_location(
    "wordpress_edit_post",
    PUBLISH_DIR / "wordpress-edit-post.py",
)
_edit_mod = importlib.util.module_from_spec(_edit_spec)
_edit_spec.loader.exec_module(_edit_mod)

_md_to_html = _edit_mod.markdown_to_html


# -- Parametrized test cases --------------------------------------------------

LINK_CASES = [
    pytest.param(
        "[a](https://example.com/x)",
        '<a href="https://example.com/x">a</a>',
        id="plain-link",
    ),
    pytest.param(
        "[a](https://example.com/?x=1&y=2)",
        "x=1&amp;y=2",
        id="query-string-ampersand",
    ),
    pytest.param(
        '[a](https://example.com/" onmouseover="alert(1))',
        None,  # checked specially below
        id="quote-injection",
    ),
    pytest.param(
        "[a](javascript:void(0))",
        None,  # no <a, text kept
        id="script-scheme",
    ),
    pytest.param(
        "[a](/about)",
        '<a href="/about">a</a>',
        id="relative-link",
    ),
    pytest.param(
        "[a](#top)",
        '<a href="#top">a</a>',
        id="anchor-link",
    ),
    pytest.param(
        "[a](mailto:someone@example.com)",
        '<a href="mailto:someone@example.com">a</a>',
        id="mailto-link",
    ),
]

IMAGE_CASES = [
    pytest.param(
        "![alt](data:text/html;base64,AAAA)",
        None,  # no <img, text kept
        id="data-scheme-image",
    ),
    pytest.param(
        '![say "hi"](https://example.com/i.png)',
        'alt="say &quot;hi&quot;"',
        id="alt-with-quote",
    ),
]


# -- Upload script tests (_apply_inline_formatting) --------------------------


class TestUploadInlineFormatting:
    """Tests for _apply_inline_formatting in wordpress-upload.py."""

    @pytest.mark.parametrize("md,expected", LINK_CASES)
    def test_link(self, md: str, expected: str | None) -> None:
        result = _apply_inline(md)
        if md == "[a](javascript:void(0))":
            assert "<a " not in result
            assert "a" in result
        elif md.startswith('[a](https://example.com/" '):
            # quote-injection: exactly one href attribute, injected attr inside it
            assert result.count('href="') == 1
            assert (
                "&quot;" in result or "&#x27;" in result or "onmouseover" not in result.split('href="')[1].split('"')[1]
                if 'href="' in result
                else True
            )
        elif expected is not None:
            assert expected in result

    @pytest.mark.parametrize("md,expected", IMAGE_CASES)
    def test_image(self, md: str, expected: str | None) -> None:
        result = _apply_inline(md)
        if md.startswith("![alt](data:"):
            assert "<img" not in result
            assert "alt" in result
        elif expected is not None:
            assert expected in result


# -- Edit-post script tests (markdown_to_html) -------------------------------


class TestEditPostMarkdownToHtml:
    """Tests for markdown_to_html in wordpress-edit-post.py."""

    @pytest.mark.parametrize("md,expected", LINK_CASES)
    def test_link(self, md: str, expected: str | None) -> None:
        result = _md_to_html(md)
        if md == "[a](javascript:void(0))":
            assert "<a " not in result
            assert "a" in result
        elif md.startswith('[a](https://example.com/" '):
            assert result.count('href="') == 1
        elif expected is not None:
            assert expected in result

    @pytest.mark.parametrize("md,expected", IMAGE_CASES)
    def test_image(self, md: str, expected: str | None) -> None:
        result = _md_to_html(md)
        if md.startswith("![alt](data:"):
            assert "<img" not in result
            assert "alt" in result
        elif expected is not None:
            assert expected in result
