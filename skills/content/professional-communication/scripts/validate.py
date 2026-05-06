#!/usr/bin/env python3
"""
Validation script for professional-communication skill.
Tests skill structure and reference files.
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
        "scripts/validate.py",
        "references/examples.md",
        "references/templates.md",
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
    required_fields = ["name:", "description:", "version:", "allowed-tools:"]
    for field in required_fields:
        if field in frontmatter:
            results.append((f"YAML field {field}", True, "OK"))
        else:
            results.append((f"YAML field {field}", False, f"Missing {field}"))

    # Validate name matches directory
    if "name: professional-communication" in frontmatter:
        results.append(("Skill name matches directory", True, "OK"))
    else:
        results.append(("Skill name matches directory", False, "Name mismatch"))

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files exist and are readable."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # Check specific reference files
    required_refs = ["examples.md", "templates.md"]
    for ref_file in required_refs:
        ref_path = references_dir / ref_file
        if ref_path.exists():
            # Check file is not empty
            size = ref_path.stat().st_size
            if size > 0:
                results.append((f"Reference file {ref_file}", True, f"OK ({size} bytes)"))
            else:
                results.append((f"Reference file {ref_file}", False, "File is empty"))
        else:
            results.append((f"Reference file {ref_file}", False, f"Missing {ref_file}"))

    return results


def validate_content_patterns() -> List[Tuple[str, bool, str]]:
    """Validate key content patterns exist in SKILL.md."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("Content validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for key sections
    required_sections = [
        "## Purpose",
        "## Operator Context",
        "## When to Use This Skill",
        "## Instructions",
        "## Status Indicator Reference",
        "## Common Transformation Patterns",
    ]

    for section in required_sections:
        if section in content:
            results.append((f"Section exists: {section}", True, "OK"))
        else:
            results.append((f"Section exists: {section}", False, "Missing section"))

    # Check for status indicators
    status_indicators = ["GREEN", "YELLOW", "RED"]
    for indicator in status_indicators:
        if indicator in content:
            results.append((f"Status indicator: {indicator}", True, "OK"))
        else:
            results.append((f"Status indicator: {indicator}", False, "Missing indicator"))

    return results


def validate_template_structure() -> List[Tuple[str, bool, str]]:
    """Validate template file has required templates."""
    results = []
    skill_dir = Path(__file__).parent.parent
    templates_file = skill_dir / "references" / "templates.md"

    if not templates_file.exists():
        return [("Template validation", False, "templates.md not found")]

    with open(templates_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for key templates
    required_templates = [
        "Standard Business Communication Template",
        "GREEN Status Template",
        "YELLOW Status Template",
        "RED Status Template",
        "Summary Section Structure",
        "Technical Details Section",
        "Next Steps Section",
    ]

    for template in required_templates:
        if template in content:
            results.append((f"Template exists: {template}", True, "OK"))
        else:
            results.append((f"Template exists: {template}", False, "Missing template"))

    return results


def run_all_validations() -> bool:
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
        ("Reference Files", validate_reference_files),
        ("Content Patterns", validate_content_patterns),
        ("Template Structure", validate_template_structure),
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
