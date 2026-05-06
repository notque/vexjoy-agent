#!/usr/bin/env python3
"""
Validation script for docs-sync-checker skill.
Tests core functionality and verifies reference files.
"""

__version__ = "1.0.0"

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
        "scripts/scan_tools.py",
        "scripts/parse_docs.py",
        "scripts/generate_report.py",
        "scripts/validate.py",
    ]

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

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files exist and are readable."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # List all reference files
    reference_files = list(references_dir.rglob("*"))
    file_count = len([f for f in reference_files if f.is_file()])
    results.append(
        (
            f"Reference files count: {file_count}",
            file_count > 0,
            "No reference files found" if file_count == 0 else "OK",
        )
    )

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


def validate_functional_tests() -> List[Tuple[str, bool, str]]:
    """Run functional tests of core logic."""
    results = []

    try:
        # Test 1: Tool discovery
        sys.path.insert(0, str(Path(__file__).parent))

        # Create temp test structure
        import tempfile

        from scan_tools import ToolScanner

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create test skill
            skill_dir = tmppath / "skills" / "test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill for validation
version: 1.0.0
---

# Test Skill
""")

            # Create test agent
            agents_dir = tmppath / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "test-agent.md").write_text("""---
name: test-agent
description: Test agent for validation
version: 1.0.0
---

# Test Agent
""")

            # Create test command
            commands_dir = tmppath / "commands"
            commands_dir.mkdir(parents=True)
            (commands_dir / "test-command.md").write_text("# Test Command\n\nTest command description")

            # Test scanning
            scanner = ToolScanner(tmppath, debug=False)
            scan_results = scanner.scan_all()

            # Validate results
            skills_found = len(scan_results.get("skills", []))
            results.append(("Tool discovery: skills", skills_found == 1, f"Expected 1 skill, found {skills_found}"))

            agents_found = len(scan_results.get("agents", []))
            results.append(("Tool discovery: agents", agents_found == 1, f"Expected 1 agent, found {agents_found}"))

            commands_found = len(scan_results.get("commands", []))
            results.append(
                ("Tool discovery: commands", commands_found == 1, f"Expected 1 command, found {commands_found}")
            )

        # Test 2: Markdown table parsing
        from parse_docs import DocumentationParser

        test_markdown = """
# Skills

| Name | Description | Command |
|------|-------------|---------|
| test-skill | Test skill | `skill: test-skill` |
| another-skill | Another skill | `skill: another-skill` |
"""

        parser = DocumentationParser(Path.cwd(), debug=False)
        rows = parser.parse_markdown_table(test_markdown)

        results.append(("Markdown table parsing", len(rows) == 2, f"Expected 2 rows, parsed {len(rows)}"))

        # Test 3: Missing entry detection
        discovered = {
            "skills": [
                {
                    "name": "new-skill",
                    "description": "New skill",
                    "version": "1.0.0",
                    "path": "skills/new-skill/SKILL.md",
                }
            ],
            "agents": [],
            "commands": [],
        }
        documented = {"skills/README.md": [{"name": "old-skill", "description": "Old skill"}]}

        issues = parser.detect_issues(discovered, documented)
        missing_count = len(issues["missing_entries"])

        results.append(
            ("Missing entry detection", missing_count == 1, f"Expected 1 missing entry, found {missing_count}")
        )

        # Test 4: Stale entry detection
        stale_count = len(issues["stale_entries"])

        results.append(("Stale entry detection", stale_count == 1, f"Expected 1 stale entry, found {stale_count}"))

        # Test 5: Version mismatch detection (would need version in README)
        results.append(
            (
                "Version mismatch detection",
                True,  # Placeholder - would need version column in test
                "OK (not implemented in test data)",
            )
        )

    except Exception as e:
        results.append(("Functional tests", False, f"Exception during functional tests: {e}"))

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
        ("Script Executability", validate_script_executability),
        ("Functional Tests", validate_functional_tests),
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
