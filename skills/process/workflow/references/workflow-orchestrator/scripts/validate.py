#!/usr/bin/env python3
"""
Validation script for workflow-orchestrator skill.
Tests core functionality and verifies reference files.
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
    required_files = [
        "SKILL.md",
        "scripts/validate.py",
        "references/plan-template.md",
        "references/task-patterns.md",
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
    required_fields = ["name:", "description:", "version:", "allowed_tools:"]
    for field in required_fields:
        if field in frontmatter:
            results.append((f"YAML field {field}", True, "OK"))
        else:
            results.append((f"YAML field {field}", False, f"Missing {field}"))

    # Check skill name matches directory
    if "name: workflow-orchestrator" in frontmatter:
        results.append(("Skill name matches directory", True, "OK"))
    else:
        results.append(
            (
                "Skill name matches directory",
                False,
                "Name should be 'workflow-orchestrator'",
            )
        )

    # Check allowed tools
    expected_tools = ["Read", "Write", "Bash", "Grep", "Glob", "Task"]
    for tool in expected_tools:
        if tool in frontmatter:
            results.append((f"Allowed tool: {tool}", True, "OK"))
        else:
            results.append((f"Allowed tool: {tool}", False, f"Missing {tool} in allowed_tools"))

    return results


def validate_operator_context() -> List[Tuple[str, bool, str]]:
    """Validate Operator Context section in SKILL.md."""
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
            results.append((f"Subsection: {subsection}", True, "OK"))
        else:
            results.append((f"Subsection: {subsection}", False, f"Missing {subsection}"))

    # Check for hardcoded behaviors
    hardcoded_checks = [
        "Exact File Paths Required",
        "Verification Mandatory",
        "Task Duration",
    ]

    for check in hardcoded_checks:
        if check in content:
            results.append((f"Hardcoded behavior: {check}", True, "OK"))
        else:
            results.append(
                (
                    f"Hardcoded behavior: {check}",
                    False,
                    f"Missing hardcoded behavior: {check}",
                )
            )

    return results


def validate_workflow_phases() -> List[Tuple[str, bool, str]]:
    """Validate three-phase workflow documentation."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for three phases
    phases = [
        "### Phase 1: BRAINSTORM",
        "### Phase 2: WRITE-PLAN",
        "### Phase 3: EXECUTE-PLAN",
    ]

    for phase in phases:
        if phase in content:
            results.append((f"Workflow phase: {phase}", True, "OK"))
        else:
            results.append((f"Workflow phase: {phase}", False, f"Missing {phase}"))

    # Check brainstorm phase components
    brainstorm_checks = [
        "Understand Requirements",
        "Identify Constraints and Dependencies",
        "Generate Multiple Approaches",
        "Select Best Approach",
    ]

    for check in brainstorm_checks:
        if check in content:
            results.append((f"Brainstorm component: {check}", True, "OK"))
        else:
            results.append(
                (
                    f"Brainstorm component: {check}",
                    False,
                    f"Missing brainstorm component: {check}",
                )
            )

    # Check write-plan phase components
    plan_checks = [
        "Create Task Breakdown",
        "Identify Task Dependencies",
        "Define Verification Steps",
    ]

    for check in plan_checks:
        if check in content:
            results.append((f"Write-plan component: {check}", True, "OK"))
        else:
            results.append(
                (
                    f"Write-plan component: {check}",
                    False,
                    f"Missing write-plan component: {check}",
                )
            )

    # Check execute-plan phase components
    execute_checks = [
        "Load and Validate Plan",
        "Execute Tasks in Order",
        "Handle Verification Failures",
        "Handle Blockers",
        "Report Final Status",
    ]

    for check in execute_checks:
        if check in content:
            results.append((f"Execute-plan component: {check}", True, "OK"))
        else:
            results.append(
                (
                    f"Execute-plan component: {check}",
                    False,
                    f"Missing execute-plan component: {check}",
                )
            )

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files content."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Validate plan-template.md
    plan_template = skill_dir / "references" / "plan-template.md"
    if plan_template.exists():
        results.append(("Plan template file exists", True, "OK"))

        with open(plan_template, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for template examples
        template_checks = [
            "Template 1: Database Schema Change",
            "Template 2: API Endpoint Addition",
            "Template 3: Frontend Component Addition",
            "Template 4: Bug Fix with Regression Test",
            "Template 5: Configuration Change with Rollback",
        ]

        for check in template_checks:
            if check in content:
                results.append((f"Template: {check}", True, "OK"))
            else:
                results.append((f"Template: {check}", False, f"Missing template: {check}"))

        # Check for JSON plan examples
        if "```json" in content:
            results.append(("JSON plan examples present", True, "OK"))
        else:
            results.append(("JSON plan examples present", False, "Missing JSON plan examples"))

    else:
        results.append(("Plan template file exists", False, "Missing plan-template.md"))

    # Validate task-patterns.md
    task_patterns = skill_dir / "references" / "task-patterns.md"
    if task_patterns.exists():
        results.append(("Task patterns file exists", True, "OK"))

        with open(task_patterns, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for pattern categories
        pattern_checks = [
            "File Creation Patterns",
            "File Modification Patterns",
            "Database Patterns",
            "Testing Patterns",
            "Configuration Patterns",
            "Build & Deploy Patterns",
            "Validation Patterns",
        ]

        for check in pattern_checks:
            if check in content:
                results.append((f"Pattern category: {check}", True, "OK"))
            else:
                results.append(
                    (
                        f"Pattern category: {check}",
                        False,
                        f"Missing pattern category: {check}",
                    )
                )

        # Check for verification command patterns
        if "Verification Command Patterns" in content:
            results.append(("Verification command patterns section", True, "OK"))
        else:
            results.append(
                (
                    "Verification command patterns section",
                    False,
                    "Missing verification command patterns",
                )
            )

        # Check for task duration guidelines
        if "Task Duration Guidelines" in content:
            results.append(("Task duration guidelines section", True, "OK"))
        else:
            results.append(
                (
                    "Task duration guidelines section",
                    False,
                    "Missing task duration guidelines",
                )
            )

    else:
        results.append(("Task patterns file exists", False, "Missing task-patterns.md"))

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

        # Check for shebang
        with open(script, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            has_shebang = first_line.startswith("#!")
            results.append(
                (
                    f"Script has shebang: {script.name}",
                    has_shebang,
                    f"Missing shebang in {script.name}" if not has_shebang else "OK",
                )
            )

    return results


def validate_json_examples() -> List[Tuple[str, bool, str]]:
    """Validate JSON examples in reference files are valid."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Extract JSON examples from plan-template.md
    plan_template = skill_dir / "references" / "plan-template.md"
    if plan_template.exists():
        with open(plan_template, "r", encoding="utf-8") as f:
            content = f.read()

        # Find JSON code blocks
        json_blocks = []
        in_json_block = False
        current_block = []

        for line in content.split("\n"):
            if line.strip() == "```json":
                in_json_block = True
                current_block = []
            elif line.strip() == "```" and in_json_block:
                in_json_block = False
                json_blocks.append("\n".join(current_block))
            elif in_json_block:
                current_block.append(line)

        # Validate each JSON block
        for i, block in enumerate(json_blocks):
            try:
                json.loads(block)
                results.append((f"JSON example {i + 1} valid", True, "OK"))
            except json.JSONDecodeError as e:
                results.append((f"JSON example {i + 1} valid", False, f"Invalid JSON: {e}"))

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("WORKFLOW ORCHESTRATOR SKILL VALIDATION REPORT")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Operator Context", validate_operator_context),
        ("Workflow Phases", validate_workflow_phases),
        ("Reference Files", validate_reference_files),
        ("Script Executability", validate_script_executability),
        ("JSON Examples", validate_json_examples),
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
        import traceback

        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
