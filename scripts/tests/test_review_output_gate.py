#!/usr/bin/env python3
"""Tests for the review-output validation gate wired into review dispatch.

Run with: python3 -m pytest scripts/tests/test_review_output_gate.py -v

The review skills (parallel-code-review, systematic-code-review) run each
reviewer's markdown output through `scripts/validate-review-output.py
--type <type>` after the reviewer returns. A valid review passes (exit 0); a
malformed review (missing verdict / bad severity / missing file:line) is
rejected (exit 1), which triggers the retry-once-then-stop gate documented in
those SKILL.md files.

These tests pin the gate's observable contract for the two wired types:
- VALID output passes via file path AND stdin (the dispatch flow may pipe).
- MALFORMED output is rejected so the gate actually fires.

Conventions match scripts/tests/: importlib loads the hyphenated validator
module for unit assertions; subprocess exercises the CLI exit-code contract
the SKILL.md prose names.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

VALIDATOR_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate-review-output.py"

_spec = importlib.util.spec_from_file_location("validate_review_output", VALIDATOR_PATH)
assert _spec is not None and _spec.loader is not None
_validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validator)

parse_markdown = _validator.parse_markdown
validate_structure = _validator.validate_structure


# ---------------------------------------------------------------------------
# Fixtures: VALID review output (passes, exit 0)
# ---------------------------------------------------------------------------

VALID_PARALLEL_MD = textwrap.dedent("""\
    ## Parallel Review Complete

    ### Severity Matrix

    | Severity | Count | Summary |
    |----------|-------|---------|
    | Critical | 1     | SQL injection found |
    | High     | 1     | Auth bypass |
    | Medium   | 1     | Missing validation |
    | Low      | 0     | None |

    ### Combined Findings

    #### CRITICAL
    1. [Security] SQL injection in user query - `internal/db/users.go:55`
       - Issue: Unparameterized query with user input
       - Recommendation: Use prepared statements

    #### HIGH
    1. [Business Logic] Auth bypass on admin route - `internal/api/admin.go:22`
       - Issue: Missing role check before privileged action
       - Recommendation: Add role guard middleware

    #### MEDIUM
    1. [Architecture] Missing input validation - `internal/api/handler.go:44`
       - Issue: Body parsed without schema validation
       - Recommendation: Validate against request struct

    ### Summary by Reviewer

    | Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
    |----------------|----------|------|--------|-----|
    | Security       | 1        | 0    | 0      | 0   |
    | Business Logic | 0        | 1    | 0      | 0   |
    | Architecture   | 0        | 0    | 1      | 0   |

    ### Recommendation
    **BLOCK** - Critical SQL injection must be fixed before merge.
""")

VALID_SYSTEMATIC_MD = textwrap.dedent("""\
    # Code Review: feat/add-user-endpoint

    ## Summary
    Added a REST endpoint for user creation with validation and persistence.
    Follows existing patterns but has an input-sanitization concern.

    ## Findings

    ### BLOCKING
    1. **SQL injection in user lookup** - `internal/api/handler.go:42`
       - Issue: Raw string interpolation in SQL query
       - Recommendation: Use parameterized queries

    ### SHOULD FIX
    1. **Missing error-path test** - `internal/api/handler_test.go:15`
       - Issue: Only happy path tested
       - Recommendation: Add a 409-conflict test case

    ### SUGGESTIONS
    1. **Extract validation** - `internal/api/handler.go:30`
       - Issue: Inline validation could be middleware
       - Recommendation: Optional, low priority

    ## POSITIVE NOTES
    - Clean separation of handler and service layers
    - Good use of context propagation

    Risk Level: HIGH

    Verdict: REQUEST-CHANGES

    Rationale: SQL injection risk must be addressed before merge.
""")


# ---------------------------------------------------------------------------
# Fixtures: MALFORMED review output (rejected, exit 1)
# ---------------------------------------------------------------------------

# parallel: no verdict, no severity matrix, no reviewer summary, and the lone
# finding has no [Reviewer] tag and no file:line location.
MALFORMED_PARALLEL_MD = textwrap.dedent("""\
    ## Parallel Review Complete

    #### CRITICAL
    1. SQL injection somewhere in the database layer
       - Issue: looks risky
