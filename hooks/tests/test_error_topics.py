#!/usr/bin/env python3
"""Golden-fixture tests for extended error-topic classification.

The live learning DB shows topic=unknown dominating category=error rows
(4142 unknown vs ~1300 classified). The dominant unknown shapes are CLI
usage errors, test failures, lint output, command-not-found, JSON parse,
git conflicts, and HTTP/network errors. ``classify_error_topic`` maps
those to concrete topics; everything else still falls back to "unknown".
The base ``classify_error`` taxonomy keeps first claim (no reclassification
of already-known shapes).

Run with: python3 -m pytest hooks/tests/test_error_topics.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from error_topics import classify_error_topic

GOLDENS = [
    # base taxonomy keeps first claim
    ("Error: no such file or directory: foo.txt", "missing_file"),
    ("bash: permission denied", "permissions"),
    ("operation timed out after 30s", "timeout"),
    # extended: command_not_found
    ("bash: rgg: command not found", "command_not_found"),
    ("zsh: command not found: pnmp", "command_not_found"),
    # extended: json_parse
    ("json.decoder.JSONDecodeError: Expecting value: line 1 column 1", "json_parse"),
    ("failed to parse JSON response", "json_parse"),
    ("Unexpected end of JSON input", "json_parse"),
    # extended: git_conflict
    ("CONFLICT (content): Merge conflict in app.py", "git_conflict"),
    ("Automatic merge failed; fix conflicts and then commit", "git_conflict"),
    ("error: you need to resolve your current index first; app.py: needs merge", "git_conflict"),
    # extended: usage_error
    ("usage: validate.py [-h] [--json]\nvalidate.py: error: unrecognized arguments: --all", "usage_error"),
    ("error: unrecognized arguments: --frobnicate", "usage_error"),
    ("error: the following arguments are required: --agent", "usage_error"),
    # extended: lint_error
    ("ruff check failed: 5 errors found", "lint_error"),
    ("Would reformat: hooks/error-learner.py", "lint_error"),
    ("4 fixable with the `--fix` option", "lint_error"),
    # extended: test_failure
    ("AssertionError: expected 3 got 4", "test_failure"),
    ("=== FAILURES ===\ntest_x failed", "test_failure"),
    ("2 failed, 130 passed in 5.21s", "test_failure"),
    # extended: network
    ("HTTP Error 404: Not Found", "network"),
    ("curl: (6) Could not resolve host: example.com", "network"),
    ("Connection reset by peer", "network"),
    # fallback stays unknown
    ("something inexplicable happened", "unknown"),
    ("", "unknown"),
]


@pytest.mark.parametrize(("message", "topic"), GOLDENS)
def test_classify_error_topic(message, topic):
    assert classify_error_topic(message) == topic, message
