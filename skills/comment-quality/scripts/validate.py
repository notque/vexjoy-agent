#!/usr/bin/env python3
"""
Validation script for comment-quality skill.
Tests core functionality and verifies reference files.
"""

import sys
from pathlib import Path


def validate_skill_structure() -> list[tuple[str, bool, str]]:
    """Validate skill directory structure."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Check required files
    required_files = [
        "SKILL.md",
        "references/temporal-keywords.txt",
        "references/examples.md",
        "references/anti-patterns.md",
    ]

    for file_path in required_files:
        full_path = skill_dir / file_path
        exists = full_path.exists()
        results.append(
            (
                f"File exists: {file_path}",
                exists,
                f"Missing required file: {file_path}" if not exists else "OK",
            )
        )

    return results


def validate_yaml_frontmatter() -> list[tuple[str, bool, str]]:
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

    # Validate skill name
    if "name: comment-quality" in frontmatter:
        results.append(("Skill name correct", True, "OK"))
    else:
        results.append(
            ("Skill name correct", False, "Name should be 'comment-quality'")
        )

    return results


def validate_reference_files() -> list[tuple[str, bool, str]]:
    """Validate reference files exist and contain required content."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # Validate temporal-keywords.txt content
    keywords_file = references_dir / "temporal-keywords.txt"
    if keywords_file.exists():
        with open(keywords_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Check for key temporal words
            key_words = ["new", "old", "fixed", "updated", "improved"]
            found_words = sum(1 for word in key_words if word in content.lower())
            if found_words >= 4:
                results.append(("temporal-keywords.txt has key words", True, "OK"))
            else:
                results.append(
                    (
                        "temporal-keywords.txt has key words",
                        False,
                        f"Only found {found_words}/5 key temporal words",
                    )
                )
    else:
        results.append(
            ("temporal-keywords.txt exists", False, "Missing temporal-keywords.txt")
        )

    # Validate examples.md content
    examples_file = references_dir / "examples.md"
    if examples_file.exists():
        with open(examples_file, "r", encoding="utf-8") as f:
            content = f.read()
            has_bad_good = "# Bad:" in content and "# Good:" in content
            results.append(
                (
                    "examples.md has Bad/Good examples",
                    has_bad_good,
                    "Missing Bad/Good example format" if not has_bad_good else "OK",
                )
            )
    else:
        results.append(("examples.md exists", False, "Missing examples.md"))

    # Validate anti-patterns.md content
    antipatterns_file = references_dir / "anti-patterns.md"
    if antipatterns_file.exists():
        with open(antipatterns_file, "r", encoding="utf-8") as f:
            content = f.read()
            has_patterns = "Anti-Pattern" in content
            results.append(
                (
                    "anti-patterns.md has patterns",
                    has_patterns,
                    "Missing anti-pattern content" if not has_patterns else "OK",
                )
            )
    else:
        results.append(("anti-patterns.md exists", False, "Missing anti-patterns.md"))

    return results


def validate_operator_context() -> list[tuple[str, bool, str]]:
    """Validate Operator Context section exists in SKILL.md."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("Operator Context validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for Operator Context section
    has_operator = "## Operator Context" in content
    results.append(
        (
            "Operator Context section exists",
            has_operator,
            "Missing Operator Context section" if not has_operator else "OK",
        )
    )

    # Check for behavior sections
    behavior_sections = [
        "Hardcoded Behaviors",
        "Default Behaviors",
        "Optional Behaviors",
    ]

    for section in behavior_sections:
        has_section = section in content
        results.append(
            (
                f"{section} section exists",
                has_section,
                f"Missing {section} section" if not has_section else "OK",
            )
        )

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("COMMENT QUALITY SKILL VALIDATION REPORT")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Reference Files", validate_reference_files),
        ("Operator Context", validate_operator_context),
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
