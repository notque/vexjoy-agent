"""Regression tests for explicit quality-gate tool selection."""

from pathlib import Path
from unittest.mock import patch

import pytest
import quality_gate


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    """Reset the process-level registry cache between tests."""
    quality_gate._registry_cache = None
    yield
    quality_gate._registry_cache = None


def test_explicit_filter_does_not_run_builtin_for_skipped_optional_tool(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    builtin_calls: list[str] = []

    monkeypatch.setattr(quality_gate, "check_tool_available", lambda _cmd: False)
    monkeypatch.setattr(
        quality_gate,
        "_run_builtin_checks",
        lambda language, _files: builtin_calls.append(language),
    )

    report = quality_gate.run_quality_gate(
        project_path=tmp_path,
        files=[source],
        languages=["python"],
        include_patterns=False,
        tools_filter=["security"],
    )

    assert [(result.tool_name, result.skipped) for result in report.tool_results] == [("security", True)]
    assert builtin_calls == []


def test_empty_filter_runs_no_tools_or_builtin_fallback(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    tool_calls: list[str] = []
    builtin_calls: list[str] = []

    monkeypatch.setattr(
        quality_gate,
        "run_tool",
        lambda name, *_args, **_kwargs: tool_calls.append(name),
    )
    monkeypatch.setattr(
        quality_gate,
        "_run_builtin_checks",
        lambda language, _files: builtin_calls.append(language),
    )

    report = quality_gate.run_quality_gate(
        project_path=tmp_path,
        files=[source],
        languages=["python"],
        include_patterns=False,
        tools_filter=[],
    )

    assert report.tool_results == []
    assert tool_calls == []
    assert builtin_calls == []


def test_unfiltered_gate_keeps_builtin_fallback(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    builtin_calls: list[str] = []

    monkeypatch.setattr(
        quality_gate,
        "run_tool",
        lambda name, language, *_args, **_kwargs: quality_gate.ToolResult(
            tool_name=name,
            language=language,
            passed=True,
            output="",
            skipped=True,
            skip_reason="not installed",
        ),
    )
    monkeypatch.setattr(
        quality_gate,
        "_run_builtin_checks",
        lambda language, _files: (
            builtin_calls.append(language)
            or quality_gate.ToolResult(
                tool_name="builtin",
                language=language,
                passed=True,
                output="no issues",
            )
        ),
    )

    report = quality_gate.run_quality_gate(
        project_path=tmp_path,
        files=[source],
        languages=["python"],
        include_patterns=False,
    )

    assert builtin_calls == ["python"]
    assert any(result.tool_name == "builtin" for result in report.tool_results)


def test_load_registry_reads_file_once(tmp_path: Path, monkeypatch):
    """Two calls to load_registry parse the JSON file only once."""
    registry_file = tmp_path / "language_registry.json"
    registry_file.write_text('{"languages": {}, "fallback": {"tools": {}}, "global_patterns": {}}')
    monkeypatch.setattr(quality_gate, "REGISTRY_PATH", registry_file)

    read_count = 0
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        nonlocal read_count
        if self == registry_file:
            read_count += 1
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", counting_read_text):
        result1 = quality_gate.load_registry()
        result2 = quality_gate.load_registry()

    assert read_count == 1
    assert result1 is result2


def test_check_tool_available_empty_string_returns_false():
    assert quality_gate.check_tool_available("") is False
    assert quality_gate.check_tool_available("   ") is False


def test_summary_counts_exclude_skipped_tools_from_passed(tmp_path: Path, monkeypatch):
    """Skipped tools must not be counted in passed_tools or drive failed_tools negative."""
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    outcomes = {
        "lint": quality_gate.ToolResult(tool_name="lint", language="python", passed=False, output="E001"),
        "format": quality_gate.ToolResult(
            tool_name="format", language="python", passed=True, output="", skipped=True, skip_reason="not installed"
        ),
        "typecheck": quality_gate.ToolResult(
            tool_name="typecheck", language="python", passed=True, output="", skipped=True, skip_reason="not installed"
        ),
        "security": quality_gate.ToolResult(tool_name="security", language="python", passed=True, output="ok"),
    }
    monkeypatch.setattr(
        quality_gate,
        "run_tool",
        lambda name, *_args, **_kwargs: outcomes[name],
    )

    report = quality_gate.run_quality_gate(
        project_path=tmp_path,
        files=[source],
        languages=["python"],
        include_patterns=False,
    )

    assert report.passed is False
    assert "Quality gate failed: 1 tool(s) reported issues" in report.summary


def test_summary_counts_when_only_passed_and_skipped(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    outcomes = {
        "lint": quality_gate.ToolResult(tool_name="lint", language="python", passed=True, output="ok"),
        "format": quality_gate.ToolResult(
            tool_name="format", language="python", passed=True, output="", skipped=True, skip_reason="not installed"
        ),
    }
    monkeypatch.setattr(
        quality_gate,
        "run_tool",
        lambda name, *_args, **_kwargs: outcomes[name],
    )

    report = quality_gate.run_quality_gate(
        project_path=tmp_path,
        files=[source],
        languages=["python"],
        include_patterns=False,
        tools_filter=["lint", "format"],
    )

    assert report.passed is True
    assert report.summary == "Quality gate passed: 1/2 tools OK (1 skipped)"


def test_run_tool_on_windows_uses_argv_without_shell_or_single_quotes(tmp_path: Path, monkeypatch):
    """On Windows, run_tool passes an argv list with shell=False instead of POSIX shlex.quote."""
    spaced = tmp_path / "my dir" / "sample file.py"
    spaced.parent.mkdir()
    spaced.write_text("x = 1\n", encoding="utf-8")

    captured: dict = {}

    class _Done:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["shell"] = kwargs.get("shell")
        return _Done()

    monkeypatch.setattr(quality_gate.shutil, "which", lambda _name: None)
    monkeypatch.setattr(quality_gate.subprocess, "run", fake_run)

    # Scope os.name patch tightly so pytest/pathlib teardown sees the real platform.
    with patch.object(quality_gate.os, "name", "nt"):
        result = quality_gate.run_tool(
            "lint",
            {"cmd": "ruff check {files}", "optional": False},
            [spaced],
            "python",
        )

    assert result.passed is True
    assert captured["shell"] is False
    assert captured["cmd"] == ["ruff", "check", str(spaced)]
    assert all(not arg.startswith("'") for arg in captured["cmd"])
