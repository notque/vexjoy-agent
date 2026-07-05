"""Tests for config_parser — the critical test targets values containing '='."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config_parser import parse_config


def test_simple_pair():
    assert parse_config("host=localhost") == {"host": "localhost"}


def test_value_with_equals():
    """Values like 'postgres://host?opt=1' contain '=' and must be preserved."""
    result = parse_config("db_url=postgres://host?opt=1")
    assert result["db_url"] == "postgres://host?opt=1"


def test_comments_and_blanks():
    text = "# comment\n\nkey=val\n"
    assert parse_config(text) == {"key": "val"}


def test_whitespace_trimming():
    assert parse_config("  key  =  value  ") == {"key": "value"}
