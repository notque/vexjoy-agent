#!/usr/bin/env python3
"""Golden-file tests for /do enhancement stacking.

Tests the COMBINATION logic: when multiple signal words appear in a
request, do the enhancements, anti-rationalization patterns, thinking
directives, model selection, and constraints all stack correctly?

This is the hardest part to get right deterministically — /do (Opus)
reads prose tables and combines them with judgment. do-enhance.py
must produce the same combinations from keyword matching.

Run:
    python3 -m pytest scripts/tests/test_do_enhancement_stacking.py -v
    python3 scripts/tests/test_do_enhancement_stacking.py  # scorecard

Golden expectations validated by Opus interpretation of /do SKILL.md
Phase 3 (ENHANCE) and Phase 4 (EXECUTE) rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importlib import import_module

do_classify = import_module("do-classify")
do_enhance = import_module("do-enhance")


def _norm_th(val: str | None) -> str | None:
    if val is None:
        return None
    return val.replace("thinking:", "")


def _run(request: str, complexity: str) -> dict:
    """Run enhance pipeline, return normalized result."""
    e = do_enhance.enhance(request, complexity)
    return {
        "enh": sorted(e["enhancements"]),
        "ar": sorted(e["anti_rationalization"]),
        "th": _norm_th(e["thinking_tag"]),
        "wm": e["worker_model"],
        "lo": e["local_only"],
        "md": e["model_dispatch"],
    }


# ─────────────────────────────────────────────────────────────────
# GOLDEN CASES: Single-signal baseline
# ─────────────────────────────────────────────────────────────────

SINGLE_SIGNAL_CASES = [
    {
        "id": 1,
        "label": "simple-code-fix",
        "request": "fix the null pointer in parser.go",
        "complexity": "Simple",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": "fast",
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 2,
        "label": "code-review",
        "request": "review the auth module changes",
        "complexity": "Medium",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "anti-rationalization-review"],
            "th": None,  # Medium = adaptive
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 3,
        "label": "security-work",
        "request": "security audit of the payment endpoint",
        "complexity": "Complex",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "anti-rationalization-security"],
            "th": "slow",
            "wm": "opus",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 4,
        "label": "testing-task",
        "request": "add test coverage for the router module",
        "complexity": "Simple",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "anti-rationalization-testing"],
            "th": "fast",
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 5,
        "label": "debugging-task",
        "request": "debug why the CI pipeline fails intermittently",
        "complexity": "Medium",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": None,  # Medium = adaptive
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 6,
        "label": "local-only",
        "request": "refactor the config loader, don't commit",
        "complexity": "Medium",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": None,
            "wm": "sonnet",
            "lo": True,
            "md": "direct",
        },
    },
]

# ─────────────────────────────────────────────────────────────────
# GOLDEN CASES: Multi-signal combinations (the hard ones)
# ─────────────────────────────────────────────────────────────────

COMBO_CASES = [
    {
        "id": 10,
        "label": "comprehensive-security-review",
        "request": "comprehensive security review of the entire auth system",
        "complexity": "Complex",
        "expect": {
            "enh": ["parallel-reviewers"],
            "ar": ["anti-rationalization-core", "anti-rationalization-security"],
            "th": "slow",  # security audit override
            "wm": "opus",  # Complex + security
            "lo": False,
            "md": "direct",  # analysis verb → direct
        },
    },
    {
        "id": 11,
        "label": "fix-with-tests-production",
        "request": "fix the login bug with tests, production ready",
        "complexity": "Simple",
        "expect": {
            "enh": ["test-driven-development", "verification-before-completion"],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": "fast",  # Simple
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 12,
        "label": "investigate-debug-local",
        "request": "investigate and debug the race condition, stay local",
        "complexity": "Medium",
        "expect": {
            "enh": ["research-coordinator-engineer"],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": None,  # Medium
            "wm": "sonnet",
            "lo": True,
            "md": "direct",
        },
    },
    {
        "id": 13,
        "label": "thorough-review-many-files",
        "request": "thorough review of the routing module across 12 files",
        "complexity": "Medium",
        "expect": {
            "enh": ["parallel-reviewers"],
            "ar": ["anti-rationalization-core", "anti-rationalization-review"],
            "th": None,  # Medium = adaptive
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 14,
        "label": "complex-extraction-grep",
        "request": "find all API endpoints and list their auth requirements",
        "complexity": "Complex",
        "expect": {
            "enh": [],
            "ar": [],  # extraction task, not security work (no security words)
            "th": "slow",  # Complex
            "wm": "opus",
            "lo": False,
            "md": "parallel-haiku",  # extraction verbs → fan-out
        },
    },
    {
        "id": 15,
        "label": "research-then-implement",
        "request": "research needed before we implement the caching layer",
        "complexity": "Medium",
        "expect": {
            "enh": ["research-coordinator-engineer"],
            "ar": ["anti-rationalization-core", "verification-checklist"],
            "th": None,  # Medium
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 16,
        "label": "comprehensive-test-production",
        "request": "comprehensive testing of the payment flow, production ready",
        "complexity": "Medium",
        "expect": {
            "enh": ["parallel-reviewers", "verification-before-completion"],
            "ar": ["anti-rationalization-core", "anti-rationalization-testing"],
            "th": None,
            "wm": "sonnet",
            "lo": False,
            "md": "direct",
        },
    },
    {
        "id": 17,
        "label": "security-fix-no-push",
        "request": "fix the SQL injection vulnerability, no push",
        "complexity": "Simple",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "anti-rationalization-security"],
            "th": "slow",  # security override beats Simple
            "wm": "opus",  # security override
            "lo": True,
            "md": "direct",
        },
    },
    {
        "id": 18,
        "label": "complex-audit-extract",
        "request": "audit all database queries and extract the slow ones",
        "complexity": "Complex",
        "expect": {
            "enh": [],
            "ar": ["anti-rationalization-core", "anti-rationalization-review"],
            "th": "slow",  # Complex
            "wm": "opus",
            "lo": False,
            "md": "parallel-haiku",  # extract → fan-out
        },
    },
    {
        "id": 19,
        "label": "investigate-first-security",
        "request": "investigate first then fix the auth bypass vulnerability",
        "complexity": "Complex",
        "expect": {
            "enh": ["research-coordinator-engineer"],
            "ar": ["anti-rationalization-core", "anti-rationalization-security"],
            "th": "slow",  # Complex + security
            "wm": "opus",
            "lo": False,
            "md": "direct",  # investigate is analysis verb
        },
    },
    {
        "id": 20,
        "label": "full-review-local-debug",
        "request": "full review and debug the memory leak, keep it local",
        "complexity": "Medium",
        "expect": {
            "enh": ["parallel-reviewers"],
            "ar": ["anti-rationalization-core", "anti-rationalization-review"],
            "th": None,  # Medium
            "wm": "sonnet",
            "lo": True,
            "md": "direct",
        },
    },
]

ALL_CASES = SINGLE_SIGNAL_CASES + COMBO_CASES


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", ALL_CASES, ids=[c["label"] for c in ALL_CASES])
def test_enhancement_stacking(case: dict) -> None:
    """Verify enhancement stacking matches Opus-validated golden expectation."""
    actual = _run(case["request"], case["complexity"])
    expect = case["expect"]

    mismatches = []
    for field in ("enh", "ar", "th", "wm", "lo", "md"):
        if actual[field] != expect[field]:
            mismatches.append(f"{field}: expected={expect[field]!r} got={actual[field]!r}")

    assert not mismatches, (
        f"#{case['id']} {case['label']}: {'; '.join(mismatches)}\n"
        f"  Request: {case['request']!r} (complexity={case['complexity']})\n"
        f"  Expected: {expect}\n"
        f"  Actual:   {actual}"
    )


@pytest.mark.parametrize(
    "case",
    COMBO_CASES,
    ids=[c["label"] for c in COMBO_CASES],
)
def test_combo_enhancement_count(case: dict) -> None:
    """Verify multi-signal requests produce multiple enhancements."""
    actual = _run(case["request"], case["complexity"])
    # Count total active features
    feature_count = (
        len(actual["enh"])
        + len(actual["ar"])
        + (1 if actual["lo"] else 0)
        + (1 if actual["th"] else 0)
        + (1 if actual["md"] != "direct" else 0)
    )
    # Every combo case should have at least 2 active features
    assert feature_count >= 2, (
        f"#{case['id']} {case['label']}: only {feature_count} active features "
        f"for multi-signal request. Expected ≥2.\n"
        f"  Active: enh={actual['enh']}, ar={actual['ar']}, "
        f"th={actual['th']}, lo={actual['lo']}, md={actual['md']}"
    )


# ─────────────────────────────────────────────────────────────────
# Standalone scorecard
# ─────────────────────────────────────────────────────────────────


def run_scorecard() -> None:
    """Run all cases and print enhancement stacking scorecard."""
    total = len(ALL_CASES)
    passed = 0
    failed = []

    for case in ALL_CASES:
        actual = _run(case["request"], case["complexity"])
        expect = case["expect"]

        mismatches = []
        for field in ("enh", "ar", "th", "wm", "lo", "md"):
            if actual[field] != expect[field]:
                mismatches.append(f"{field}:{expect[field]!r}→{actual[field]!r}")

        if mismatches:
            failed.append((case, mismatches))
        else:
            passed += 1

    print(f"\n{'=' * 70}")
    print(f"ENHANCEMENT STACKING TEST: {passed}/{total} ({passed * 100 // total}%)")
    print(
        f"  Singles: {sum(1 for c in SINGLE_SIGNAL_CASES if not any(c == f[0] for f in failed))}/{len(SINGLE_SIGNAL_CASES)}"
    )
    print(f"  Combos:  {sum(1 for c in COMBO_CASES if not any(c == f[0] for f in failed))}/{len(COMBO_CASES)}")
    print(f"{'=' * 70}")

    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for case, mismatches in failed:
            print(f"  #{case['id']:>2} {case['label']:<30} {', '.join(mismatches)}")
    else:
        print("\nAll enhancement stacking cases match golden expectations.")
    print()


if __name__ == "__main__":
    run_scorecard()
