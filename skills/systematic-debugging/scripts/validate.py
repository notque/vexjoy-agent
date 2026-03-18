#!/usr/bin/env python3
"""
Validation script for systematic-debugging skill.
Tests skill structure and validates reference files.
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
        "references/debugging-patterns.md",
        "references/tools.md",
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

    # Validate specific values
    if "name: systematic-debugging" in frontmatter:
        results.append(("Skill name correct", True, "OK"))
    else:
        results.append(("Skill name correct", False, "Expected 'systematic-debugging'"))

    if "version: 1.0.0" in frontmatter:
        results.append(("Version format correct", True, "OK"))
    else:
        results.append(("Version format correct", False, "Expected semantic version"))

    return results


def validate_operator_context() -> List[Tuple[str, bool, str]]:
    """Validate Operator Context section exists."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("Operator Context validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for Operator Context section
    if "## Operator Context" in content:
        results.append(("Operator Context section exists", True, "OK"))
    else:
        results.append(("Operator Context section exists", False, "Missing section"))
        return results

    # Check for required subsections
    required_sections = [
        "### Hardcoded Behaviors (Always Apply)",
        "### Default Behaviors (ON unless disabled)",
        "### Optional Behaviors (OFF unless enabled)",
    ]

    for section in required_sections:
        if section in content:
            results.append((f"Section present: {section}", True, "OK"))
        else:
            results.append((f"Section present: {section}", False, f"Missing {section}"))

    return results


def validate_4_phase_workflow() -> List[Tuple[str, bool, str]]:
    """Validate 4-phase debugging workflow is documented."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("4-phase workflow validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for all 4 phases
    phases = [
        "### Phase 1: REPRODUCE",
        "### Phase 2: ISOLATE",
        "### Phase 3: IDENTIFY",
        "### Phase 4: VERIFY",
    ]

    for phase in phases:
        if phase in content:
            results.append((f"Phase documented: {phase}", True, "OK"))
        else:
            results.append((f"Phase documented: {phase}", False, f"Missing {phase}"))

    # Check for critical hardcoded behaviors
    critical_behaviors = [
        "Reproduce First",
        "No Random Changes",
        "Document Every Step",
        "Verify Fixes",
        "Evidence Required",
    ]

    for behavior in critical_behaviors:
        # Allow variations in capitalization
        if behavior.lower() in content.lower():
            results.append((f"Critical behavior: {behavior}", True, "OK"))
        else:
            results.append(
                (f"Critical behavior: {behavior}", False, f"Missing {behavior}")
            )

    return results


def validate_reference_files() -> List[Tuple[str, bool, str]]:
    """Validate reference files exist and contain expected content."""
    results = []
    skill_dir = Path(__file__).parent.parent
    references_dir = skill_dir / "references"

    if not references_dir.exists():
        return [("References directory", False, "references/ directory not found")]

    results.append(("References directory exists", True, "OK"))

    # Check debugging-patterns.md
    patterns_file = references_dir / "debugging-patterns.md"
    if patterns_file.exists():
        results.append(("debugging-patterns.md exists", True, "OK"))

        with open(patterns_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for key patterns
        expected_patterns = [
            "Off-by-One Errors",
            "Null/None Pointer Errors",
            "Race Conditions",
            "Resource Leaks",
            "Incorrect Error Handling",
        ]

        for pattern in expected_patterns:
            if pattern in content:
                results.append((f"Pattern documented: {pattern}", True, "OK"))
            else:
                results.append(
                    (f"Pattern documented: {pattern}", False, f"Missing {pattern}")
                )
    else:
        results.append(
            ("debugging-patterns.md exists", False, "Missing patterns reference")
        )

    # Check tools.md
    tools_file = references_dir / "tools.md"
    if tools_file.exists():
        results.append(("tools.md exists", True, "OK"))

        with open(tools_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for key languages
        expected_languages = [
            "## Python",
            "## Go",
            "## JavaScript/Node.js",
            "## Java",
            "## C/C++",
            "## Rust",
        ]

        for lang in expected_languages:
            if lang in content:
                results.append((f"Language tools: {lang}", True, "OK"))
            else:
                results.append((f"Language tools: {lang}", False, f"Missing {lang}"))
    else:
        results.append(("tools.md exists", False, "Missing tools reference"))

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


def validate_skill_content_quality() -> List[Tuple[str, bool, str]]:
    """Validate skill content quality and completeness."""
    results = []
    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("Content quality validation", False, "SKILL.md not found")]

    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for essential sections
    essential_sections = [
        "## Purpose",
        "## When to Use This Skill",
        "## Instructions",
        "## Error Handling",
        "## Reference Files",
        "## Anti-Patterns to Avoid",
        "## Workflow Checkpoints",
        "## Success Metrics",
    ]

    for section in essential_sections:
        if section in content:
            results.append((f"Essential section: {section}", True, "OK"))
        else:
            results.append(
                (f"Essential section: {section}", False, f"Missing {section}")
            )

    # Check for code examples (bash and python)
    if "```bash" in content:
        bash_count = content.count("```bash")
        results.append(
            (
                f"Bash examples present: {bash_count}",
                bash_count >= 5,
                "OK"
                if bash_count >= 5
                else f"Only {bash_count} bash examples (expected 5+)",
            )
        )
    else:
        results.append(("Bash examples present", False, "No bash examples found"))

    if "```python" in content or "```markdown" in content:
        results.append(("Code examples present", True, "OK"))
    else:
        results.append(("Code examples present", False, "No code examples found"))

    # Check skill length (should be comprehensive)
    line_count = content.count("\n")
    results.append(
        (
            f"Skill length: {line_count} lines",
            line_count >= 400,
            "OK"
            if line_count >= 400
            else "Skill may be too brief (expected 400+ lines)",
        )
    )

    return results


def run_all_validations() -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("SYSTEMATIC DEBUGGING SKILL VALIDATION REPORT")
    print("=" * 60)
    print()

    # Run validation categories
    validations = [
        ("Skill Structure", validate_skill_structure),
        ("YAML Frontmatter", validate_yaml_frontmatter),
        ("Operator Context", validate_operator_context),
        ("4-Phase Workflow", validate_4_phase_workflow),
        ("Reference Files", validate_reference_files),
        ("Script Executability", validate_script_executability),
        ("Content Quality", validate_skill_content_quality),
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
