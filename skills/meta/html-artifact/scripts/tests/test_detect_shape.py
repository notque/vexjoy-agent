"""Tests for detect-shape.py — deterministic shape classifier."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "detect-shape.py")


def run_detect(request: str, compact: bool = False) -> dict:
    """Run detect-shape.py and return parsed JSON."""
    cmd = [sys.executable, SCRIPT, "--request", request]
    if compact:
        cmd.append("--json-compact")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    return json.loads(result.stdout)


# --- Add the script's parent to sys.path so we can import directly ---
sys.path.insert(0, str(Path(__file__).parent.parent))
from importlib import import_module

# import via importlib because filename has a hyphen
detect_shape = import_module("detect-shape")
classify_request = detect_shape.classify_request


class TestClassifyRequestDirect:
    """Unit tests calling classify_request() directly."""

    def test_empty_request_returns_report_low(self) -> None:
        result = classify_request("")
        assert result["shape"] == "report"
        assert result["confidence"] == "low"
        assert result["signals"] == []

    def test_whitespace_only_returns_report_low(self) -> None:
        result = classify_request("   ")
        assert result["shape"] == "report"
        assert result["confidence"] == "low"

    def test_no_signals_returns_report_low(self) -> None:
        result = classify_request("hello world foo bar")
        assert result["shape"] == "report"
        assert result["confidence"] == "low"

    def test_spec_high_confidence(self) -> None:
        result = classify_request("explore 3 auth approaches and compare tradeoffs")
        assert result["shape"] == "spec"
        assert result["confidence"] == "high"
        assert "explore" in result["signals"]
        assert "compare" in result["signals"]
        assert "tradeoff" in [s.rstrip("s") for s in result["signals"]] or "tradeoff" in result["signals"]

    def test_code_review_signals(self) -> None:
        result = classify_request("review PR #42 and annotate the diff")
        assert result["shape"] == "code-review"
        assert result["confidence"] == "high"

    def test_prototype_signals(self) -> None:
        result = classify_request("build a prototype with slider controls and animation")
        assert result["shape"] == "prototype"
        assert result["confidence"] == "high"

    def test_report_signals(self) -> None:
        result = classify_request("summarize the weekly incident timeline")
        assert result["shape"] == "report"
        assert result["confidence"] == "high"

    def test_editor_signals(self) -> None:
        result = classify_request("triage and prioritize the backlog, flag urgent items")
        assert result["shape"] == "editor"
        assert result["confidence"] == "high"

    def test_data_viz_signals(self) -> None:
        result = classify_request("visualize the dashboard metrics and chart the trend")
        assert result["shape"] == "data-viz"
        assert result["confidence"] == "high"

    def test_medium_confidence(self) -> None:
        # Single primary signal = 2 points = medium
        result = classify_request("let's brainstorm")
        assert result["shape"] == "spec"
        assert result["confidence"] == "medium"

    def test_low_confidence_single_secondary(self) -> None:
        # Single secondary signal = 1 point = low
        result = classify_request("show me the pros and cons")
        assert result["shape"] == "spec"
        assert result["confidence"] == "low"

    def test_tie_breaking_editor_wins_over_spec(self) -> None:
        # Both editor and spec get same score -> editor wins (higher priority)
        result = classify_request("plan to reorder")
        assert result["shape"] == "editor"

    def test_tie_breaking_spec_wins_over_report(self) -> None:
        result = classify_request("explore the status")
        assert result["shape"] == "spec"

    def test_case_insensitive(self) -> None:
        result = classify_request("EXPLORE APPROACHES")
        assert result["shape"] == "spec"

    def test_markdown_mention_still_classifies(self) -> None:
        result = classify_request("explore approaches, output as markdown")
        assert result["shape"] == "spec"

    def test_deterministic_same_input_same_output(self) -> None:
        for _ in range(10):
            r = classify_request("compare and explore tradeoffs")
            assert r["shape"] == "spec"
            assert r["confidence"] == "high"

    def test_secondary_signals_contribute(self) -> None:
        result = classify_request("write an implementation plan with design options")
        assert result["shape"] == "spec"
        # "plan" = 2pts primary + "implementation plan" = 1pt + "design options" = 1pt = 4 -> high
        assert result["confidence"] == "high"


@pytest.mark.slow
class TestCLIInterface:
    """Integration tests via subprocess."""

    def test_cli_basic(self) -> None:
        result = run_detect("explore approaches")
        assert result["shape"] == "spec"

    def test_cli_compact_json(self) -> None:
        cmd = [sys.executable, SCRIPT, "--request", "explore approaches", "--json-compact"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = proc.stdout.strip()
        # Compact JSON has no newlines inside the object
        assert "\n" not in output.rstrip("\n")
        parsed = json.loads(output)
        assert parsed["shape"] == "spec"

    def test_cli_empty_request(self) -> None:
        result = run_detect("")
        assert result["shape"] == "report"
        assert result["confidence"] == "low"
