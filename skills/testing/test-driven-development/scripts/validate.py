#!/usr/bin/env python3
"""
Validation script for test-driven-development skill.
Tests skill directory structure and verifies reference files.
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

    # Validate skill name matches directory
    skill_name_line = [line for line in frontmatter.split("\n") if line.startswith("name:")]
    if skill_name_line:
        skill_name = skill_name_line[0].split(":", 1)[1].strip()
        expected_name = "test-driven-development"
        if skill_name == expected_name:
            results.append(("Skill name matches directory", True, "OK"))
        else:
            results.append(
                (
                    "Skill name matches directory",
                    False,
                    f"Expected {expected_name}, got {skill_name}",
                )
            )

    # Check allowed-tools field
    allowed_tools_line = [line for line in frontmatter.split("\n") if line.startswith("allowed-tools:")]
    if allowed_tools_line:
        tools = allowed_tools_line[0].split(":", 1)[1].strip()
        required_tools = ["Read", "Write", "Bash", "Grep"]
        all_present = all(tool in tools for tool in required_tools)
        results.append(
            (
                "Required tools specified",
                all_present,
                f"Missing some of: {required_tools}" if not all_present else "OK",
            )
        )

    return results


def validate_operator_context() -> List[Tuple[str, bool, str]]:
    """Validate Operator Context section exists."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for Operator Context section
    if "## Operator Context" in content:
        results.append(("Operator Context section exists", True, "OK"))
    else:
        results.append(
            (
                "Operator Context section exists",
                False,
                "Missing Operator Context section",
            )
        )
        return results

    # Check for required subsections
    required_subsections = [
        "### Hardcoded Behaviors (Always Apply)",
        "### Default Behaviors (ON unless disabled)",
        "### Optional Behaviors (OFF unless enabled)",
    ]

    for subsection in required_subsections:
        if subsection in content:
            results.append((f"Subsection: {subsection[:30]}...", True, "OK"))
        else:
            results.append((f"Subsection: {subsection[:30]}...", False, f"Missing: {subsection}"))

    return results


def validate_tdd_workflow() -> List[Tuple[str, bool, str]]:
    """Validate TDD workflow instructions exist."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for RED-GREEN-REFACTOR workflow steps
    workflow_steps = [
        "Step 1: Write a Failing Test (RED Phase)",
        "Step 2: Verify Test Fails for the RIGHT Reason",
        "Step 3: Write MINIMUM Code to Pass (GREEN Phase)",
        "Step 4: Verify Test Passes (GREEN Verification)",
        "Step 5: Refactor While Keeping Tests Green",
        "Step 6: Commit Atomic Changes",
    ]

    for step in workflow_steps:
        if step in content:
            results.append((f"Workflow step: {step[:40]}...", True, "OK"))
        else:
            results.append((f"Workflow step: {step[:40]}...", False, f"Missing: {step}"))

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files exist and have content."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # Check examples.md exists and has substantial content
    examples_file = references_dir / "examples.md"
    if examples_file.exists():
        with open(examples_file, "r", encoding="utf-8") as f:
            content = f.read()
            word_count = len(content.split())

        if word_count > 500:
            results.append((f"examples.md has content ({word_count} words)", True, "OK"))
        else:
            results.append(
                (
                    f"examples.md has content ({word_count} words)",
                    False,
                    f"File too short: {word_count} words (expected >500)",
                )
            )

        # Check for language-specific examples
        languages = ["Go", "Python", "JavaScript"]
        for lang in languages:
            if lang in content:
                results.append((f"Examples include {lang}", True, "OK"))
            else:
                results.append((f"Examples include {lang}", False, f"Missing {lang} examples"))

    else:
        results.append(("examples.md exists", False, "Missing examples.md"))

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


def validate_content_quality() -> List[Tuple[str, bool, str]]:
    """Validate content quality and completeness."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for error handling section
    if "## Error Handling" in content:
        results.append(("Error Handling section exists", True, "OK"))
    else:
        results.append(("Error Handling section exists", False, "Missing Error Handling section"))

    # Check for language-specific commands
    languages = ["Go", "Python", "JavaScript"]
    for lang in languages:
        if lang in content or lang.lower() in content:
            results.append((f"Language support: {lang}", True, "OK"))
        else:
            results.append((f"Language support: {lang}", False, f"Missing {lang} support"))

    # Check for command examples
    if "```bash" in content:
        bash_count = content.count("```bash")
        results.append(
            (
                f"Command examples present ({bash_count} blocks)",
                bash_count >= 5,
                "Needs more command examples" if bash_count < 5 else "OK",
            )
        )

    # Check for code examples
    code_blocks = content.count("```")
    results.append(
        (
            f"Code examples present ({code_blocks // 2} blocks)",
            code_blocks >= 20,
            "Needs more code examples" if code_blocks < 20 else "OK",
        )
    )

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("TDD SKILL VALIDATION REPORT")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Operator Context", validate_operator_context),
        ("TDD Workflow", validate_tdd_workflow),
        ("Reference Files", validate_reference_files),
        ("Script Executability", validate_script_executability),
        ("Content Quality", validate_content_quality),
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
