#!/usr/bin/env python3
"""
Compare agent benchmark results.

Usage:
    python scripts/compare.py benchmark/workerpool/
"""

import subprocess
import sys
from pathlib import Path


def count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def run_tests(directory: Path) -> tuple[int, int]:
    """Run go tests and return (passed, total)."""
    result = subprocess.run(["go", "test", "-v"], cwd=directory, capture_output=True, text=True)

    output = result.stdout + result.stderr
    passed = output.count("--- PASS:")
    failed = output.count("--- FAIL:")

    return passed, passed + failed


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare.py <benchmark-dir>")
        sys.exit(1)

    base = Path(sys.argv[1])
    full_dir = base / "full"
    compact_dir = base / "compact"

    if not full_dir.exists() or not compact_dir.exists():
        print(f"Error: Expected {full_dir} and {compact_dir} to exist")
        sys.exit(1)

    print(f"Comparing {base.name}")
    print("=" * 50)

    # Line counts
    full_main = count_lines(full_dir / "main.go")
    compact_main = count_lines(compact_dir / "main.go")
    full_test = count_lines(full_dir / "main_test.go")
    compact_test = count_lines(compact_dir / "main_test.go")

    print("\nCode lines (main.go):")
    print(f"  Full:    {full_main}")
    print(f"  Compact: {compact_main}")

    print("\nTest lines (main_test.go):")
    print(f"  Full:    {full_test}")
    print(f"  Compact: {compact_test}")

    # Test results
    print("\nRunning tests...")
    full_passed, full_total = run_tests(full_dir)
    compact_passed, compact_total = run_tests(compact_dir)

    print("\nTest results:")
    print(f"  Full:    {full_passed}/{full_total} passed")
    print(f"  Compact: {compact_passed}/{compact_total} passed")

    # Verdict
    print("\n" + "=" * 50)
    if full_passed == full_total and compact_passed < compact_total:
        print("VERDICT: Full agent produced higher quality code")
    elif full_passed == full_total and compact_passed == compact_total:
        print("VERDICT: Both agents produced equivalent quality")
    else:
        print("VERDICT: Results inconclusive - manual review needed")


if __name__ == "__main__":
    main()
