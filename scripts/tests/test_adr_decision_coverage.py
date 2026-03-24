"""Tests for adr-decision-coverage.py.

Tests decision point extraction, keyword extraction, coverage matching,
output formatting, and edge cases.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Import the module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
adc = importlib.import_module("adr-decision-coverage")
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Sample ADR content
# ---------------------------------------------------------------------------

SAMPLE_ADR = """\
# ADR-093: Parallel Agent Branch Convergence

## Status
Accepted

## Date
2026-03-23

## Context

When dispatching parallel agents, each creates its own feature branch.

## Decision

The orchestrator creates the feature branch **before** dispatching agents.

### Orchestrator Protocol

1. **Before dispatch**: Orchestrator creates and checks out the target branch
2. **In each agent prompt**: Include explicit instruction to work on the branch
3. **After all agents return**: Verify convergence on the target branch
4. **Safety valve**: If conflicts exist, resolve them sequentially

### Why Not Worktrees?

Git worktrees give each agent an isolated copy.

## Consequences

- Single branch for parallel work
"""

SAMPLE_ADR_CODE_REFS = """\
# ADR-091: ADR Intake Queue

## Status
Proposed

## Decision

1. **`scripts/adr-intake.py`** — CLI that scans `adr/` and reports status
2. **SessionStart hook integration** — inject a one-line summary at session start
3. **`/do` routing** — Add "next ADR" as a force-route trigger

## Consequences

- ADRs are surfaced proactively
"""

SAMPLE_ADR_NO_DECISION = """\
# ADR-099: Something

## Status
Proposed

## Context

Some context here.

## Consequences

- Something happens
"""

SAMPLE_ADR_EMPTY_DECISION = """\
# ADR-099: Something

## Status
Proposed

## Decision

This decision has no numbered bold items, just prose.

## Consequences

- Something happens
"""


# ---------------------------------------------------------------------------
# Decision section extraction
# ---------------------------------------------------------------------------


class TestExtractDecisionSection:
    def test_extracts_decision_section(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        assert "Before dispatch" in section
        assert "Safety valve" in section

    def test_excludes_consequences(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        assert "Single branch for parallel work" not in section

    def test_includes_subsections(self) -> None:
        """### subsections within ## Decision should be included."""
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        assert "### Orchestrator Protocol" in section
        assert "### Why Not Worktrees?" in section

    def test_no_decision_section(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR_NO_DECISION)
        assert section is None

    def test_decision_at_end_of_file(self) -> None:
        """Decision section at the end with no following ## heading."""
        content = "# ADR\n\n## Decision\n\n1. **Foo**: bar\n"
        section = adc.extract_decision_section(content)
        assert section is not None
        assert "Foo" in section


# ---------------------------------------------------------------------------
# Decision point parsing
# ---------------------------------------------------------------------------


