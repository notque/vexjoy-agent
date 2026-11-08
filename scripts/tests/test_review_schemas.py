#!/usr/bin/env python3
"""Test review output schemas against valid and invalid examples.

Generates realistic example outputs for each review type (systematic, parallel,
sapcc-review, sapcc-audit), validates them, then generates intentionally broken
outputs and confirms they fail validation with the expected errors.

Run with: python3 -m pytest scripts/tests/test_review_schemas.py -v
"""

from __future__ import annotations

# Import the validator module from the scripts/ directory.
# The filename uses hyphens (validate-review-output.py) so we use importlib.
import copy
import importlib.util
import textwrap
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("jsonschema", exc_type=ImportError)

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

    Verdict: BLOCK

    Rationale: SQL injection risk must be addressed before merge.
""")

VALID_SYSTEMATIC_JSON: dict[str, Any] = {
    "verdict": "NEEDS_CHANGES",
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
    "verdict": "NEEDS_CHANGES",
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
                "verdict": "LGTM",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
                "risk_level": "LOW",
            },
            "VALUE: verdict",
        ),
        (
            "missing_risk_level",
            {
                "verdict": "PASS",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
            },
            "MISSING: risk_level",
        ),
        (
            "bad_risk_level",
            {
                "verdict": "PASS",
                "findings": {"blocking": [], "should_fix": [], "suggestions": []},
                "risk_level": "EXTREME",
            },
            "VALUE: risk_level",
        ),
        (
            "bad_location_format",
            {
                "verdict": "BLOCK",
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
                "verdict": "BLOCK",
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
                "verdict": "PASS",
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
                "verdict": "PASS",
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
                "verdict": "BLOCK",
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
                "verdict": "PASS",
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "severity_matrix": {"critical": -1, "high": 0, "medium": 0, "low": 0},
                "reviewer_summary": [],
            },
            "VALUE: severity_matrix.critical",
        ),
        (
            "missing_matrix_field",
            {
                "verdict": "PASS",
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
# Tests
# ---------------------------------------------------------------------------

ALL_TYPES = ("systematic", "parallel", "sapcc-review", "sapcc-audit")


@pytest.mark.parametrize("rtype", ALL_TYPES)
def test_valid_json_validates(rtype: str) -> None:
    assert validate_structure(copy.deepcopy(VALID_JSON_FIXTURES[rtype]), rtype) == []


@pytest.mark.parametrize("rtype", ALL_TYPES)
def test_valid_markdown_parses_and_validates(rtype: str) -> None:
    parsed = parse_markdown(VALID_MD_FIXTURES[rtype], rtype)
    assert "verdict" in parsed, list(parsed)
    assert any(len(v) > 0 for v in parsed.get("findings", {}).values() if isinstance(v, list)), parsed
    assert validate_structure(parsed, rtype) == []


@pytest.mark.parametrize(
    ("rtype", "case_name", "data", "expected_error"),
    [(rtype, name, data, expected) for rtype in ALL_TYPES for name, data, expected in INVALID_CASES[rtype]],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_invalid_json_is_rejected(rtype: str, case_name: str, data: dict[str, Any], expected_error: str) -> None:
    errors = validate_structure(copy.deepcopy(data), rtype)
    assert errors, f"{rtype}/{case_name}: expected validation errors but got none"
    assert any(expected_error in err for err in errors), errors


@pytest.mark.parametrize("rtype", ALL_TYPES)
def test_schema_loads(rtype: str) -> None:
    assert load_schema(rtype)["type"] == "object"


# The Phase 4 template in skills/review/review/SKILL.md: label lines, not headings.
SKILL_TEMPLATE_MD = textwrap.dedent("""\
    Review Summary:
      Files Reviewed: 3 | Lines Changed: +40/-5
      Test Status: PASS
      Risk Level: MEDIUM

    BLOCKING:
      1. Token compared with == leaks timing - internal/auth/token.go:42
    SHOULD FIX:
      1. Error message drops the cause - internal/auth/login.go:52
      2. No test for the expired-token path - internal/auth/token_test.go:12
    SUGGESTIONS:
      1. Name the 3600 constant - internal/auth/token.go:62

    Verdict: BLOCK
    Rationale: The timing leak must be fixed; evidence at the cited lines.