""")

# systematic: missing verdict, missing risk_level, finding location is a bare
# filename with no :line, so it fails the file:line pattern too.
MALFORMED_SYSTEMATIC_MD = textwrap.dedent("""\
    # Code Review

    ## Findings

    ### BLOCKING
    1. **SQL injection** - handler.go
       - Issue: raw query
""")


VALID_MD = {"parallel": VALID_PARALLEL_MD, "systematic": VALID_SYSTEMATIC_MD}
MALFORMED_MD = {"parallel": MALFORMED_PARALLEL_MD, "systematic": MALFORMED_SYSTEMATIC_MD}


def _run_cli(review_type: str, md_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the validator CLI exactly as the dispatch gate names it."""
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--type", review_type, str(md_path)],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Unit-level: parser + schema (no subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("review_type", ["parallel", "systematic"])
def test_valid_output_has_no_schema_errors(review_type: str) -> None:
    """VALID review output parses and validates clean for the wired types."""
    parsed = parse_markdown(VALID_MD[review_type], review_type)
    errors = validate_structure(parsed, review_type)
    assert errors == [], f"expected clean validation, got: {errors}"


@pytest.mark.parametrize("review_type", ["parallel", "systematic"])
def test_malformed_output_is_rejected(review_type: str) -> None:
    """MALFORMED review output produces schema errors so the gate fires."""
    parsed = parse_markdown(MALFORMED_MD[review_type], review_type)
    errors = validate_structure(parsed, review_type)
    assert errors, "expected schema errors for malformed output, got none"


def test_malformed_parallel_flags_missing_verdict_and_reviewer() -> None:
    """The parallel malformed fixture trips the gate-relevant required fields."""
    parsed = parse_markdown(MALFORMED_PARALLEL_MD, "parallel")
    errors = validate_structure(parsed, "parallel")
    joined = "\n".join(errors)
    assert "MISSING: verdict" in joined
    assert "MISSING: severity_matrix" in joined
    assert "MISSING: reviewer_summary" in joined


def test_malformed_systematic_flags_verdict_risk_and_location() -> None:
    """The systematic malformed fixture trips verdict, risk_level, and file:line."""
    parsed = parse_markdown(MALFORMED_SYSTEMATIC_MD, "systematic")
    errors = validate_structure(parsed, "systematic")
    joined = "\n".join(errors)
    assert "MISSING: verdict" in joined
    assert "MISSING: risk_level" in joined
    # Bare "handler.go" never reaches the file:line pattern; it surfaces as a
    # missing location on the finding.
    assert "MISSING: location" in joined


# ---------------------------------------------------------------------------
# CLI-level: exit-code contract the SKILL.md prose depends on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("review_type", ["parallel", "systematic"])
def test_cli_accepts_valid_via_file(review_type: str, tmp_path: Path) -> None:
    """`validate-review-output.py --type <type> file.md` exits 0 on valid output."""
    md_path = tmp_path / "review.md"
    md_path.write_text(VALID_MD[review_type])
    result = _run_cli(review_type, md_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "VALIDATION PASSED" in result.stdout


@pytest.mark.parametrize("review_type", ["parallel", "systematic"])
def test_cli_rejects_malformed_via_file(review_type: str, tmp_path: Path) -> None:
    """Malformed output exits 1 — the failure that triggers retry-once-then-stop."""
    md_path = tmp_path / "review.md"
    md_path.write_text(MALFORMED_MD[review_type])
    result = _run_cli(review_type, md_path)
    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "VALIDATION FAILED" in result.stdout


@pytest.mark.parametrize("review_type", ["parallel", "systematic"])
def test_cli_accepts_valid_via_stdin(review_type: str) -> None:
    """The dispatch gate may pipe reviewer output: `... --type <type> -` exits 0."""
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--type", review_type, "-"],
        input=VALID_MD[review_type],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
