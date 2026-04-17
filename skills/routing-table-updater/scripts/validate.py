#!/usr/bin/env python3
"""
Validation script for routing-table-updater skill.
Tests routing table integrity and skill structure.
"""

import sys
from pathlib import Path
from typing import List, Tuple


def validate_skill_structure() -> List[Tuple[str, bool, str]]:
    """Validate skill directory structure."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Check required files
    required_files = [
        "SKILL.md",
        "scripts/scan.py",
        "scripts/extract_metadata.py",
        "scripts/generate_routes.py",
        "scripts/update_routing.py",
        "scripts/validate.py",
    ]

    for file_path in required_files:
        full_path = skill_dir / file_path
        exists = full_path.exists()
        results.append(
            (f"File exists: {file_path}", exists, f"Missing required file: {file_path}" if not exists else "OK")
        )

    # Check reference files
    ref_files = [
        "references/routing-format.md",
        "references/extraction-patterns.md",
        "references/conflict-resolution.md",
        "references/examples.md",
    ]

    for file_path in ref_files:
        full_path = skill_dir / file_path
        exists = full_path.exists()
        results.append(
            (
                f"Reference file exists: {file_path}",
                exists,
                f"Missing reference file: {file_path}" if not exists else "OK",
            )
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
    required_fields = ["name:", "description:"]
    for field in required_fields:
        if field in frontmatter:
            results.append((f"YAML field {field}", True, "OK"))
        else:
            results.append((f"YAML field {field}", False, f"Missing {field}"))

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


def validate_routing_table_target(target_path: Path = None) -> List[Tuple[str, bool, str]]:
    """
    Validate commands/do.md routing tables.

    If target_path provided, validates that file.
    Otherwise validates default location.
    """
    results = []

    if target_path is None:
        # Default to agents repo structure
        skill_dir = Path(__file__).parent.parent
        repo_root = skill_dir.parent.parent
        target_path = repo_root / "commands" / "do.md"

    if not target_path.exists():
        results.append(("Target routing file exists", False, f"Target file not found: {target_path}"))
        return results

    results.append(("Target routing file exists", True, "OK"))

    # Read file content
    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for expected routing table headers
    expected_tables = [
        "### Intent Detection Patterns",
        "### Task Type Routing",
        "### Domain-Specific Routing",
        "### Combination Routing",
    ]

    for table_header in expected_tables:
        if table_header in content:
            results.append((f"Table found: {table_header}", True, "OK"))
        else:
            results.append((f"Table found: {table_header}", False, f"Table header not found in do.md: {table_header}"))

    # Count auto-generated markers
    auto_gen_count = content.count("[AUTO-GENERATED]")
    results.append((f"Auto-generated entries: {auto_gen_count}", True, "OK"))

    # Validate table syntax (basic check)
    lines = content.split("\n")
    table_errors = 0

    for _line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            # Check for basic pipe structure
            if not stripped.endswith("|"):
                table_errors += 1

    results.append(
        (
            "Table syntax validation",
            table_errors == 0,
            f"Found {table_errors} table syntax errors" if table_errors > 0 else "OK",
        )
    )

    return results


def run_all_validations(target_path: Path = None) -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("SKILL VALIDATION REPORT")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Script Executability", validate_script_executability),
    ]

    # Add routing table validation if target specified
    if target_path:
        validations.append(("Routing Table Target", lambda: validate_routing_table_target(target_path)))

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
    import argparse

    parser = argparse.ArgumentParser(description="Validate routing-table-updater skill")
    parser.add_argument("--target", type=Path, help="Optional commands/do.md file path to validate")

    args = parser.parse_args()

    try:
        all_passed = run_all_validations(args.target)
        sys.exit(0 if all_passed else 1)
    except Exception as e:
        print(f"\nValidation error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
