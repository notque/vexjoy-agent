#!/usr/bin/env python3
"""Routing regression benchmark for the /do router.

Validates that all expected routing targets (agents, skills, pipelines) referenced
in the benchmark test fixture actually exist in the INDEX.json files. This is a
STRUCTURAL benchmark — it checks that routing targets are valid, not that the LLM
routes correctly.

Usage:
    python3 scripts/routing-benchmark.py
    python3 scripts/routing-benchmark.py --verbose
    python3 scripts/routing-benchmark.py --category go-development
    python3 scripts/routing-benchmark.py --fixture path/to/custom.json

Exit codes:
    0 - All test cases have valid targets (or all expected targets are null)
    1 - One or more test cases reference non-existent components
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = REPO_ROOT / "scripts" / "routing-benchmark.json"
AGENTS_INDEX = REPO_ROOT / "agents" / "INDEX.json"
SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
PIPELINES_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"


def load_json(path: Path) -> dict:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        SystemExit: If the file is missing or contains invalid JSON.
    """
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def load_component_names() -> tuple[set[str], set[str], set[str]]:
    """Load all known agent, skill, and pipeline names from INDEX files.

    Returns:
        Tuple of (agent_names, skill_names, pipeline_names).
    """
    agents: set[str] = set()
    skills: set[str] = set()
    pipelines: set[str] = set()

    if AGENTS_INDEX.exists():
        data = load_json(AGENTS_INDEX)
        agents = set(data.get("agents", {}).keys())

    if SKILLS_INDEX.exists():
        data = load_json(SKILLS_INDEX)
        skills = set(data.get("skills", {}).keys())

    if PIPELINES_INDEX.exists():
        data = load_json(PIPELINES_INDEX)
        # Pipelines INDEX may use "pipelines" or "skills" as the key
        pipelines = set(data.get("pipelines", data.get("skills", {})).keys())

    return agents, skills, pipelines


def validate_test_case(
    case: dict,
    agents: set[str],
    skills: set[str],
    pipelines: set[str],
) -> list[str]:
    """Validate a single test case against known components.

    Args:
        case: Test case dictionary with expected_agent and expected_skill.
        agents: Set of known agent names.
        skills: Set of known skill names.
        pipelines: Set of known pipeline names.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    expected_agent = case.get("expected_agent")
    if expected_agent and expected_agent not in agents:
        errors.append(f"agent '{expected_agent}' not found in agents/INDEX.json")

    expected_skill = case.get("expected_skill")
    if expected_skill and expected_skill not in skills and expected_skill not in pipelines:
        errors.append(f"skill '{expected_skill}' not found in skills/INDEX.json")

    return errors


def run_benchmark(fixture_path: Path, *, verbose: bool = False, category_filter: str | None = None) -> bool:
    """Run the routing benchmark and report results.

    Args:
        fixture_path: Path to the benchmark JSON fixture.
        verbose: Show per-test-case results.
        category_filter: Only run test cases in this category.

    Returns:
        True if all test cases pass, False otherwise.
    """
    fixture = load_json(fixture_path)
    test_cases: list[dict] = fixture.get("test_cases", [])

    if not test_cases:
        print("ERROR: No test cases found in fixture", file=sys.stderr)
        return False

    agents, skills, pipelines = load_component_names()

    if verbose:
        print(f"Loaded components: {len(agents)} agents, {len(skills)} skills, {len(pipelines)} pipelines")
        print()

    # Filter by category if requested
    if category_filter:
        test_cases = [tc for tc in test_cases if tc.get("category") == category_filter]
        if not test_cases:
            print(f"ERROR: No test cases found for category '{category_filter}'", file=sys.stderr)
            return False

    pass_count = 0
    fail_count = 0
    null_count = 0
    category_counts: Counter[str] = Counter()
    failures: list[tuple[dict, list[str]]] = []

    for case in test_cases:
        category = case.get("category", "uncategorized")
        category_counts[category] += 1

        expected_agent = case.get("expected_agent")
        expected_skill = case.get("expected_skill")

        # Null targets are valid — they represent requests that should NOT route
        if expected_agent is None and expected_skill is None:
            null_count += 1
            pass_count += 1
            if verbose:
                print(f"  PASS (null target) : {case['request']}")
            continue

        errors = validate_test_case(case, agents, skills, pipelines)
        if errors:
            fail_count += 1
            failures.append((case, errors))
            if verbose:
                print(f"  FAIL : {case['request']}")
                for err in errors:
                    print(f"         -> {err}")
        else:
            pass_count += 1
            if verbose:
                targets = []
                if expected_agent:
                    targets.append(f"agent={expected_agent}")
                if expected_skill:
                    targets.append(f"skill={expected_skill}")
                print(f"  PASS : {case['request']}  [{', '.join(targets)}]")

    total = pass_count + fail_count

    if verbose:
        print()

    # Summary
    print(f"Routing Benchmark: {pass_count}/{total} test cases have valid targets", end="")
    if null_count:
        print(f" ({null_count} null-target guards)")
    else:
        print()

    # Category breakdown
    cat_parts = [f"{cat}({count})" for cat, count in sorted(category_counts.items())]
    print(f"Categories: {', '.join(cat_parts)}")

    # Report failures
    if failures:
        print()
        print("FAILURES:")
        for case, errors in failures:
            print(f'  [{case.get("category", "?")}] "{case["request"]}"')
            for err in errors:
                print(f"    -> {err}")

    return fail_count == 0


def main() -> None:
    """CLI entry point for the routing benchmark."""
    parser = argparse.ArgumentParser(
        description="Routing regression benchmark for the /do router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/routing-benchmark.py                     # Run all tests
  python3 scripts/routing-benchmark.py --verbose            # Show per-test results
  python3 scripts/routing-benchmark.py --category go-development  # Filter by category
        """,
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"Path to benchmark fixture JSON (default: {DEFAULT_FIXTURE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-test-case pass/fail results",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Only run test cases in this category",
    )

    args = parser.parse_args()
    success = run_benchmark(args.fixture, verbose=args.verbose, category_filter=args.category)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
