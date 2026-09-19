"""Tests for generate-filename.py — deterministic filename generator."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "generate-filename.py")

# --- Import module directly for unit tests ---
sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

filename_mod = import_module("generate-filename")
generate_filename = filename_mod.generate_filename


class TestGenerateFilenameDirect:
    """Unit tests calling generate_filename() directly."""

    def test_basic_request(self) -> None:
        result = generate_filename("explore 3 approaches to rate limiting")
        # "explore" is verb prefix, "3" is numeric (not [a-z]+), "to" is stop word
        assert result == "approaches-rate-limiting.html"

    def test_stop_words_removed(self) -> None:
        result = generate_filename("the quick brown fox")
        assert result == "quick-brown-fox.html"

    def test_verb_prefixes_removed(self) -> None:
        result = generate_filename("create a dashboard widget")
        assert result == "dashboard-widget.html"

    def test_max_4_words(self) -> None:
        result = generate_filename("foo bar baz qux quux corge")
        assert result == "foo-bar-baz-qux.html"

    def test_empty_after_filtering_no_shape(self) -> None:
        result = generate_filename("explore the")
        assert result == "artifact.html"

    def test_empty_after_filtering_with_shape(self) -> None:
        result = generate_filename("explore the", shape="spec")
        assert result == "spec-artifact.html"

    def test_shape_prepended_when_not_in_words(self) -> None:
        result = generate_filename("rate limiting strategies", shape="spec")
        assert result == "spec-rate-limiting-strategies.html"

    def test_shape_not_prepended_when_already_present(self) -> None:
        # "data" appears as content word and is a part of "data-viz"
        result = generate_filename("data pipeline performance", shape="data-viz")
        assert result == "data-pipeline-performance.html"

    def test_case_insensitive(self) -> None:
        result = generate_filename("EXPLORE Rate LIMITING")
        assert result == "rate-limiting.html"

    def test_numbers_stripped(self) -> None:
        # re.findall(r"[a-z]+", ...) only matches letters
        result = generate_filename("explore 3 approaches")
        assert result == "approaches.html"

    def test_special_chars_ignored(self) -> None:
        result = generate_filename("auth: OAuth2 vs JWT!")
        assert result == "auth-oauth-vs-jwt.html"

    def test_deterministic_same_input_same_output(self) -> None:
        results = [generate_filename("compare auth approaches") for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_all_stop_words(self) -> None:
        result = generate_filename("the a an to for of in on at by")
        assert result == "artifact.html"

    def test_shape_code_review_prepended(self) -> None:
        result = generate_filename("auth module refactor", shape="code-review")
        assert result.startswith("code-review-")
        assert result.endswith(".html")


@pytest.mark.slow
class TestCLIInterface:
    """Integration tests via subprocess."""

    def test_cli_basic(self) -> None:
        cmd = [sys.executable, SCRIPT, "--request", "explore 3 approaches to rate limiting"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert proc.stdout.strip().endswith(".html")

    def test_cli_with_shape(self) -> None:
        cmd = [sys.executable, SCRIPT, "--request", "rate limiting strategies", "--shape", "spec"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        assert proc.stdout.strip().startswith("spec-")

    def test_cli_invalid_shape_exits_1(self) -> None:
        cmd = [sys.executable, SCRIPT, "--request", "test", "--shape", "banana"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1

    def test_cli_output_has_no_extra_whitespace(self) -> None:
        cmd = [sys.executable, SCRIPT, "--request", "build a dashboard"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0
        output = proc.stdout.strip()
        assert " " not in output
        assert output.endswith(".html")
