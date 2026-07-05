"""Tests for user_input — the critical test targets missing HTML escaping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.user_input import sanitize_for_display


def test_strips_script_tags():
    assert "<script>" not in sanitize_for_display('<script>alert("xss")</script>hello')


def test_escapes_angle_brackets():
    """Raw < and > must be entity-escaped for safe display."""
    result = sanitize_for_display("1 < 2 and 3 > 1")
    assert "<" not in result or "&lt;" in result


def test_escapes_ampersand():
    result = sanitize_for_display("Tom & Jerry")
    assert "&" not in result or "&amp;" in result


def test_preserves_plain_text():
    assert sanitize_for_display("hello world") == "hello world"
