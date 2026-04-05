"""Tests for scripts/prompt-length-variants.py.

Covers full/half/quarter variant generation, token reduction statistics,
stderr stats output, and graceful handling of missing skills.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module and script path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "prompt-length-variants.py"


def _load_module():
    """Load prompt-length-variants.py as a Python module.

    Returns:
        Loaded module object.
    """
    spec = importlib.util.spec_from_file_location("prompt_length_variants", str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A SKILL.md with all the structural elements the variants target:
# - Fenced code blocks after Example: / EXAMPLE: labels
# - Markdown tables
# - Anti-Pattern sections
# - Multiple headings with substantial multi-paragraph content
#
# Design intent:
#   full > half > quarter (by token count)
#   half removes: example blocks + anti-pattern sections + collapses tables
#   quarter keeps: headings + first paragraph per section only
#
# To ensure quarter < half, each section has a large second+ paragraph that
# quarter drops but half keeps.  Anti-pattern sections are small so their
# removal by half does not outweigh the body-text cuts of quarter.
_SAMPLE_SKILL = """\
# Overview

This skill does important things for the pipeline.

This second paragraph of the overview provides extended context that is useful
but not strictly required for a minimal understanding of what the skill does.
It explains background history, rationale, and design philosophy in detail.

## Phase 1: Preparation

Prepare the inputs for processing.

This second paragraph of Phase 1 goes into extensive detail about preparation
steps, validation rules, environment checks, dependency resolution, and the
exact sequence of operations that must occur before execution can begin safely.
There are many lines of explanatory prose here that add bulk to the section.
Each sentence adds more words so the second-paragraph count is substantial.

EXAMPLE:
```python
data = load()
process(data)
```

## Phase 2: Execution

Execute the core logic here.
Output: A transformed result.
Format: JSON

This second paragraph of Phase 2 covers advanced execution scenarios,
error recovery strategies, retry logic, timeout handling, and how to
interpret intermediate state during a long-running execution.  It is
deliberately verbose to ensure the section contributes meaningful token
mass beyond its first paragraph.

Example:
```bash
run --input data.json
```

## Anti-Pattern Section

### Anti-Pattern: Do Not Do This

Never do the bad thing.
Always do the good thing instead.

## Phase 3: Output

Produce the final artifact.
Format: markdown

This second paragraph of Phase 3 elaborates on output formats, encoding
requirements, schema validation, downstream consumer expectations, and how
to handle partial outputs when processing terminates early.  Again, it is
intentionally long to add token bulk that the quarter variant will strip.

| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Alpha    | Beta     | Gamma    |

## Anti-patterns and Pitfalls

Avoid these common mistakes.
They will cause failures in production.

## Final Notes

These are the final notes summarising everything above.

This second paragraph of Final Notes restates all key points from every
previous section, providing a comprehensive summary that is useful for
quick reference but entirely redundant for someone who read the full skill.
It adds many tokens to ensure half is meaningfully larger than quarter.
"""


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with a test skill.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        Path to the skills base directory.
    """
    skills_base = tmp_path / "skills"
    skill_path = skills_base / "test-skill"
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text(_SAMPLE_SKILL, encoding="utf-8")
    return skills_base


def _run(skill_dir: Path, variant: str, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run prompt-length-variants.py via subprocess.

    Args:
        skill_dir: Path to the skills base directory.
        variant: Variant to generate (full/half/quarter).
        extra: Additional CLI arguments.

    Returns:
        CompletedProcess with captured stdout/stderr.
    """
    cmd = [
        sys.executable,
        str(_SCRIPT),
        "--skill",
        "test-skill",
        "--variant",
        variant,
        "--skills-dir",
        str(skill_dir),
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15)


# ---------------------------------------------------------------------------
# Tests: full variant
# ---------------------------------------------------------------------------


class TestFullVariant:
    """--variant full outputs the original SKILL.md unchanged."""

    def test_full_output_matches_original(self, skill_dir: Path):
        """Full variant stdout exactly matches the original SKILL.md content.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "full")
        assert result.returncode == 0
        # stdout includes the original text (may have trailing newline differences)
        assert result.stdout.strip() == _SAMPLE_SKILL.strip()

    def test_full_reduction_is_zero(self, skill_dir: Path):
        """Full variant reports 0.0% reduction in stderr stats.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "full")
        assert "Reduction: 0.0%" in result.stderr

    def test_full_stats_in_stderr(self, skill_dir: Path):
        """Full variant emits token stats line to stderr.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "full")
        assert "Variant: full" in result.stderr
        assert "tokens" in result.stderr


# ---------------------------------------------------------------------------
# Tests: half variant
# ---------------------------------------------------------------------------


