"""Tests for validate-references.py --check-do-framing mode.

Three core cases:
1. Unpaired anti-pattern block fails validation (exit code 1, issue listed).
2. Paired anti-pattern block passes validation (exit code 0, no issues).
3. Annotated exception (no-pair-required) passes validation (exit code 0).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# ─── Path setup ────────────────────────────────────────────────────────────────

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
for _p in [str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

vr = importlib.import_module("validate-references")

# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_md(tmp_path):
    """Factory: write markdown content to a temp file and return its Path."""

    def _write(content: str, name: str = "test-agent.md") -> Path:
        f = tmp_path / name
        f.write_text(content, encoding="utf-8")
        return f

    return _write


# ---------------------------------------------------------------------------
# Case 1: Unpaired anti-pattern — must fail
# ---------------------------------------------------------------------------


UNPAIRED_CONTENT = """\
# Test Agent

## Anti-Pattern: Bad Thing

**What it looks like**: Someone does the bad thing.

**Why wrong**: It causes problems.
"""


def test_unpaired_antipattern_fails(tmp_md):
    """An anti-pattern block with no Do-instead counterpart produces an issue."""
    path = tmp_md(UNPAIRED_CONTENT)
    issues = vr.check_do_framing_in_file(path)
    assert len(issues) == 1, f"Expected 1 issue, got {len(issues)}: {issues}"
    assert issues[0].line_start >= 1


# ---------------------------------------------------------------------------
# Case 2: Paired anti-pattern — must pass
# ---------------------------------------------------------------------------


PAIRED_CONTENT = """\
# Test Agent

## Anti-Pattern: Bad Thing

**What it looks like**: Someone does the bad thing.

**Why wrong**: It causes problems.

**Do instead**: Do the good thing instead.
"""


def test_paired_antipattern_passes(tmp_md):
    """An anti-pattern block with a Do-instead counterpart produces no issues."""
    path = tmp_md(PAIRED_CONTENT)
    issues = vr.check_do_framing_in_file(path)
    assert issues == [], f"Expected no issues, got: {issues}"


# ---------------------------------------------------------------------------
# Case 3: Annotated exception — must pass
# ---------------------------------------------------------------------------


ANNOTATED_CONTENT = """\
# Test Agent

<!-- no-pair-required: absolute prohibition, no safe alternative -->
## Anti-Pattern: Never Do This

**What it looks like**: Someone commits credentials.

**Why wrong**: Security breach.
"""


def test_annotated_exception_passes(tmp_md):
    """An anti-pattern block annotated with no-pair-required produces no issues."""
    path = tmp_md(ANNOTATED_CONTENT)
    issues = vr.check_do_framing_in_file(path)
    assert issues == [], f"Expected no issues for annotated exception, got: {issues}"


# ---------------------------------------------------------------------------
# Case 4: Correct approach variant also counts as Do-instead
# ---------------------------------------------------------------------------


CORRECT_APPROACH_CONTENT = """\
# Test Agent

## Anti-Pattern: Wrong Way

**What it looks like**: Bad code.

**Why wrong**: It fails.

**Correct approach**: Use the right pattern.
"""


def test_correct_approach_counts_as_do_instead(tmp_md):
    """'Correct approach' is accepted as a Do-instead counterpart."""
    path = tmp_md(CORRECT_APPROACH_CONTENT)
    issues = vr.check_do_framing_in_file(path)
    assert issues == [], f"Expected no issues for 'Correct approach' variant, got: {issues}"


# ---------------------------------------------------------------------------
# Case 5: File with no anti-patterns — must pass
# ---------------------------------------------------------------------------


NO_ANTIPATTERN_CONTENT = """\
# Test Agent

## Overview

This agent does something useful.

## Patterns

Use this approach for best results.
"""


def test_no_antipatterns_passes(tmp_md):
    """A file with no anti-pattern blocks produces no issues."""
    path = tmp_md(NO_ANTIPATTERN_CONTENT)
    issues = vr.check_do_framing_in_file(path)
    assert issues == [], f"Expected no issues for file without anti-patterns, got: {issues}"
