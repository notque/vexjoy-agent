#!/usr/bin/env python3
"""
Validation script for skill-composer.
Validates skill compositions and execution DAGs.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


class ValidationError(Exception):
    """Validation related errors."""

    pass


def validate_dag_structure(dag: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Validate DAG structure is well-formed."""
    results = []

    # Check required fields
    required_fields = ["task", "phases", "dependencies", "execution_order"]
    for field in required_fields:
        exists = field in dag
        results.append(
            (
                f"DAG has required field: {field}",
                exists,
                f"Missing required field: {field}" if not exists else "OK",
            )
        )

    # Validate phases structure
    if "phases" in dag:
        phases = dag["phases"]
        if not isinstance(phases, list):
            results.append(
                (
                    "Phases is a list",
                    False,
                    f"Phases must be a list, got {type(phases)}",
                )
            )
        else:
            results.append(("Phases is a list", True, "OK"))

            # Check phase numbering
            for i, phase in enumerate(phases, 1):
                expected_num = i
                actual_num = phase.get("phase", -1)
                is_correct = expected_num == actual_num
                results.append(
                    (
                        f"Phase {i} numbered correctly",
                        is_correct,
                        f"Expected phase {expected_num}, got {actual_num}" if not is_correct else "OK",
                    )
                )

    return results


def validate_acyclic(dependencies: Dict[str, List[str]]) -> List[Tuple[str, bool, str]]:
    """Validate dependency graph is acyclic using DFS."""
    results = []

    def has_cycle() -> Tuple[bool, List[str]]:
        """Check for cycles using DFS."""
        visited = set()
        rec_stack = []

        def dfs(node: str) -> bool:
            if node in rec_stack:
                # Found cycle
                cycle_start = rec_stack.index(node)
                cycle = rec_stack[cycle_start:] + [node]
                return True, cycle

            if node in visited:
                return False, []

            visited.add(node)
            rec_stack.append(node)

            for neighbor in dependencies.get(node, []):
                has_cycle_result, cycle = dfs(neighbor)
                if has_cycle_result:
                    return True, cycle

            rec_stack.pop()
            return False, []

        for node in dependencies:
            if node not in visited:
                has_cycle_result, cycle = dfs(node)
                if has_cycle_result:
                    return True, cycle

        return False, []

    has_cycle_result, cycle = has_cycle()

    if has_cycle_result:
        cycle_str = " → ".join(cycle)
        results.append(("DAG is acyclic", False, f"Circular dependency detected: {cycle_str}"))
    else:
        results.append(("DAG is acyclic (no circular dependencies)", True, "OK"))

    return results