class TestHalfVariant:
    """--variant half strips examples, collapses tables, removes anti-patterns."""

    def test_half_removes_example_blocks(self, skill_dir: Path):
        """Half variant output does not contain the example code fences.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "half")
        assert result.returncode == 0
        # The example code body should be gone
        assert "load()" not in result.stdout
        assert "run --input data.json" not in result.stdout

    def test_half_collapses_tables(self, skill_dir: Path):
        """Half variant converts | table rows | to inline lists.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "half")
        # Original table row format should be replaced
        assert "| Value 1  | Value 2  | Value 3  |" not in result.stdout
        # Collapsed format: key: value
        assert "Column A: Value 1" in result.stdout

    def test_half_removes_antipattern_sections(self, skill_dir: Path):
        """Half variant removes headings containing 'Anti-Pattern'.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "half")
        assert "Never do the bad thing" not in result.stdout
        assert "Avoid these common mistakes" not in result.stdout

    def test_half_retains_core_phases(self, skill_dir: Path):
        """Half variant keeps Phase headings and their content.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "half")
        assert "Phase 1: Preparation" in result.stdout
        assert "Phase 2: Execution" in result.stdout
        assert "Phase 3: Output" in result.stdout

    def test_half_is_shorter_than_full(self, skill_dir: Path):
        """Half variant token count is less than full.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        full_result = _run(skill_dir, "full")
        half_result = _run(skill_dir, "half")

        full_tokens = len(full_result.stdout.split())
        half_tokens = len(half_result.stdout.split())
        assert half_tokens < full_tokens

    def test_half_reduction_positive(self, skill_dir: Path):
        """Half variant reports a positive reduction percentage.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "half")
        # Extract reduction from stderr line "Reduction: X%"
        import re

        match = re.search(r"Reduction:\s+([\d.]+)%", result.stderr)
        assert match is not None
        assert float(match.group(1)) > 0


# ---------------------------------------------------------------------------
# Tests: quarter variant
# ---------------------------------------------------------------------------


class TestQuarterVariant:
    """--variant quarter keeps only headings and first paragraphs."""

    def test_quarter_keeps_headings(self, skill_dir: Path):
        """Quarter variant output contains all original headings.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "quarter")
        assert result.returncode == 0
        assert "# Overview" in result.stdout
        assert "## Phase 1: Preparation" in result.stdout
        assert "## Phase 2: Execution" in result.stdout

    def test_quarter_removes_code_blocks(self, skill_dir: Path):
        """Quarter variant drops example code blocks.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "quarter")
        assert "load()" not in result.stdout
        assert "run --input" not in result.stdout

    def test_quarter_keeps_output_format_lines(self, skill_dir: Path):
        """Quarter variant keeps lines with Output: or Format: markers.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        result = _run(skill_dir, "quarter")
        assert "Output:" in result.stdout or "Format:" in result.stdout

    def test_quarter_is_shorter_than_half(self, skill_dir: Path):
        """Quarter variant token count is less than half.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        half_result = _run(skill_dir, "half")
        quarter_result = _run(skill_dir, "quarter")

        half_tokens = len(half_result.stdout.split())
        quarter_tokens = len(quarter_result.stdout.split())
        assert quarter_tokens < half_tokens

    def test_quarter_reduction_greater_than_half(self, skill_dir: Path):
        """Quarter variant has higher reduction% than half variant.

        Args:
            skill_dir: Fixture providing skills directory.
        """
        import re

        half_result = _run(skill_dir, "half")
        quarter_result = _run(skill_dir, "quarter")

        def extract_reduction(stderr: str) -> float:
            match = re.search(r"Reduction:\s+([\d.]+)%", stderr)
            assert match is not None, f"No reduction% in stderr: {stderr!r}"
            return float(match.group(1))

        half_reduction = extract_reduction(half_result.stderr)
        quarter_reduction = extract_reduction(quarter_result.stderr)
        assert quarter_reduction > half_reduction


# ---------------------------------------------------------------------------
# Tests: stderr stats format
# ---------------------------------------------------------------------------


class TestStderrStats:
    """Verify stats line format on stderr."""

    @pytest.mark.parametrize("variant", ["full", "half", "quarter"])
    def test_stats_line_format(self, skill_dir: Path, variant: str):
        """Stderr contains 'Variant: X | Original: N tokens | Variant: M tokens | Reduction: P%'.

        Args:
            skill_dir: Fixture providing skills directory.
            variant: Variant to test.
        """
        result = _run(skill_dir, variant)
        assert result.returncode == 0
        stderr = result.stderr
        assert f"Variant: {variant}" in stderr
        assert "Original:" in stderr
        assert "tokens" in stderr
        assert "Reduction:" in stderr

    @pytest.mark.parametrize("variant", ["full", "half", "quarter"])
    def test_stats_token_counts_are_integers(self, skill_dir: Path, variant: str):
        """Token counts in stderr are valid integers.

        Args:
            skill_dir: Fixture providing skills directory.
            variant: Variant to test.
        """
        import re

        result = _run(skill_dir, variant)
        # Extract "Original: N tokens"
        orig_match = re.search(r"Original:\s+(\d+)\s+tokens", result.stderr)
        var_match = re.search(r"Variant:\s+\S+\s+\|\s+Original:\s+\d+.*Variant:\s+(\d+)\s+tokens", result.stderr)
        assert orig_match is not None, f"No original token count in: {result.stderr!r}"
        assert int(orig_match.group(1)) > 0


