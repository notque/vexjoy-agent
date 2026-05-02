#!/usr/bin/env python3
"""Test review output schemas against valid and invalid examples.

Generates realistic example outputs for each review type (systematic, parallel,
sapcc-review, sapcc-audit), validates them, then generates intentionally broken
outputs and confirms they fail validation with the expected errors.

Usage:
    python3 scripts/test-review-schemas.py
    python3 scripts/test-review-schemas.py -v          # verbose — show parsed structures
    python3 scripts/test-review-schemas.py --type parallel  # test only one type

Exit codes:
    0 = all tests pass
    1 = at least one test failed
"""

from __future__ import annotations

import argparse

# Import the validator module from the same scripts/ directory.
# The filename uses hyphens (validate-review-output.py) so we use importlib.
import importlib.util
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

_validator_path = Path(__file__).resolve().parent.parent / "validate-review-output.py"
_spec = importlib.util.spec_from_file_location("validate_review_output", _validator_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

load_schema = _mod.load_schema
parse_markdown = _mod.parse_markdown
validate_structure = _mod.validate_structure

# ---------------------------------------------------------------------------
# Test Fixtures: Valid Examples
# ---------------------------------------------------------------------------

VALID_SYSTEMATIC_MD = textwrap.dedent("""\
    # Code Review: feat/add-user-endpoint

    ## Summary
    Added a new REST endpoint for user creation with input validation and database persistence.
    The implementation follows existing patterns but has security concerns around input sanitization.

    ## Findings

    ### BLOCKING
    1. **SQL injection in user lookup** - `internal/api/handler.go:42`
       - Issue: Raw string interpolation in SQL query
       - Recommendation: Use parameterized queries via sqlx

    ### SHOULD FIX
    1. **Missing test for error path** - `internal/api/handler_test.go:15`
       - Issue: Only happy path tested, no test for duplicate user error
       - Recommendation: Add test case for 409 conflict response
    2. **Debug logging left in** - `internal/api/handler.go:67`
       - Issue: fmt.Println used instead of structured logger
       - Recommendation: Replace with log.Info

    ### SUGGESTIONS
    1. **Consider extracting validation** - `internal/api/handler.go:30`
       - Issue: Inline validation could be a reusable middleware
       - Recommendation: Extract to validation middleware (optional, low priority)

    ## POSITIVE NOTES
    - Clean separation of handler and service layers
    - Good use of context propagation

    Risk Level: HIGH

    Verdict: REQUEST-CHANGES

    Rationale: SQL injection risk must be addressed before merge.
""")

VALID_SYSTEMATIC_JSON: dict[str, Any] = {
    "verdict": "APPROVE",
    "summary": "Clean implementation with good test coverage and proper error handling throughout.",
    "risk_level": "LOW",
    "findings": {
        "blocking": [],
        "should_fix": [
            {
                "title": "Missing edge case test",
                "location": "internal/api/handler_test.go:88",
                "description": "No test for empty input",
                "recommendation": "Add test case",
            }
        ],
        "suggestions": [],
    },
    "positives": ["Good error handling", "Clean code structure"],
}

VALID_PARALLEL_MD = textwrap.dedent("""\
    ## Parallel Review Complete

    ### Severity Matrix

    | Severity | Count | Summary |
    |----------|-------|---------|
    | Critical | 1     | SQL injection found |
    | High     | 2     | Logic errors in auth flow |
    | Medium   | 3     | Code quality issues |
    | Low      | 1     | Minor naming suggestion |

    ### Combined Findings

    #### CRITICAL
    1. [Security] SQL injection in user query - `internal/db/users.go:55`
       - Issue: Unparameterized query with user input
       - Recommendation: Use prepared statements

    #### HIGH
    1. [Business Logic] Race condition in concurrent updates - `internal/api/handler.go:102`
       - Issue: No mutex or transaction isolation for balance update
       - Recommendation: Wrap in transaction with row-level lock
    2. [Architecture] Circular dependency between packages - `internal/service/auth.go:15`
       - Issue: auth imports user, user imports auth
       - Recommendation: Extract shared interface to common package

    #### MEDIUM
    1. [Security] Missing rate limiting on login endpoint - `internal/api/routes.go:33`
       - Issue: No rate limit on POST /login
       - Recommendation: Add rate limiter middleware
    2. [Business Logic] Silent failure on notification send - `internal/service/notify.go:28`
       - Issue: Error from email service swallowed
       - Recommendation: Log error and return to caller
    3. [Architecture] Large handler function - `internal/api/handler.go:45`
       - Issue: 200+ line handler function
       - Recommendation: Extract into smaller functions

    #### LOW
    1. [Architecture] Inconsistent naming - `internal/models/user.go:12`
       - Issue: Mix of camelCase and snake_case in struct tags
       - Recommendation: Standardize on camelCase for JSON tags

    ### Summary by Reviewer

    | Reviewer       | CRITICAL | HIGH | MEDIUM | LOW |
    |----------------|----------|------|--------|-----|
    | Security       | 1        | 0    | 1      | 0   |
    | Business Logic | 0        | 1    | 1      | 0   |
    | Architecture   | 0        | 1    | 1      | 1   |

    ## What Was Done Well
    - Comprehensive error types defined
    - Good middleware chain structure

    ### Recommendation
    **BLOCK** - Critical SQL injection vulnerability must be fixed before merge.
""")

VALID_PARALLEL_JSON: dict[str, Any] = {
    "verdict": "FIX",
    "summary": "Several high-priority issues found across security and architecture domains.",
    "severity_matrix": {"critical": 0, "high": 3, "medium": 2, "low": 1},
    "reviewer_summary": [
        {"reviewer": "Security", "critical": 0, "high": 1, "medium": 1, "low": 0},
        {"reviewer": "Business Logic", "critical": 0, "high": 1, "medium": 0, "low": 0},
        {"reviewer": "Architecture", "critical": 0, "high": 1, "medium": 1, "low": 1},
    ],
    "findings": {
        "critical": [],
        "high": [
            {
                "title": "Missing auth check on admin endpoint",
                "location": "internal/api/admin.go:22",
                "reviewer": "Security",
            },
            {
                "title": "Incorrect balance calculation",
                "location": "internal/service/billing.go:89",
                "reviewer": "Business Logic",
            },
            {
                "title": "Monolithic handler needs splitting",
                "location": "internal/api/handler.go:15",
                "reviewer": "Architecture",
            },
        ],
        "medium": [
            {
                "title": "Missing input validation",
                "location": "internal/api/handler.go:44",
                "reviewer": "Security",
            },
            {
                "title": "Dead code in router",
                "location": "internal/api/routes.go:90",
                "reviewer": "Architecture",
            },
        ],
        "low": [
            {
                "title": "Inconsistent naming style",
                "location": "internal/models/user.go:5",
                "reviewer": "Architecture",
            },
        ],
    },
    "positives": ["Clean error types"],
}

VALID_SAPCC_REVIEW_MD = textwrap.dedent("""\
    # SAPCC Code Review: limesctl

    **Module**: github.com/sapcc/limesctl
    **Date**: 2026-05-01
    **Packages reviewed**: 5 packages, 22 Go files, 8 test files
    **Agents dispatched**: 10 domain specialists

    ## Verdict

    Mostly clean codebase with a few type-safety issues around Option[T] usage and some
    missing test coverage for error paths. Would pass lead review with minor fixes.

    ## Score Card

    | Domain | Agent | Findings | Critical | High | Medium | Low |
    |--------|-------|----------|----------|------|--------|-----|
    | Signatures/Config | 1 | 2 | 0 | 1 | 1 | 0 |
    | Types/Option[T] | 2 | 3 | 0 | 2 | 1 | 0 |
    | HTTP/API | 3 | 1 | 0 | 0 | 1 | 0 |
    | Error Handling | 4 | 2 | 0 | 1 | 1 | 0 |
    | Database/SQL | 5 | 0 | 0 | 0 | 0 | 0 |
    | Testing | 6 | 4 | 0 | 1 | 2 | 1 |
    | Pkg Org/Imports | 7 | 1 | 0 | 0 | 0 | 1 |
    | Modern Go/Stdlib | 8 | 1 | 0 | 0 | 1 | 0 |
    | Observability/Jobs | 9 | 0 | 0 | 0 | 0 | 0 |
    | Anti-Patterns/LLM | 10 | 1 | 0 | 0 | 0 | 1 |

    ## Quick Wins

    1. Fix Option[T] in config struct - `internal/config/config.go:23`
       - Replace *string with Option[string]
    2. Remove dead import - `cmd/root.go:8`
       - Unused "fmt" import
    3. Add missing test assertion - `internal/service/limes_test.go:45`
       - Test creates resource but doesn't assert on result

    ## Critical Findings

    (none)

    ## High Findings

    ### HIGH
    1. **Pointer-based optional instead of Option[T]** - `internal/config/config.go:23`
       - Issue: Uses *string for optional fields instead of Option[string]
       - Recommendation: Migrate to Option[T] from go-bits
    2. **Missing nil check on Option value** - `internal/service/limes.go:89`
       - Issue: Accesses .Value without checking .IsSet first
       - Recommendation: Add IsSet guard before Value access
    3. **Untested error path in resource creation** - `internal/service/limes_test.go:30`
       - Issue: No test for quota exceeded error
       - Recommendation: Add test with mock returning quota error

    ## Medium Findings

    ### MEDIUM
    1. **Verbose error wrapping** - `internal/api/handler.go:55`
       - Issue: Error message duplicates context from caller
       - Recommendation: Use fmt.Errorf with %w, remove duplicate context
    2. **HTTP handler missing Content-Type check** - `internal/api/handler.go:12`
       - Issue: POST handler does not validate Content-Type header
       - Recommendation: Add Content-Type validation middleware
    3. **Test uses real HTTP client** - `internal/service/limes_test.go:60`
       - Issue: Integration test mixed with unit tests
       - Recommendation: Use httptest.NewServer for isolation

    ## Low Findings

    ### LOW
    1. **Unused helper function** - `internal/util/helpers.go:44`
       - Issue: FormatDuration not called anywhere
    2. **Comment style inconsistency** - `cmd/root.go:15`
       - Issue: Mix of // and /* */ comments

    ## What's Done Well
    - Clean package structure with clear boundaries
    - Good use of go-bits error handling patterns
    - Comprehensive happy-path test coverage
""")

VALID_SAPCC_REVIEW_JSON: dict[str, Any] = {
    "verdict": "Needs minor fixes before merge",
    "summary": "Clean codebase with a few type-safety issues around Option[T] usage. Would pass lead review with minor fixes.",
    "scorecard": [
        {"domain": "Signatures/Config", "agent": 1, "findings": 2, "critical": 0, "high": 1, "medium": 1, "low": 0},
        {"domain": "Types/Option[T]", "agent": 2, "findings": 3, "critical": 0, "high": 2, "medium": 1, "low": 0},
        {"domain": "HTTP/API", "agent": 3, "findings": 1, "critical": 0, "high": 0, "medium": 1, "low": 0},
        {"domain": "Error Handling", "agent": 4, "findings": 2, "critical": 0, "high": 1, "medium": 1, "low": 0},
        {"domain": "Database/SQL", "agent": 5, "findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"domain": "Testing", "agent": 6, "findings": 4, "critical": 0, "high": 1, "medium": 2, "low": 1},
        {"domain": "Pkg Org/Imports", "agent": 7, "findings": 1, "critical": 0, "high": 0, "medium": 0, "low": 1},
        {"domain": "Modern Go/Stdlib", "agent": 8, "findings": 1, "critical": 0, "high": 0, "medium": 1, "low": 0},
        {"domain": "Observability/Jobs", "agent": 9, "findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
        {"domain": "Anti-Patterns/LLM", "agent": 10, "findings": 1, "critical": 0, "high": 0, "medium": 0, "low": 1},
    ],
    "quick_wins": [
        {"title": "Fix Option[T] usage", "location": "internal/config/config.go:23"},
        {"title": "Remove dead import", "location": "cmd/root.go:8"},
    ],
    "findings": {
        "critical": [],
        "high": [
            {"title": "Pointer-based optional instead of Option[T]", "location": "internal/config/config.go:23"},
        ],
        "medium": [
            {"title": "Verbose error wrapping", "location": "internal/api/handler.go:55"},
        ],
        "low": [
            {"title": "Unused helper function", "location": "internal/util/helpers.go:44"},
        ],
    },
    "positives": ["Clean package structure", "Good use of go-bits error handling"],
}

VALID_SAPCC_AUDIT_MD = textwrap.dedent("""\
    # SAPCC Code Review: elektra

    **Reviewed by**: Lead & secondary reviewer standards (simulated)
    **Date**: 2026-05-01
    **Packages**: 8 packages, 35 Go files

    ## Verdict

    Needs work before review — 3 must-fix issues found. The codebase has consistent
    patterns but several interfaces with single implementations and some dead code.

    ## Must-Fix

    ### MUST-FIX
    1. **Interface with single implementation** - `internal/service/interface.go:12`
       - Convention: "Remove interface, use concrete type directly"
       - Issue: PolicyProvider interface has exactly one implementation
       - Recommendation: Delete interface, use PolicyService directly
    2. **Constructor returns error unnecessarily** - `internal/auth/auth.go:15`
       - Convention: "Constructors should be infallible"
       - Issue: NewAuthHandler returns (AuthHandler, error) but error is always nil
       - Recommendation: Remove error return, panic on programming errors
    3. **Internal error with no context** - `internal/storage/db.go:87`
       - Convention: "Every error message must carry enough context to debug"
       - Issue: Returns fmt.Errorf("internal error") with no file/operation context
       - Recommendation: Include operation name and relevant IDs

    ## Should-Fix

    ### SHOULD-FIX
    1. **Viper config instead of osext.MustGetenv** - `internal/config/config.go:33`
       - Convention: "Use osext.MustGetenv for environment config"
       - Issue: Using viper to read env vars
       - Recommendation: Replace with osext.MustGetenv
    2. **Duplicate handler logic** - `internal/api/routes.go:61`
       - Issue: Handler at line 61 is 90% identical to handler at line 89
       - Recommendation: Extract shared logic into helper function

    ## Nits

    ### NIT
    1. **Comment style inconsistency** - `cmd/main.go:5`
       - Issue: Mix of sentence-case and lowercase comments
    2. **Unused import in test** - `internal/api/handler_test.go:3`
       - Issue: "testing/quick" imported but not used

    ## What's Done Well
    - Clean error propagation chain
    - Good use of httptest in integration tests
    - Consistent package naming

    ## Package-by-Package Summary

    | Package | Files | Must-Fix | Should-Fix | Nit | Verdict |
    |---------|-------|----------|-----------|-----|---------|
    | internal/api | 8 | 0 | 1 | 0 | OK |
    | internal/auth | 4 | 1 | 0 | 0 | NEEDS WORK |
    | internal/config | 3 | 0 | 1 | 0 | OK |
    | internal/service | 6 | 1 | 0 | 0 | NEEDS WORK |
    | internal/storage | 5 | 1 | 0 | 0 | NEEDS WORK |
    | internal/models | 4 | 0 | 0 | 0 | CLEAN |
    | cmd | 3 | 0 | 0 | 1 | OK |
    | internal/util | 2 | 0 | 0 | 1 | OK |
""")

VALID_SAPCC_AUDIT_JSON: dict[str, Any] = {
    "verdict": "Needs work before review",
    "summary": "Three must-fix issues found. The codebase has consistent patterns but interface and error handling violations.",
    "findings": {
        "must_fix": [
            {
                "title": "Interface with single implementation",
                "location": "internal/service/interface.go:12",
                "convention": "Remove interface, use concrete type directly",
            },
        ],
        "should_fix": [
            {
                "title": "Viper config instead of osext.MustGetenv",
                "location": "internal/config/config.go:33",
                "convention": "Use osext.MustGetenv for environment config",
            },
        ],
        "nit": [
            {"title": "Comment style inconsistency", "location": "cmd/main.go:5"},
        ],
    },
    "package_summary": [
        {"package": "internal/api", "files": 8, "must_fix": 0, "should_fix": 1, "nit": 0, "verdict": "OK"},
        {"package": "internal/auth", "files": 4, "must_fix": 1, "should_fix": 0, "nit": 0, "verdict": "NEEDS WORK"},
        {"package": "cmd", "files": 3, "must_fix": 0, "should_fix": 0, "nit": 1, "verdict": "OK"},
    ],
    "positives": ["Clean error propagation chain"],
}


# ---------------------------------------------------------------------------
# Test Fixtures: Invalid Examples
# ---------------------------------------------------------------------------


def _invalid_systematic_cases() -> list[tuple[str, dict[str, Any], str]]:
    """Return (name, data, expected_error_substring) tuples for systematic review."""
    return [
        (
            "missing_verdict",
            {
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
                "risk_level": "LOW",
            },
            "MISSING: verdict",
        ),
        (
            "bad_verdict_enum",
            {
                "verdict": "PASS",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
                "risk_level": "LOW",
            },
            "VALUE: verdict",
        ),
        (
            "missing_risk_level",
            {
                "verdict": "APPROVE",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
            },
            "MISSING: risk_level",
        ),
        (
            "bad_risk_level",
            {
                "verdict": "APPROVE",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
                "risk_level": "EXTREME",
            },
            "VALUE: risk_level",
        ),
        (
            "bad_location_format",
            {
                "verdict": "APPROVE",
                "findings": {
                    "blocking": [{"title": "Issue", "location": "handler.go"}],
                    "should_fix": [],
                    "suggestions": [],
                },
                "risk_level": "LOW",
            },
            "FORMAT: findings.blocking.0.location",
        ),
        (
            "missing_finding_title",
            {
                "verdict": "APPROVE",
                "findings": {
                    "blocking": [{"location": "handler.go:42"}],
                    "should_fix": [],
                    "suggestions": [],
                },
                "risk_level": "LOW",
            },
            "MISSING: title",
        ),
    ]


def _invalid_parallel_cases() -> list[tuple[str, dict[str, Any], str]]:
    """Return (name, data, expected_error_substring) tuples for parallel review."""
    return [
        (
            "missing_severity_matrix",
            {
                "verdict": "APPROVE",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "reviewer_summary": [
                    {"reviewer": "Security", "critical": 0, "high": 0, "medium": 0, "low": 0},
                ],
            },
            "MISSING: severity_matrix",
        ),
        (
            "missing_reviewer_summary",
            {
                "verdict": "APPROVE",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "severity_matrix": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            },
            "MISSING: reviewer_summary",
        ),
        (
            "bad_verdict",
            {
                "verdict": "NEEDS-DISCUSSION",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "severity_matrix": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "reviewer_summary": [],
            },
            "VALUE: verdict",
        ),
        (
            "finding_missing_reviewer",
            {
                "verdict": "APPROVE",
                "findings": {
                    "critical": [{"title": "SQL injection", "location": "db.go:55"}],
                    "high": [],
                    "medium": [],
                    "low": [],
                },
                "severity_matrix": {"critical": 1, "high": 0, "medium": 0, "low": 0},
                "reviewer_summary": [
                    {"reviewer": "Security", "critical": 1, "high": 0, "medium": 0, "low": 0},
                ],
            },
            "MISSING: reviewer",
        ),
        (
            "negative_count_in_matrix",
            {
                "verdict": "APPROVE",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "severity_matrix": {"critical": -1, "high": 0, "medium": 0, "low": 0},
                "reviewer_summary": [],
            },
            "VALUE: severity_matrix.critical",
        ),
        (
            "missing_matrix_field",
            {
                "verdict": "APPROVE",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "severity_matrix": {"critical": 0, "high": 0, "medium": 0},
                "reviewer_summary": [],
            },
            "MISSING: low",
        ),
    ]


def _invalid_sapcc_review_cases() -> list[tuple[str, dict[str, Any], str]]:
    """Return (name, data, expected_error_substring) tuples for sapcc-review."""
    base_scorecard = [
        {"domain": f"Domain {i}", "agent": i, "findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
        for i in range(1, 11)
    ]
    return [
        (
            "missing_scorecard",
            {
                "verdict": "Needs fixes",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "quick_wins": [],
            },
            "MISSING: scorecard",
        ),
        (
            "wrong_scorecard_count",
            {
                "verdict": "Needs fixes",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "scorecard": base_scorecard[:5],
                "quick_wins": [],
            },
            "COUNT: scorecard",
        ),
        (
            "missing_quick_wins",
            {
                "verdict": "Needs fixes",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "scorecard": base_scorecard,
            },
            "MISSING: quick_wins",
        ),
        (
            "scorecard_agent_out_of_range",
            {
                "verdict": "Needs fixes",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "scorecard": [
                    *base_scorecard[:9],
                    {"domain": "Extra", "agent": 11, "findings": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
                ],
                "quick_wins": [],
            },
            "scorecard.9.agent",
        ),
    ]


def _invalid_sapcc_audit_cases() -> list[tuple[str, dict[str, Any], str]]:
    """Return (name, data, expected_error_substring) tuples for sapcc-audit."""
    return [
        (
            "missing_package_summary",
            {
                "verdict": "Needs work",
                "findings": {"must_fix": [], "should_fix": [], "nit": []},
            },
            "MISSING: package_summary",
        ),
        (
            "empty_package_summary",
            {
                "verdict": "Needs work",
                "findings": {"must_fix": [], "should_fix": [], "nit": []},
                "package_summary": [],
            },
            "COUNT: package_summary",
        ),
        (
            "package_missing_verdict",
            {
                "verdict": "Needs work",
                "findings": {"must_fix": [], "should_fix": [], "nit": []},
                "package_summary": [{"package": "internal/api", "files": 5, "must_fix": 0, "should_fix": 0, "nit": 0}],
            },
            "MISSING: verdict",
        ),
        (
            "bad_location_in_finding",
            {
                "verdict": "Needs work",
                "findings": {
                    "must_fix": [{"title": "Bad error", "location": "db.go"}],
                    "should_fix": [],
                    "nit": [],
                },
                "package_summary": [
                    {
                        "package": "internal/api",
                        "files": 5,
                        "must_fix": 1,
                        "should_fix": 0,
                        "nit": 0,
                        "verdict": "NEEDS WORK",
                    }
                ],
            },
            "FORMAT: findings.must_fix.0.location",
        ),
    ]


# ---------------------------------------------------------------------------
# Test Fixtures: Valid Markdown Examples (parsed then validated)
# ---------------------------------------------------------------------------

VALID_MD_FIXTURES: dict[str, str] = {
    "systematic": VALID_SYSTEMATIC_MD,
    "parallel": VALID_PARALLEL_MD,
    "sapcc-review": VALID_SAPCC_REVIEW_MD,
    "sapcc-audit": VALID_SAPCC_AUDIT_MD,
}

VALID_JSON_FIXTURES: dict[str, dict[str, Any]] = {
    "systematic": VALID_SYSTEMATIC_JSON,
    "parallel": VALID_PARALLEL_JSON,
    "sapcc-review": VALID_SAPCC_REVIEW_JSON,
    "sapcc-audit": VALID_SAPCC_AUDIT_JSON,
}

INVALID_CASES: dict[str, list[tuple[str, dict[str, Any], str]]] = {
    "systematic": _invalid_systematic_cases(),
    "parallel": _invalid_parallel_cases(),
    "sapcc-review": _invalid_sapcc_review_cases(),
    "sapcc-audit": _invalid_sapcc_audit_cases(),
}


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------


class TestResults:
    """Accumulates test pass/fail counts."""

    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        """Record a test result."""
        if passed:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed += 1
            self.failures.append(f"{name}: {detail}")
            print(f"  FAIL  {name}")
            if detail:
                print(f"        {detail}")

    @property
    def total(self) -> int:
        return self.passed + self.failed


def run_tests(review_types: list[str], verbose: bool = False) -> TestResults:
    """Run all schema validation tests.

    Args:
        review_types: Which review types to test.
        verbose: Show parsed structures on pass.

    Returns:
        TestResults with accumulated pass/fail counts.
    """
    results = TestResults()

    for rtype in review_types:
        print(f"\n{'=' * 60}")
        print(f"  Testing: {rtype}")
        print(f"{'=' * 60}")

        # -- Valid JSON tests --
        print(f"\n  --- Valid JSON ({rtype}) ---")
        json_data = VALID_JSON_FIXTURES[rtype]
        errors = validate_structure(json_data, rtype)
        passed = len(errors) == 0
        detail = "; ".join(errors[:3]) if errors else ""
        results.record(f"{rtype}/valid_json", passed, detail)
        if verbose and passed:
            print(f"        Structure: {json.dumps(json_data, indent=2)[:200]}...")

        # -- Valid Markdown tests --
        print(f"\n  --- Valid Markdown ({rtype}) ---")
        md_content = VALID_MD_FIXTURES[rtype]
        parsed = parse_markdown(md_content, rtype)

        # First check parse succeeded
        has_verdict = "verdict" in parsed
        results.record(f"{rtype}/md_parse_verdict", has_verdict, f"parsed keys: {list(parsed.keys())}")

        has_findings = "findings" in parsed and any(
            len(v) > 0 for v in parsed.get("findings", {}).values() if isinstance(v, list)
        )
        results.record(f"{rtype}/md_parse_findings", has_findings, f"findings: {parsed.get('findings', {})}")

        # Validate parsed markdown
        errors = validate_structure(parsed, rtype)
        passed = len(errors) == 0
        detail = "; ".join(errors[:3]) if errors else ""
        results.record(f"{rtype}/md_validates", passed, detail)

        if verbose and passed:
            print(f"        Parsed: {json.dumps(parsed, indent=2)[:300]}...")

        # -- Invalid JSON tests --
        print(f"\n  --- Invalid JSON ({rtype}) ---")
        invalid_cases = INVALID_CASES[rtype]
        for case_name, data, expected_error in invalid_cases:
            errors = validate_structure(data, rtype)
            # Should have at least one error
            has_errors = len(errors) > 0
            # Expected error substring should appear in at least one error
            has_expected = any(expected_error in err for err in errors)
            passed = has_errors and has_expected
            if not has_errors:
                detail = "expected validation errors but got none"
            elif not has_expected:
                detail = f"expected '{expected_error}' in errors, got: {errors[:2]}"
            else:
                detail = ""
            results.record(f"{rtype}/invalid_{case_name}", passed, detail)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the test suite.

    Returns:
        Exit code: 0 if all pass, 1 if any fail.
    """
    parser = argparse.ArgumentParser(description="Test review output schemas.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show parsed structures on pass.")
    parser.add_argument(
        "--type", choices=("systematic", "parallel", "sapcc-review", "sapcc-audit"), help="Test only one review type."
    )
    args = parser.parse_args()

    types = [args.type] if args.type else ["systematic", "parallel", "sapcc-review", "sapcc-audit"]

    print("Review Schema Validation Test Suite")
    print("=" * 60)

    results = run_tests(types, verbose=args.verbose)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {results.passed} passed, {results.failed} failed, {results.total} total")
    print(f"{'=' * 60}")

    if results.failures:
        print("\nFailures:")
        for f in results.failures:
            print(f"  - {f}")

    return 0 if results.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
