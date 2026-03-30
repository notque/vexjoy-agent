#!/usr/bin/env python3
"""
Validation script for go-patterns skill.
Tests skill structure and functionality.
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple


def validate_skill_structure() -> List[Tuple[str, bool, str]]:
    """Validate skill directory structure."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Check required files
    required_files = ["SKILL.md", "scripts/quality_checker.py", "scripts/validate.py"]

    for file_path in required_files:
        full_path = skill_dir / file_path
        exists = full_path.exists()
        results.append(
            (f"File exists: {file_path}", exists, f"Missing required file: {file_path}" if not exists else "OK")
        )

    return results


def validate_yaml_frontmatter() -> List[Tuple[str, bool, str]]:
    """Validate SKILL.md YAML frontmatter."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("YAML frontmatter validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for YAML frontmatter
    if not content.startswith("---"):
        results.append(("YAML frontmatter exists", False, "Missing opening ---"))
        return results

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        results.append(("YAML frontmatter format", False, "Missing closing ---"))
        return results

    frontmatter = parts[1].strip()

    # Check required fields
    required_fields = ["name:", "description:", "version:"]
    for field in required_fields:
        if field in frontmatter:
            results.append((f"YAML field {field}", True, "OK"))
        else:
            results.append((f"YAML field {field}", False, f"Missing {field}"))

    # Validate name
    if "name: go-patterns" in frontmatter:
        results.append(("Skill name correct", True, "OK"))
    else:
        results.append(("Skill name correct", False, "Expected 'go-patterns'"))

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files exist and are valid JSON."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # Expected reference files (now in sub-directories)
    expected_files = ["quality-gate/common-lint-errors.json", "quality-gate/makefile-targets.json"]

    for ref_file in expected_files:
        ref_path = references_dir / ref_file
        exists = ref_path.exists()

        if exists:
            # Validate JSON
            try:
                with open(ref_path, "r", encoding="utf-8") as f:
                    json.load(f)
                results.append((f"Reference file valid: {ref_file}", True, "OK"))
            except json.JSONDecodeError as e:
                results.append((f"Reference file valid: {ref_file}", False, f"Invalid JSON: {e}"))
        else:
            results.append((f"Reference file exists: {ref_file}", False, f"Missing reference file: {ref_file}"))

    return results


def validate_script_executability() -> List[Tuple[str, bool, str]]:
    """Validate scripts are executable."""
    results = []
    skill_dir = Path(__file__).parent.parent
    scripts_dir = skill_dir / "scripts"

    if not scripts_dir.exists():
        return [("Scripts directory", False, "scripts/ directory not found")]

    python_scripts = list(scripts_dir.glob("*.py"))
    for script in python_scripts:
        # Check if file has execute permissions
        is_executable = script.stat().st_mode & 0o111 != 0
        results.append(
            (
                f"Script executable: {script.name}",
                is_executable,
                f"Script not executable: {script.name}" if not is_executable else "OK",
            )
        )

    return results


def validate_script_imports() -> List[Tuple[str, bool, str]]:
    """Validate quality_checker.py can import required modules."""
    results = []

    try:
        # Test importing standard library modules used by quality_checker.py
        import argparse
        import json
        import os
        import re
        import subprocess
        import sys
        from pathlib import Path
        from typing import Any, Dict, List, Optional, Tuple

        results.append(("Required modules importable", True, "OK"))
    except ImportError as e:
        results.append(("Required modules importable", False, f"Import error: {e}"))

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("GO PATTERNS SKILL VALIDATION")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Reference Files", validate_reference_files),
        ("Script Executability", validate_script_executability),
        ("Script Imports", validate_script_imports),
    ]

    all_passed = True

    for category, validation_func in validations:
        print(f"\n{category}:")
        print("-" * 60)
        results = validation_func()
        all_results.extend(results)

        for description, passed, message in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} - {description}")
            if not passed:
                print(f"         {message}")
                all_passed = False

    # Summary
    print("\n" + "=" * 60)
    total_checks = len(all_results)
    passed_checks = sum(1 for _, passed, _ in all_results if passed)
    failed_checks = total_checks - passed_checks

    print(f"SUMMARY: {passed_checks}/{total_checks} checks passed")
    if failed_checks > 0:
        print(f"         {failed_checks} checks failed")
    print("=" * 60)

    return all_passed


def main():
    """Main entry point."""
    try:
        all_passed = run_all_validations()
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\nValidation error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
