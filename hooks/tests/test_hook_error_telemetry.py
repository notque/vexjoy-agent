#!/usr/bin/env python3
"""Tests for isolated hook-error telemetry."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import hook_utils
from hook_utils import hook_error


def test_hook_error_uses_test_fixture_path(monkeypatch):
    path = Path(os.environ["CLAUDE_HOOK_ERRORS_PATH"])

    hook_error("fixture-test", RuntimeError("boom"))

    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["hook"] == "fixture-test"


def test_hook_error_resolves_override_at_call_time(tmp_path, monkeypatch):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(first))
    hook_error("first", RuntimeError("one"))

    monkeypatch.setenv("CLAUDE_HOOK_ERRORS_PATH", str(second))
    hook_error("second", RuntimeError("two"))

    assert json.loads(first.read_text(encoding="utf-8"))["hook"] == "first"
    assert json.loads(second.read_text(encoding="utf-8"))["hook"] == "second"


def test_hook_error_fixture_isolates_default_when_environment_is_cleared(monkeypatch):
    isolated_default = hook_utils._DEFAULT_HOOK_ERRORS_PATH
    monkeypatch.delenv("CLAUDE_HOOK_ERRORS_PATH")

    hook_error("fallback", RuntimeError("three"))

    assert json.loads(isolated_default.read_text(encoding="utf-8"))["hook"] == "fallback"
