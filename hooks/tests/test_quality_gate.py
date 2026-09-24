"""Regression tests for explicit quality-gate tool selection."""

from pathlib import Path

import quality_gate


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