def validate_skill_existence(dag: Dict[str, Any], skill_index: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Validate all referenced skills exist in index."""
    results = []

    skill_map = skill_index.get("skill_map", {})
    selected_skills = dag.get("selected_skills", [])

    for skill_name in selected_skills:
        exists = skill_name in skill_map
        results.append(
            (
                f"Skill exists: {skill_name}",
                exists,
                f"Skill not found in index: {skill_name}" if not exists else "OK",
            )
        )

    return results


def validate_compatibility(dag: Dict[str, Any], skill_index: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Validate skill input/output compatibility."""
    results = []

    skill_map = skill_index.get("skill_map", {})
    dependencies = dag.get("dependencies", {})

    for skill_name, deps in dependencies.items():
        skill = skill_map.get(skill_name)
        if not skill:
            continue

        skill_inputs = set(skill.get("inputs", []))

        for dep_name in deps:
            dep = skill_map.get(dep_name)
            if not dep:
                continue

            dep_outputs = set(dep.get("outputs", []))

            # Check if any outputs match inputs
            compatible = bool(skill_inputs & dep_outputs) or not skill_inputs or not dep_outputs

            if compatible:
                results.append((f"Compatibility: {dep_name} → {skill_name}", True, "OK"))
            else:
                results.append(
                    (
                        f"Compatibility: {dep_name} → {skill_name}",
                        False,
                        f"No matching I/O: {dep_name} outputs {dep_outputs}, {skill_name} needs {skill_inputs}",
                    )
                )

    # If no dependencies, still pass
    if not dependencies:
        results.append(("No dependencies to validate", True, "OK"))

    return results


def validate_topological_ordering(dag: Dict[str, Any]) -> List[Tuple[str, bool, str]]:
    """Validate execution order satisfies dependencies."""
    results = []

    execution_order = dag.get("execution_order", [])
    dependencies = dag.get("dependencies", {})

    # Build position map
    position = {skill: i for i, skill in enumerate(execution_order)}

    # Check each dependency
    all_valid = True
    for skill, deps in dependencies.items():
        if skill not in position:
            continue

        skill_pos = position[skill]

        for dep in deps:
            if dep not in position:
                results.append(
                    (
                        f"Dependency ordering: {dep} → {skill}",
                        False,
                        f"Dependency {dep} not in execution order",
                    )
                )
                all_valid = False
                continue

            dep_pos = position[dep]

            if dep_pos < skill_pos:
                results.append((f"Dependency ordering: {dep} → {skill}", True, "OK"))
            else:
                results.append(
                    (
                        f"Dependency ordering: {dep} → {skill}",
                        False,
                        f"Dependency {dep} (pos {dep_pos}) must come before {skill} (pos {skill_pos})",
                    )
                )
                all_valid = False

    if all_valid:
        results.append(("Topological ordering valid", True, "OK"))

    return results


def validate_skill_composer() -> List[Tuple[str, bool, str]]:
    """Validate skill-composer skill structure."""
    results = []
    skill_dir = Path(__file__).parent.parent

    # Check required files
    required_files = [
        "SKILL.md",
        "scripts/discover_skills.py",
        "scripts/build_dag.py",
        "scripts/validate.py",
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

    # Check SKILL.md has operator context
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        has_operator = "## Operator Context" in content
        results.append(
            (
                "SKILL.md has Operator Context",
                has_operator,
                "Missing Operator Context section" if not has_operator else "OK",
            )
        )

        has_hardcoded = "### Hardcoded Behaviors" in content
        results.append(
            (
                "SKILL.md has Hardcoded Behaviors",
                has_hardcoded,
                "Missing Hardcoded Behaviors section" if not has_hardcoded else "OK",
            )
        )

    return results


def run_all_validations(dag: Dict[str, Any], skill_index: Dict[str, Any]) -> bool:
    """Run all validation checks."""
    all_results = []

    print("=" * 60)
    print("SKILL COMPOSITION VALIDATION")
    print("=" * 60)
    print()

    # Validation categories
    validations = [
        ("DAG Structure", lambda: validate_dag_structure(dag)),
        ("Acyclic Check", lambda: validate_acyclic(dag.get("dependencies", {}))),
        ("Skill Existence", lambda: validate_skill_existence(dag, skill_index)),
        ("I/O Compatibility", lambda: validate_compatibility(dag, skill_index)),
        ("Topological Ordering", lambda: validate_topological_ordering(dag)),
    ]

    all_passed = True

    for category, validation_func in validations:
        print(f"{category}:")
        print("-" * 60)
        results = validation_func()
        all_results.extend(results)

        for description, passed, message in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} - {description}")
            if not passed:
                print(f"         {message}")
                all_passed = False
        print()

    # Summary
    print("=" * 60)
    total_checks = len(all_results)
    passed_checks = sum(1 for _, passed, _ in all_results if passed)
    failed_checks = total_checks - passed_checks

    print(f"SUMMARY: {passed_checks}/{total_checks} checks passed")
    if failed_checks > 0:
        print(f"         {failed_checks} checks failed")
    else:
        print("         Composition valid - ready for execution")
    print("=" * 60)

    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate skill composition and DAG")
    parser.add_argument("--dag", type=Path, help="Path to DAG JSON file")
    parser.add_argument("--skill-index", type=Path, help="Path to skill index JSON file")
    parser.add_argument(
        "--self-validate",
        action="store_true",
        help="Validate skill-composer skill structure",
    )

    args = parser.parse_args()

    try:
        # Self-validation mode
        if args.self_validate:
            print("Running self-validation for skill-composer...\n", file=sys.stderr)
            results = validate_skill_composer()

            print("=" * 60)
            print("SKILL-COMPOSER SELF-VALIDATION")
            print("=" * 60)

            all_passed = True
            for description, passed, message in results:
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"{status} - {description}")
                if not passed:
                    print(f"       {message}")
                    all_passed = False

            total = len(results)
            passed = sum(1 for _, p, _ in results if p)
            print("\n" + "=" * 60)
            print(f"SUMMARY: {passed}/{total} checks passed")
            print("=" * 60)

            sys.exit(0 if all_passed else 1)

        # DAG validation mode
        if not args.dag or not args.skill_index:
            parser.error("--dag and --skill-index required (or use --self-validate)")

        # Load DAG
        if not args.dag.exists():
            raise ValidationError(f"DAG file not found: {args.dag}")

        with open(args.dag, "r", encoding="utf-8") as f:
            dag = json.load(f)

        # Load skill index
        if not args.skill_index.exists():
            raise ValidationError(f"Skill index not found: {args.skill_index}")

        with open(args.skill_index, "r", encoding="utf-8") as f:
            skill_index = json.load(f)

        # Run validations
        all_passed = run_all_validations(dag, skill_index)

        sys.exit(0 if all_passed else 1)

    except ValidationError as e:
        print(
            json.dumps(
                {"status": "error", "error_type": "ValidationError", "message": str(e)},
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps(
                {"status": "error", "error_type": type(e).__name__, "message": str(e)},
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