# ---------------------------------------------------------------------------
# Tests: missing skill
# ---------------------------------------------------------------------------


class TestMissingSkill:
    """Graceful handling when skill does not exist."""

    def test_missing_skill_exits_nonzero(self, tmp_path: Path):
        """Script exits with code 1 when skill directory does not exist.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        skills_base = tmp_path / "skills"
        skills_base.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--skill",
                "nonexistent-skill",
                "--variant",
                "full",
                "--skills-dir",
                str(skills_base),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 1

    def test_missing_skill_error_message(self, tmp_path: Path):
        """Script prints 'not found' error for missing skill.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        skills_base = tmp_path / "skills"
        skills_base.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--skill",
                "nonexistent-skill",
                "--variant",
                "full",
                "--skills-dir",
                str(skills_base),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Unit tests: internal transformation functions
# ---------------------------------------------------------------------------


class TestStripExampleBlocks:
    """Unit tests for _strip_example_blocks."""

    def test_removes_example_code_block(self):
        """Example: label + fenced block is removed."""
        text = "Before\n\nExample:\n```\ncode here\n```\n\nAfter\n"
        result = _mod._strip_example_blocks(text)
        assert "code here" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_uppercase_example(self):
        """EXAMPLE: label (uppercase) also triggers removal."""
        text = "Before\n\nEXAMPLE:\n```python\nx = 1\n```\n\nAfter\n"
        result = _mod._strip_example_blocks(text)
        assert "x = 1" not in result

    def test_preserves_code_blocks_without_example_label(self):
        """Fenced code blocks NOT preceded by Example: are preserved."""
        text = "Before\n\n```python\nkeep_this()\n```\n\nAfter\n"
        result = _mod._strip_example_blocks(text)
        assert "keep_this()" in result


class TestCollapseTables:
    """Unit tests for _collapse_tables."""

    def test_simple_table_collapsed(self):
        """Two-column table is collapsed to inline list."""
        text = "| Name | Value |\n|------|-------|\n| foo  | bar   |\n"
        result = _mod._collapse_tables(text)
        assert "Name: foo" in result
        assert "Value: bar" in result

    def test_separator_row_not_in_output(self):
        """Separator row (---|---) does not appear in collapsed output."""
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        result = _mod._collapse_tables(text)
        assert "---" not in result

    def test_non_table_lines_preserved(self):
        """Lines not part of a table are passed through unchanged."""
        text = "Not a table line\n| A | B |\n|---|---|\n| 1 | 2 |\nAlso preserved\n"
        result = _mod._collapse_tables(text)
        assert "Not a table line" in result
        assert "Also preserved" in result


class TestRemoveAntipatternSections:
    """Unit tests for _remove_antipattern_sections."""

    def test_antipattern_heading_and_body_removed(self):
        """Section with 'Anti-Pattern' in heading is removed including body."""
        text = (
            "## Good Section\n\nGood content.\n\n## Anti-Pattern: Bad\n\nBad content.\n\n## After\n\nAfter content.\n"
        )
        result = _mod._remove_antipattern_sections(text)
        assert "Bad content" not in result
        assert "Good content" in result
        assert "After content" in result

    def test_case_insensitive_antipattern(self):
        """'anti-pattern' (lowercase) also triggers removal."""
        text = "## anti-pattern example\n\nRemove me.\n\n## Keep\n\nKeep me.\n"
        result = _mod._remove_antipattern_sections(text)
        assert "Remove me" not in result
        assert "Keep me" in result


class TestGenerateQuarter:
    """Unit tests for _generate_quarter."""

    def test_keeps_headings(self):
        """All headings are preserved in quarter variant."""
        text = "# Title\n\nIntro paragraph.\n\nExtra line.\n\n## Section\n\nFirst paragraph.\n\nExtra.\n"
        result = _mod._generate_quarter(text)
        assert "# Title" in result
        assert "## Section" in result

    def test_keeps_first_paragraph(self):
        """First paragraph after heading is kept."""
        text = "## Section\n\nFirst paragraph line.\n\nSecond paragraph line.\n"
        result = _mod._generate_quarter(text)
        assert "First paragraph line." in result

    def test_drops_second_paragraph(self):
        """Lines after the first blank after a heading are dropped."""
        text = "## Section\n\nFirst line.\n\nDropped line.\n"
        result = _mod._generate_quarter(text)
        assert "Dropped line" not in result

    def test_always_keeps_output_lines(self):
        """Lines containing 'Output:' are always kept regardless of position."""
        text = "## Section\n\nFirst.\n\nSecond para.\nOutput: JSON format\n"
        result = _mod._generate_quarter(text)
        assert "Output: JSON format" in result
