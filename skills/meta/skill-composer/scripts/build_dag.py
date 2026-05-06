#!/usr/bin/env python3
"""
DAG builder for skill composition.
Analyzes tasks and creates execution directed acyclic graphs.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


class DAGBuildError(Exception):
    """DAG building related errors."""

    pass


class SkillDAGBuilder:
    """Build execution DAG from task and skill index."""

    def __init__(self, skill_index: Dict[str, Any]):
        self.skill_index = skill_index
        self.skill_map = skill_index["skill_map"]

    def analyze_task(self, task_description: str) -> Dict[str, Any]:
        """Analyze task to identify required skills."""
        task_lower = task_description.lower()

        analysis = {
            "primary_goals": [],
            "quality_requirements": [],
            "domain_hints": [],
            "execution_hints": [],
        }

        # Identify primary goals
        if any(word in task_lower for word in ["add", "implement", "create", "build"]):
            analysis["primary_goals"].append("implementation")
        if any(word in task_lower for word in ["fix", "debug", "resolve", "repair"]):
            analysis["primary_goals"].append("debugging")
        if any(word in task_lower for word in ["analyze", "review", "examine", "investigate"]):
            analysis["primary_goals"].append("analysis")
        if any(word in task_lower for word in ["document", "comment", "explain"]):
            analysis["primary_goals"].append("documentation")

        # Identify quality requirements
        if any(word in task_lower for word in ["test", "tested", "testing"]):
            analysis["quality_requirements"].append("testing")
        if any(word in task_lower for word in ["verify", "validation", "check"]):
            analysis["quality_requirements"].append("verification")
        if any(word in task_lower for word in ["quality", "lint", "style"]):
            analysis["quality_requirements"].append("quality_checks")

        # Identify domain hints
        if "go" in task_lower or "golang" in task_lower:
            analysis["domain_hints"].append("golang")
        if any(word in task_lower for word in ["pr", "pull request", "review"]):
            analysis["domain_hints"].append("pr_review")
        if "workflow" in task_lower or "orchestrat" in task_lower:
            analysis["domain_hints"].append("workflow")

        # Identify execution hints
        if "and" in task_lower or "," in task_description:
            analysis["execution_hints"].append("multiple_steps")
        if any(word in task_lower for word in ["then", "after", "before"]):
            analysis["execution_hints"].append("sequential")
        if any(word in task_lower for word in ["also", "parallel", "simultaneously"]):
            analysis["execution_hints"].append("parallel")

        return analysis

    def select_skills(self, task_analysis: Dict[str, Any]) -> List[str]:
        """Select applicable skills based on task analysis."""
        selected = []

        # Map analysis to skill categories
        category_map = {
            "implementation": ["workflow", "testing"],
            "debugging": ["debugging"],
            "analysis": ["code-analysis"],
            "documentation": ["documentation"],
            "testing": ["testing"],
            "verification": ["quality"],
            "quality_checks": ["quality"],
        }

        # Collect applicable categories
        applicable_categories = set()
        for goal in task_analysis["primary_goals"]:
            applicable_categories.update(category_map.get(goal, []))
        for req in task_analysis["quality_requirements"]:
            applicable_categories.update(category_map.get(req, []))

        # Select skills from applicable categories
        categories = self.skill_index.get("categories", {})
        for category in applicable_categories:
            if category in categories:
                selected.extend(categories[category])

        # Remove duplicates while preserving order
        seen = set()
        unique_selected = []
        for skill in selected:
            if skill not in seen:
                seen.add(skill)
                unique_selected.append(skill)

        return unique_selected

    def build_dependency_graph(self, selected_skills: List[str]) -> Dict[str, List[str]]:
        """Build dependency graph from selected skills."""
        graph = {}

        for skill_name in selected_skills:
            skill = self.skill_map.get(skill_name)
            if not skill:
                continue

            # Get dependencies that are also selected
            deps = skill.get("dependencies", [])
            applicable_deps = [d for d in deps if d in selected_skills]

            if applicable_deps:
                graph[skill_name] = applicable_deps

        return graph

    def topological_sort(self, skills: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
        """Perform topological sort on skills."""
        # Build in-degree map
        in_degree = {skill: 0 for skill in skills}
        for skill, deps in dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[skill] += 1

        # Find skills with no dependencies
        queue = [skill for skill, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Process skill with no remaining dependencies
            skill = queue.pop(0)
            result.append(skill)

            # Reduce in-degree for dependent skills
            for dependent, deps in dependencies.items():
                if skill in deps:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Check if all skills were processed (DAG is valid)
        if len(result) != len(skills):
            unprocessed = set(skills) - set(result)
            raise DAGBuildError(f"Circular dependency detected. Unprocessed skills: {unprocessed}")

        return result

    def identify_parallel_phases(
        self, sorted_skills: List[str], dependencies: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """Identify which skills can run in parallel."""
        phases = []
        remaining = set(sorted_skills)
        processed = set()

        while remaining:
            # Find skills with all dependencies satisfied
            ready = []
            for skill in remaining:
                deps = dependencies.get(skill, [])
                if all(dep in processed for dep in deps):
                    ready.append(skill)

            if not ready:
                raise DAGBuildError(f"Cannot determine next phase. Remaining: {remaining}")

            # Create phase
            phase = {
                "phase": len(phases) + 1,
                "parallel": len(ready) > 1,
                "skills": ready,
            }
            phases.append(phase)

            # Update state
            remaining -= set(ready)
            processed.update(ready)

        return phases

    def build_dag(self, task_description: str) -> Dict[str, Any]:
        """Build complete execution DAG from task."""
        # Step 1: Analyze task
        task_analysis = self.analyze_task(task_description)

        # Step 2: Select applicable skills
        selected_skills = self.select_skills(task_analysis)

        if not selected_skills:
            raise DAGBuildError(f"No applicable skills found for task: {task_description}")

        # Step 3: Build dependency graph
        dependencies = self.build_dependency_graph(selected_skills)

        # Step 4: Topological sort
        sorted_skills = self.topological_sort(selected_skills, dependencies)

        # Step 5: Identify parallel execution opportunities
        phases = self.identify_parallel_phases(sorted_skills, dependencies)

        # Build final DAG
        dag = {
            "task": task_description,
            "task_analysis": task_analysis,
            "selected_skills": selected_skills,
            "dependencies": dependencies,
            "execution_order": sorted_skills,
            "phases": phases,
            "total_phases": len(phases),
            "parallel_phases": sum(1 for p in phases if p["parallel"]),
        }

        return dag


def detect_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    """Detect cycles in dependency graph using DFS."""
    cycles = []
    visited = set()
    rec_stack = []

    def dfs(node: str, path: List[str]):
        if node in rec_stack:
            # Found cycle
            cycle_start = rec_stack.index(node)
            cycle = rec_stack[cycle_start:] + [node]
            cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        rec_stack.append(node)

        for neighbor in graph.get(node, []):
            dfs(neighbor, path + [neighbor])

        rec_stack.pop()

    for node in graph:
        if node not in visited:
            dfs(node, [node])

    return cycles


def format_dag_output(dag: Dict[str, Any]) -> str:
    """Format DAG for human-readable display."""
    lines = [
        "=" * 60,
        "EXECUTION DAG",
        "=" * 60,
        "",
        f"Task: {dag['task']}",
        "",
        "Task Analysis:",
        f"  Primary goals: {', '.join(dag['task_analysis']['primary_goals'])}",
        f"  Quality requirements: {', '.join(dag['task_analysis']['quality_requirements'])}",
        "",
        f"Selected Skills ({len(dag['selected_skills'])}): {', '.join(dag['selected_skills'])}",
        "",
        "Execution Plan:",
        "",
    ]

    for phase in dag["phases"]:
        parallel_marker = " (PARALLEL)" if phase["parallel"] else ""
        lines.append(f"Phase {phase['phase']}{parallel_marker}:")
        for skill in phase["skills"]:
            lines.append(f"  → {skill}")
        lines.append("")

    lines.extend(
        [
            "Summary:",
            f"  Total phases: {dag['total_phases']}",
            f"  Parallel phases: {dag['parallel_phases']}",
            f"  Skills: {len(dag['selected_skills'])}",
            "=" * 60,
        ]
    )

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build execution DAG from task and skill index")
    parser.add_argument("--task", type=str, required=True, help="Task description")
    parser.add_argument("--skill-index", type=Path, required=True, help="Path to skill index JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output DAG JSON file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    try:
        # Load skill index
        if not args.skill_index.exists():
            raise DAGBuildError(f"Skill index not found: {args.skill_index}")

        with open(args.skill_index, "r", encoding="utf-8") as f:
            skill_index = json.load(f)

        # Build DAG
        print(f"Analyzing task: {args.task}", file=sys.stderr)
        builder = SkillDAGBuilder(skill_index)
        dag = builder.build_dag(args.task)

        # Check for cycles
        cycles = detect_cycles(dag["dependencies"])
        if cycles:
            cycle_strs = [" → ".join(cycle) for cycle in cycles]
            raise DAGBuildError("Circular dependencies detected:\n" + "\n".join(cycle_strs))

        # Write output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(dag, f, indent=2, ensure_ascii=False)

        print(f"\nDAG written to: {args.output}", file=sys.stderr)

        # Print formatted DAG
        print("\n" + format_dag_output(dag), file=sys.stderr)

        # Output success to stdout
        print(
            json.dumps(
                {
                    "status": "success",
                    "total_phases": dag["total_phases"],
                    "skills": len(dag["selected_skills"]),
                    "output_file": str(args.output),
                },
                indent=2,
            )
        )

    except DAGBuildError as e:
        print(
            json.dumps(
                {"status": "error", "error_type": "DAGBuildError", "message": str(e)},
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
