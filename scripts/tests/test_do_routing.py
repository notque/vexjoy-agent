#!/usr/bin/env python3
"""Golden-file regression tests for /do routing scripts.

Each test case has an Opus-validated expected output. Any script change
that breaks these cases is a regression. Run with:

    python3 -m pytest scripts/tests/test_do_routing.py -v

To regenerate the golden file after intentional changes:

    python3 scripts/tests/test_do_routing.py --regenerate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importlib import import_module

# Import the modules under test
do_classify = import_module("do-classify")
do_enhance = import_module("do-enhance")

# ---------------------------------------------------------------------------
# Golden test cases — Opus-validated expected routing decisions
# ---------------------------------------------------------------------------
# These represent the "correct" routing decision for each request.
# Validated by Opus 4.6 LLM interpretation of /do SKILL.md rules.
# Graded 4.8/5 by independent Sonnet reviewer.
#
# Fields:
#   cx = complexity, cr = is_creation, iv = is_interview
#   wm = worker_model, th = thinking_tag (normalized, no "thinking:" prefix)
# ---------------------------------------------------------------------------

GOLDEN_CASES: list[dict] = [
    {
        "id": 1,
        "label": "trivial-read",
        "request": "read /home/feedgen/CLAUDE.md",
        "expect": {"cx": "Trivial", "cr": False, "iv": False, "wm": None, "th": None},
    },
    {
        "id": 2,
        "label": "simple-go-test",
        "request": "run go tests and fix any failures",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 3,
        "label": "simple-push-pr",
        "request": "push my changes and create a PR",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 4,
        "label": "simple-quick-fix",
        "request": "fix the typo on line 42 of routing-guide.md",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 5,
        "label": "medium-refactor",
        "request": "refactor the routing system to support plugin skills",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 6,
        "label": "medium-review-8files",
        "request": "comprehensive review of the auth module across 8 files",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 7,
        "label": "complex-security-audit",
        "request": "security audit of the entire API surface and fix vulnerabilities",
        "expect": {"cx": "Complex", "cr": False, "iv": False, "wm": "opus", "th": "slow"},
    },
    {
        "id": 8,
        "label": "creation-agent",
        "request": "create a new agent for Redis cluster debugging",
        "expect": {"cx": "Medium", "cr": True, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 9,
        "label": "interview-vague",
        "request": "build a thing that handles notifications",
        "expect": {"cx": "Simple", "cr": False, "iv": True, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 10,
        "label": "edge-quick-trap",
        "request": "quick overview of the codebase architecture",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
    # --- Additional edge cases ---
    {
        "id": 11,
        "label": "simple-rename",
        "request": "rename cfg to config in internal/",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 12,
        "label": "medium-migration",
        "request": "migrate the database schema to support multi-tenancy",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 13,
        "label": "interview-where-start",
        "request": "where do i even start with this",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 14,
        "label": "simple-add-test",
        "request": "add a test for parseConfig in src/config.go",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 15,
        "label": "complex-system-wide",
        "request": "system-wide refactor of error handling across all packages",
        "expect": {"cx": "Complex", "cr": False, "iv": False, "wm": "opus", "th": "slow"},
    },
    {
        "id": 16,
        "label": "local-only-refactor",
        "request": "refactor the parser, don't commit",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 17,
        "label": "parallel-numbered",
        "request": "1. fix the typo 2. update the version 3. run tests",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 18,
        "label": "creation-skill",
        "request": "scaffold a new skill for Terraform debugging",
        "expect": {"cx": "Medium", "cr": True, "iv": False, "wm": "sonnet", "th": None},
    },
    {
        "id": 19,
        "label": "simple-status",
        "request": "check PR status on the feature branch",
        "expect": {"cx": "Simple", "cr": False, "iv": False, "wm": "sonnet", "th": "fast"},
    },
    {
        "id": 20,
        "label": "medium-debug-complex",
        "request": "debug why CI fails on the go-patterns tests across 6 files",
        "expect": {"cx": "Medium", "cr": False, "iv": False, "wm": "sonnet", "th": None},
    },
]


def _norm_th(val: str | None) -> str | None:
    """Normalize thinking tag: 'thinking:fast' → 'fast'."""
    if val is None:
        return None
    return val.replace("thinking:", "")


def _run_pipeline(request: str) -> dict:
    """Run classify + enhance pipeline, return normalized decision."""
    c = do_classify.classify(request)
    if c["complexity"] == "Trivial":
        return {
            "cx": "Trivial",
            "cr": c["is_creation"],
            "iv": c["is_interview"],
            "wm": None,
            "th": None,
        }
    e = do_enhance.enhance(request, c["complexity"])
    return {
        "cx": c["complexity"],
        "cr": c["is_creation"],
        "iv": c["is_interview"],
        "wm": e["worker_model"],
        "th": _norm_th(e["thinking_tag"]),
    }


# ---------------------------------------------------------------------------
# Pytest parametrized tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    GOLDEN_CASES,
    ids=[c["label"] for c in GOLDEN_CASES],
)
def test_routing_decision(case: dict) -> None:
    """Verify routing decision matches Opus-validated golden expectation."""
    actual = _run_pipeline(case["request"])
    expect = case["expect"]

    mismatches = []
    for field in ("cx", "cr", "iv", "wm", "th"):
        if actual[field] != expect[field]:
            mismatches.append(f"{field}: expected={expect[field]!r} got={actual[field]!r}")

    assert not mismatches, (
        f"#{case['id']} {case['label']}: {'; '.join(mismatches)}\n"
        f"  Request: {case['request']!r}\n"
        f"  Expected: {expect}\n"
        f"  Actual:   {actual}"
    )


@pytest.mark.parametrize(
    "case",
    GOLDEN_CASES,
    ids=[c["label"] for c in GOLDEN_CASES],
)
def test_classify_only(case: dict) -> None:
    """Verify classification (complexity, creation, interview) independently."""
    c = do_classify.classify(case["request"])
    expect = case["expect"]

    assert c["complexity"] == expect["cx"], (
        f"#{case['id']} complexity: expected={expect['cx']!r} got={c['complexity']!r}"
    )
    assert c["is_creation"] == expect["cr"], (
        f"#{case['id']} is_creation: expected={expect['cr']!r} got={c['is_creation']!r}"
    )
    assert c["is_interview"] == expect["iv"], (
        f"#{case['id']} is_interview: expected={expect['iv']!r} got={c['is_interview']!r}"
    )


# ---------------------------------------------------------------------------
# Standalone runner with score report
# ---------------------------------------------------------------------------


def run_scorecard() -> None:
    """Run all cases and print a scorecard."""
    total = len(GOLDEN_CASES)
    passed = 0
    failed_cases = []

    for case in GOLDEN_CASES:
        actual = _run_pipeline(case["request"])
        expect = case["expect"]

        mismatches = []
        for field in ("cx", "cr", "iv", "wm", "th"):
            if actual[field] != expect[field]:
                mismatches.append(f"{field}:{expect[field]!r}→{actual[field]!r}")

        if mismatches:
            failed_cases.append((case, mismatches, actual))
        else:
            passed += 1

    print(f"\n{'=' * 70}")
    print(f"ROUTING REGRESSION TEST: {passed}/{total} passed ({passed * 100 // total}%)")
    print(f"{'=' * 70}")

    if failed_cases:
        print(f"\nFAILED ({len(failed_cases)}):")
        for case, mismatches, actual in failed_cases:
            print(f"  #{case['id']:>2} {case['label']:<25} {', '.join(mismatches)}")
            print(f"       Request: {case['request']!r}")
    else:
        print("\nAll cases match golden expectations.")
    print()


if __name__ == "__main__":
    if "--regenerate" in sys.argv:
        print("Regenerating golden file from current script output...")
        for case in GOLDEN_CASES:
            actual = _run_pipeline(case["request"])
            print(f"  #{case['id']} {case['label']}: {actual}")
        print("\nCopy desired values into GOLDEN_CASES to update expectations.")
    else:
        run_scorecard()
