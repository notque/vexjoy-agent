"""Tests for scripts/check-whitespace.py."""

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the hyphen-named module via importlib
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parent.parent / "check-whitespace.py"
_spec = importlib.util.spec_from_file_location("check_whitespace", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
sys.modules["check_whitespace"] = _mod

Violation = _mod.Violation
check_file = _mod.check_file
fix_file = _mod.fix_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write(tmp_path: Path, name: str, content: str) -> Path:
    """Write content to a named file inside tmp_path and return the Path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# check_file — consecutive blank lines
# ---------------------------------------------------------------------------


def test_check_consecutive_blank_lines(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        "a.md",
        textwrap.dedent(
            """\
            # Heading

            First paragraph.


            Second paragraph after two blank lines.
            """
        ),
    )
    violations = check_file(p)
    kinds = [v.kind for v in violations]
    assert "consecutive_blank_lines" in kinds


def test_check_single_blank_line_is_clean(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        "clean.md",
        textwrap.dedent(
            """\
            # Heading

            Paragraph one.

            Paragraph two.
            """
        ),
    )
    violations = check_file(p)
    assert violations == []


def test_check_triple_blank_lines_reports_line_number(tmp_path: Path) -> None:
    content = "line one\n\n\n\nline after three blanks\n"
    p = write(tmp_path, "b.md", content)
    violations = check_file(p)
    assert len(violations) == 1
    v = violations[0]
    assert v.kind == "consecutive_blank_lines"
    assert v.line_no == 2  # first blank line is line 2
    assert "3" in v.detail  # 3 consecutive blank lines


# ---------------------------------------------------------------------------
# check_file — trailing whitespace
# ---------------------------------------------------------------------------


def test_check_trailing_whitespace(tmp_path: Path) -> None:
    p = write(tmp_path, "c.md", "# Heading  \nclean line\n")
    violations = check_file(p)
    assert any(v.kind == "trailing_whitespace" for v in violations)


def test_check_trailing_tab(tmp_path: Path) -> None:
    p = write(tmp_path, "d.md", "line with tab\t\nclean\n")
    violations = check_file(p)
    assert any(v.kind == "trailing_whitespace" for v in violations)


def test_check_no_trailing_whitespace_is_clean(tmp_path: Path) -> None:
    p = write(tmp_path, "e.md", "# Heading\nclean line\n")
    violations = check_file(p)
    assert not any(v.kind == "trailing_whitespace" for v in violations)


# ---------------------------------------------------------------------------
# check_file — clean file
# ---------------------------------------------------------------------------


def test_check_completely_clean_file(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        "clean_full.md",
        textwrap.dedent(
            """\
            ---
            name: test-agent
            ---

            ## Section One

            Some content here.

            ## Section Two

            More content.
            """
        ),
    )
    assert check_file(p) == []


# ---------------------------------------------------------------------------
# fix_file — consecutive blank lines
# ---------------------------------------------------------------------------


def test_fix_consecutive_blank_lines(tmp_path: Path) -> None:
    content = "line one\n\n\nline after two blanks\n"
    p = write(tmp_path, "h.md", content)
    n = fix_file(p)
    assert n >= 1
    result = p.read_text(encoding="utf-8")
    assert "\n\n\n" not in result
    assert "line one" in result
    assert "line after two blanks" in result


def test_fix_trailing_whitespace(tmp_path: Path) -> None:
    content = "line one   \nline two\t\nline three\n"
    p = write(tmp_path, "i.md", content)
    n = fix_file(p)
    assert n == 2
    result = p.read_text(encoding="utf-8")
    for line in result.splitlines():
        assert line == line.rstrip(), f"trailing whitespace remains: {line!r}"


def test_fix_returns_zero_for_clean_file(tmp_path: Path) -> None:
    content = "# Clean\n\nAll good here.\n"
    p = write(tmp_path, "j.md", content)
    n = fix_file(p)
    assert n == 0


def test_fix_clears_violations(tmp_path: Path) -> None:
    content = "# Head\n\n\ntext trailing   \nmore\n"
    p = write(tmp_path, "k.md", content)
    fix_file(p)
    violations = check_file(p)
    remaining_kinds = {v.kind for v in violations}
    assert "consecutive_blank_lines" not in remaining_kinds
    assert "trailing_whitespace" not in remaining_kinds


# ---------------------------------------------------------------------------
# fix_file — preserves trailing newline
# ---------------------------------------------------------------------------


def test_fix_preserves_trailing_newline(tmp_path: Path) -> None:
    content = "line one\n\n\nline two\n"
    p = write(tmp_path, "m.md", content)
    fix_file(p)
    result = p.read_text(encoding="utf-8")
    assert result.endswith("\n")


def test_fix_preserves_no_trailing_newline(tmp_path: Path) -> None:
    content = "line one\n\n\nline two"
    p = write(tmp_path, "n.md", content)
    fix_file(p)
    result = p.read_text(encoding="utf-8")
    assert not result.endswith("\n")


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------


def test_violation_fields() -> None:
    v = Violation(path="foo.md", line_no=5, kind="trailing_whitespace", detail="2 trailing char(s)")
    assert v.path == "foo.md"
    assert v.line_no == 5
    assert v.kind == "trailing_whitespace"
    assert v.detail == "2 trailing char(s)"


# ---------------------------------------------------------------------------
# Multiple violations in one file
# ---------------------------------------------------------------------------


def test_multiple_violations_reported(tmp_path: Path) -> None:
    content = "# Head  \n\n\nmore   \n"
    p = write(tmp_path, "multi.md", content)
    violations = check_file(p)
    kinds = {v.kind for v in violations}
    assert "trailing_whitespace" in kinds
    assert "consecutive_blank_lines" in kinds


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_file_is_clean(tmp_path: Path) -> None:
    p = write(tmp_path, "empty.md", "")
    assert check_file(p) == []


def test_single_line_no_newline(tmp_path: Path) -> None:
    p = write(tmp_path, "single.md", "just a line")
    assert check_file(p) == []


@pytest.mark.parametrize("run_len", [2, 3, 5])
def test_various_blank_line_run_lengths(tmp_path: Path, run_len: int) -> None:
    content = "before\n" + ("\n" * run_len) + "after\n"
    p = write(tmp_path, f"run{run_len}.md", content)
    violations = check_file(p)
    assert any(v.kind == "consecutive_blank_lines" for v in violations)
    assert any(str(run_len) in v.detail for v in violations)


# ---------------------------------------------------------------------------
# Code fence handling — structural checks must not fire inside fences
# ---------------------------------------------------------------------------


def test_consecutive_blank_lines_inside_fence_not_flagged(tmp_path: Path) -> None:
    content = textwrap.dedent(
        """\
        ## Section

        ```bash
        # part one

        # part two after intentional blank
        ```

        After fence.
        """
    )
    p = write(tmp_path, "blank_in_fence.md", content)
    violations = check_file(p)
    assert not any(v.kind == "consecutive_blank_lines" for v in violations)


def test_fix_preserves_blank_lines_inside_fence(tmp_path: Path) -> None:
    content = "before\n\n```\n\n\ncode with blanks\n```\nafter\n"
    p = write(tmp_path, "preserve_fence.md", content)
    fix_file(p)
    result = p.read_text(encoding="utf-8")
    # The two blank lines inside the fence must survive
    assert "```\n\n\ncode" in result


def test_tilde_fence_blank_lines_not_flagged(tmp_path: Path) -> None:
    content = "## Heading\n~~~python\ncode\n\n\nmore code\n~~~\nafter\n"
    p = write(tmp_path, "tilde.md", content)
    violations = check_file(p)
    assert not any(v.kind == "consecutive_blank_lines" for v in violations)