""")


def test_skill_template_label_sections_are_counted() -> None:
    parsed = parse_markdown(SKILL_TEMPLATE_MD, "systematic")
    findings = parsed["findings"]
    assert [f["location"] for f in findings["blocking"]] == ["internal/auth/token.go:42"]
    assert [f["location"] for f in findings["should_fix"]] == [
        "internal/auth/login.go:52",
        "internal/auth/token_test.go:12",
    ]
    assert [f["location"] for f in findings["suggestions"]] == ["internal/auth/token.go:62"]
    assert parsed["verdict"] == "BLOCK"
    assert parsed["risk_level"] == "MEDIUM"
    assert validate_structure(parsed, "systematic") == []


def test_pass_over_blocking_label_findings_is_rejected() -> None:
    md = SKILL_TEMPLATE_MD.replace("Verdict: BLOCK", "Verdict: PASS")
    errors = validate_structure(parse_markdown(md, "systematic"), "systematic")
    assert any("VERDICT: PASS" in e and "blocking" in e for e in errors), errors


def test_needs_changes_over_blocking_is_rejected() -> None:
    md = SKILL_TEMPLATE_MD.replace("Verdict: BLOCK", "Verdict: NEEDS_CHANGES")
    errors = validate_structure(parse_markdown(md, "systematic"), "systematic")
    assert any("VERDICT: NEEDS_CHANGES" in e and "BLOCK" in e for e in errors), errors


def test_pass_over_should_fix_is_rejected() -> None:
    md = SKILL_TEMPLATE_MD.replace(
        "BLOCKING:\n  1. Token compared with == leaks timing - internal/auth/token.go:42\n", ""
    )
    md = md.replace("Verdict: BLOCK", "Verdict: PASS")
    errors = validate_structure(parse_markdown(md, "systematic"), "systematic")
    assert any("VERDICT: PASS" in e and "should_fix" in e for e in errors), errors
    ok = md.replace("Verdict: PASS", "Verdict: NEEDS_CHANGES")
    assert validate_structure(parse_markdown(ok, "systematic"), "systematic") == []


def test_parallel_pass_over_high_matrix_is_rejected() -> None:
    data = copy.deepcopy(VALID_PARALLEL_JSON)
    data["verdict"] = "PASS"
    errors = validate_structure(data, "parallel")
    assert any("VERDICT: PASS" in e and "high" in e for e in errors), errors


@pytest.mark.parametrize("legacy", ["APPROVE", "REQUEST-CHANGES", "REQUEST_CHANGES", "NEEDS-DISCUSSION", "FIX"])
@pytest.mark.parametrize("rtype", ["systematic", "parallel"])
def test_legacy_verdicts_are_rejected_with_the_replacement(rtype: str, legacy: str) -> None:
    data = copy.deepcopy(VALID_JSON_FIXTURES[rtype])
    data["verdict"] = legacy
    errors = validate_structure(data, rtype)
    assert any(f'"{legacy}"' in e and "use" in e and "instead" in e for e in errors), errors


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Verdict: NEEDS_CHANGES", "NEEDS_CHANGES"),
        ("VERDICT: BLOCK", "BLOCK"),
        ("7. VERDICT: PASS", "PASS"),
        ("## 1. VERDICT: NEEDS_CHANGES", "NEEDS_CHANGES"),
        ("## 1. COMPOSITE VERDICT: BLOCK", "BLOCK"),
        ("## VERDICT: PASS", "PASS"),
        ("**NEEDS_CHANGES** - two HIGH findings", "NEEDS_CHANGES"),
        ("**Verdict**: **PASS** - nothing found", "PASS"),
    ],
)
def test_verdict_line_shapes(line: str, expected: str) -> None:
    assert parse_markdown(f"# Review\n\n{line}\n", "systematic")["verdict"] == expected


@pytest.mark.parametrize(
    ("text", "location"),
    [
        ("Cron runs at 02:00 every night", None),
        ("Server listens on localhost:8080", None),
        ("See http://localhost:8080/health", None),
        ("Bound to 127.0.0.1:8000", None),
        ("Leak in `internal/api/handler.go:42`", "internal/api/handler.go:42"),
        ("Leak in handler_test.go:15 under load", "handler_test.go:15"),
        ("Workflow .github/workflows/test.yml:7 pins nothing", ".github/workflows/test.yml:7"),
        ("Leak in /home/user/repo/scripts/x.py:12", "/home/user/repo/scripts/x.py:12"),
        ("See https://example.com/a/b.py:12", None),
        ("Target has no .PHONY - Makefile:12", "Makefile:12"),
        ("Runs as root - `Dockerfile:3`", "Dockerfile:3"),
    ],
)
def test_file_line_needs_a_path(text: str, location: str | None) -> None:
    match = _mod.FILE_LINE_RE.search(text)
    assert (match.group(1) if match else None) == location