class TestParseDecisionPoints:
    def test_basic_extraction(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert len(points) == 4

    def test_indexes(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert [p.index for p in points] == [1, 2, 3, 4]

    def test_labels(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert points[0].label == "Before dispatch"
        assert points[3].label == "Safety valve"

    def test_descriptions(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert "Orchestrator creates" in points[0].description

    def test_code_ref_labels(self) -> None:
        """Backtick-enclosed labels should have backticks stripped."""
        section = adc.extract_decision_section(SAMPLE_ADR_CODE_REFS)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert len(points) == 3
        assert points[0].label == "scripts/adr-intake.py"

    def test_em_dash_separator(self) -> None:
        """Decision points using em-dash separator should parse."""
        section = adc.extract_decision_section(SAMPLE_ADR_CODE_REFS)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert "CLI that scans" in points[0].description

    def test_empty_decision_section(self) -> None:
        section = adc.extract_decision_section(SAMPLE_ADR_EMPTY_DECISION)
        assert section is not None
        points = adc.parse_decision_points(section)
        assert points == []


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    def test_basic_keywords(self) -> None:
        keywords = adc.extract_keywords("Orchestrator creates target branch")
        assert "orchestrator" in keywords
        assert "creates" in keywords
        assert "target" in keywords
        assert "branch" in keywords

    def test_stopwords_removed(self) -> None:
        keywords = adc.extract_keywords("Include the explicit instruction to work on the branch")
        assert "the" not in keywords
        assert "to" not in keywords
        assert "on" not in keywords

    def test_short_tokens_removed(self) -> None:
        keywords = adc.extract_keywords("If an agent's PR is bad")
        # "if", "an", "is" are stopwords; "pr" is only 2 chars
        assert "pr" not in keywords
        assert "if" not in keywords

    def test_strips_markdown_bold(self) -> None:
        keywords = adc.extract_keywords("**Before dispatch**: Orchestrator creates")
        # "before" is a stopword so it's filtered; "dispatch" should survive
        assert "dispatch" in keywords
        assert "orchestrator" in keywords
        # No asterisks in keywords
        for kw in keywords:
            assert "*" not in kw

    def test_strips_backticks(self) -> None:
        keywords = adc.extract_keywords("Use `git checkout -b` to create")
        assert "git" in keywords
        assert "checkout" in keywords

    def test_preserves_hyphens_and_underscores(self) -> None:
        keywords = adc.extract_keywords("scope-overlap check_result handler")
        assert "scope-overlap" in keywords
        assert "check_result" in keywords


class TestExtractCodeRefs:
    def test_single_backtick_ref(self) -> None:
        refs = adc.extract_code_refs("Use `git checkout -b` to create")
        assert "git checkout -b" in refs

    def test_multiple_refs(self) -> None:
        refs = adc.extract_code_refs("Run `scripts/foo.py` and `scripts/bar.py`")
        assert len(refs) == 2
        assert "scripts/foo.py" in refs
        assert "scripts/bar.py" in refs

    def test_no_refs(self) -> None:
        refs = adc.extract_code_refs("No code references here")
        assert refs == []


# ---------------------------------------------------------------------------
# Coverage matching
# ---------------------------------------------------------------------------


class TestCheckCoverage:
    def _make_point(self, index: int, label: str, description: str) -> adc.DecisionPoint:
        point = adc.DecisionPoint(index=index, label=label, description=description)
        full_text = f"{label} {description}"
        point.code_refs = adc.extract_code_refs(full_text)
        point.keywords = adc.extract_keywords(full_text)
        return point

    def test_covered_by_keywords(self) -> None:
        point = self._make_point(1, "Before dispatch", "Orchestrator creates and checks out the target branch")
        results = adc.check_coverage([point], "orchestrator creates target branch checkout")
        assert results[0].status == "COVERED"
        assert any("keywords:" in e for e in results[0].evidence)

    def test_covered_by_label(self) -> None:
        point = self._make_point(1, "Before dispatch", "Orchestrator creates target branch")
        results = adc.check_coverage([point], "before dispatch we need to set things up")
        assert results[0].status == "COVERED"
        assert any("label:" in e for e in results[0].evidence)

    def test_covered_by_code_ref(self) -> None:
        point = adc.DecisionPoint(
            index=1,
            label="scripts/adr-intake.py",
            description="CLI that scans `adr/` and reports status",
            code_refs=["adr/"],
            keywords=["scripts", "adr-intake", "cli", "scans", "reports", "status"],
        )
        results = adc.check_coverage([point], "import pathlib\npath = Path('adr/')\n")
        assert results[0].status == "COVERED"
        assert any("code ref:" in e for e in results[0].evidence)

    def test_not_covered(self) -> None:
        point = self._make_point(1, "Safety valve", "Resolve conflicts sequentially")
        results = adc.check_coverage([point], "added a new function for parsing")
        assert results[0].status == "NOT_COVERED"
        assert results[0].evidence == []

    def test_empty_diff(self) -> None:
        point = self._make_point(1, "Before dispatch", "Orchestrator creates target branch")
        results = adc.check_coverage([point], "")
        assert results[0].status == "NOT_COVERED"

    def test_case_insensitive_matching(self) -> None:
        point = self._make_point(1, "Before Dispatch", "Orchestrator creates TARGET branch")
        results = adc.check_coverage([point], "BEFORE DISPATCH is the first step in ORCHESTRATOR")
        assert results[0].status == "COVERED"

    def test_multiple_points_mixed_coverage(self) -> None:
        p1 = self._make_point(1, "Before dispatch", "Orchestrator creates and checks out the target branch")
        p2 = self._make_point(2, "Safety valve", "Resolve conflicts sequentially")
        added = "orchestrator creates target branch checkout"
        results = adc.check_coverage([p1, p2], added)
        assert results[0].status == "COVERED"
        assert results[1].status == "NOT_COVERED"


# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_pass_verdict(self) -> None:
        results = [
            adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"]),
            adc.CoverageResult(index=2, label="B", status="COVERED", evidence=["y"]),
        ]
        report = adc.build_report("adr/test.md", results)
        assert report.verdict == "PASS"
        assert report.percentage == 100
        assert report.covered == 2
        assert report.total == 2

    def test_partial_verdict(self) -> None:
        results = [
            adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"]),
            adc.CoverageResult(index=2, label="B", status="NOT_COVERED"),
        ]
        report = adc.build_report("adr/test.md", results)
        assert report.verdict == "PARTIAL"
        assert report.percentage == 50

    def test_fail_verdict(self) -> None:
        results = [
            adc.CoverageResult(index=1, label="A", status="NOT_COVERED"),
            adc.CoverageResult(index=2, label="B", status="NOT_COVERED"),
        ]
        report = adc.build_report("adr/test.md", results)
        assert report.verdict == "FAIL"
        assert report.percentage == 0
        assert report.covered == 0


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_structure(self) -> None:
        results = [
            adc.CoverageResult(index=1, label="Before dispatch", status="COVERED", evidence=["label: Before dispatch"]),
            adc.CoverageResult(index=2, label="Safety valve", status="NOT_COVERED"),
        ]
        report = adc.build_report("adr/093.md", results)
        output = adc.format_json(report)
        data = json.loads(output)

        assert data["adr"] == "adr/093.md"
        assert len(data["decision_points"]) == 2
        assert data["decision_points"][0]["status"] == "COVERED"
        assert data["decision_points"][1]["status"] == "NOT_COVERED"
        assert data["coverage"]["covered"] == 1
        assert data["coverage"]["total"] == 2
        assert data["coverage"]["percentage"] == 50
        assert data["verdict"] == "PARTIAL"

    def test_valid_json(self) -> None:
        results = [adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"])]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_json(report)
        # Should not raise
        json.loads(output)


class TestFormatHuman:
    def test_contains_header(self) -> None:
        results = [adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"])]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_human(report)
        assert "ADR Decision Coverage: adr/test.md" in output

    def test_contains_covered_tag(self) -> None:
        results = [adc.CoverageResult(index=1, label="Foo", status="COVERED", evidence=["x"])]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_human(report)
        assert "[COVERED]" in output
        assert "1. Foo" in output

    def test_contains_not_covered_tag(self) -> None:
        results = [adc.CoverageResult(index=1, label="Foo", status="NOT_COVERED")]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_human(report)
        assert "[NOT COVERED]" in output

    def test_contains_verdict(self) -> None:
        results = [adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"])]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_human(report)
        assert "Verdict: PASS" in output

    def test_coverage_fraction(self) -> None:
        results = [
            adc.CoverageResult(index=1, label="A", status="COVERED", evidence=["x"]),
            adc.CoverageResult(index=2, label="B", status="NOT_COVERED"),
            adc.CoverageResult(index=3, label="C", status="NOT_COVERED"),
        ]
        report = adc.build_report("adr/test.md", results)
        output = adc.format_human(report)
        assert "Coverage: 1/3 (33%)" in output
        assert "Verdict: PARTIAL" in output


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


class TestExtractAddedLines:
    def test_extracts_added_lines(self) -> None:
        diff = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 unchanged
-removed line
+added line
+another added line
"""
        result = adc.extract_added_lines(diff)
        assert "added line" in result
        assert "another added line" in result
        assert "removed line" not in result

    def test_excludes_diff_headers(self) -> None:
        diff = "+++ b/foo.py\n+real added line\n"
        result = adc.extract_added_lines(diff)
        assert "b/foo.py" not in result
        assert "real added line" in result

    def test_empty_diff(self) -> None:
        result = adc.extract_added_lines("")
        assert result == ""


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_missing_adr_file(self) -> None:
        from unittest.mock import patch

        with patch("sys.argv", [_SCRIPT_NAME, "--adr", "/nonexistent/adr.md"]):
            rc = adc.main()
        assert rc == 2

    def test_no_decision_section(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR_NO_DECISION)
        with patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file)]):
            rc = adc.main()
        assert rc == 2

    def test_no_decision_points(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR_EMPTY_DECISION)
        with patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file)]):
            rc = adc.main()
        assert rc == 2

    def test_json_output_mode(self, tmp_path: Path) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR)

        buf = io.StringIO()
        with (
            patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file), "--json"]),
            patch.object(adc, "get_staged_diff", return_value=""),
            redirect_stdout(buf),
        ):
            rc = adc.main()

        assert rc == 1  # No diff means nothing covered
        data = json.loads(buf.getvalue())
        assert data["verdict"] == "FAIL"
        assert len(data["decision_points"]) == 4

    def test_human_output_mode(self, tmp_path: Path) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR)

        buf = io.StringIO()
        with (
            patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file), "--human"]),
            patch.object(adc, "get_staged_diff", return_value=""),
            redirect_stdout(buf),
        ):
            rc = adc.main()

        assert rc == 1
        output = buf.getvalue()
        assert "Verdict: FAIL" in output

    def test_diff_base_mode(self, tmp_path: Path) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR)

        buf = io.StringIO()
        with (
            patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file), "--diff-base", "main", "--json"]),
            patch.object(
                adc, "get_branch_diff", return_value="+orchestrator creates target branch dispatch"
            ) as mock_diff,
            redirect_stdout(buf),
        ):
            rc = adc.main()

        mock_diff.assert_called_once_with("main")
        data = json.loads(buf.getvalue())
        # At least the first point should be covered
        assert any(dp["status"] == "COVERED" for dp in data["decision_points"])

    def test_pass_exit_code(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        adr_file = tmp_path / "test.md"
        adr_file.write_text(SAMPLE_ADR)

        # Diff that covers all 4 decision points by label and keywords
        fake_diff = (
            "+before dispatch orchestrator creates checks target branch\n"
            "+in each agent prompt include explicit instruction work branch\n"
            "+after all agents return verify convergence target branch\n"
            "+safety valve conflicts resolve sequentially\n"
        )
        with (
            patch("sys.argv", [_SCRIPT_NAME, "--adr", str(adr_file)]),
            patch.object(adc, "get_staged_diff", return_value=fake_diff),
        ):
            rc = adc.main()
        assert rc == 0


# ---------------------------------------------------------------------------
# Enrich decision points
# ---------------------------------------------------------------------------


class TestEnrichDecisionPoints:
    def test_populates_keywords(self) -> None:
        point = adc.DecisionPoint(index=1, label="Before dispatch", description="Orchestrator creates target branch")
        adc.enrich_decision_points([point])
        assert len(point.keywords) > 0
        assert "orchestrator" in point.keywords
        assert "branch" in point.keywords

    def test_populates_code_refs(self) -> None:
        point = adc.DecisionPoint(index=1, label="scripts/adr-intake.py", description="CLI that scans `adr/`")
        adc.enrich_decision_points([point])
        assert "adr/" in point.code_refs


_SCRIPT_NAME = "adr-decision-coverage"
