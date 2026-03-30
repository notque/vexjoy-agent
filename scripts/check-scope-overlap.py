#!/usr/bin/env python3
"""Check file scope overlaps between parallel agent tasks.

Takes a list of tasks with file/directory scopes and detects conflicts,
then recommends parallelization groupings. Used by dispatching-parallel-agents
and parallel dispatch workflows to prevent merge conflicts.

Usage:
    python3 scripts/check-scope-overlap.py --tasks '[...]' --json
    python3 scripts/check-scope-overlap.py --tasks-file tasks.json --human
    python3 scripts/check-scope-overlap.py --tasks '[...]' --check

Exit codes:
    0 = success / no conflicts (with --check)
    1 = conflicts found (with --check)
    2 = input error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPT_NAME = "check-scope-overlap"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A single agent task with its file scope."""

    id: str
    scope: list[str]
    readonly: bool = False


@dataclass
class Conflict:
    """An overlap between two or more tasks."""

    tasks: list[str]
    overlap: list[str]


@dataclass
class AnalysisResult:
    """Full analysis output."""

    conflicts: list[Conflict] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Path normalization and overlap detection
# ---------------------------------------------------------------------------


def _normalize_scope_entry(entry: str) -> tuple[str, bool]:
    """Normalize a scope entry and determine if it represents a directory.

    Returns (normalized_path, is_directory).
    """
    is_dir = entry.endswith("/")
    normalized = entry.rstrip("/")
    return normalized, is_dir


def _paths_conflict(path_a: str, is_dir_a: bool, path_b: str, is_dir_b: bool) -> bool:
    """Determine if two scope entries conflict.

    Conflict rules:
    - Exact match (after normalization) = conflict
    - One is a parent directory of the other = conflict
    - Same directory, different files = no conflict
    """
    if path_a == path_b:
        return True

    # Check parent/child: if A is a directory, check if B is inside it
    if is_dir_a:
        # path_b starts with path_a/ means B is inside directory A
        if path_b.startswith(path_a + "/"):
            return True

    if is_dir_b:
        # path_a starts with path_b/ means A is inside directory B
        if path_a.startswith(path_b + "/"):
            return True

    # Both are directories: check parent/child relationship
    # (already handled above since we check both directions)

    return False


def _find_overlapping_paths(scope_a: list[str], scope_b: list[str]) -> list[str]:
    """Find all overlapping paths between two scopes.

    Returns the list of path expressions that cause the overlap.
    """
    overlaps: list[str] = []
    seen: set[str] = set()

    for entry_a in scope_a:
        norm_a, is_dir_a = _normalize_scope_entry(entry_a)
        for entry_b in scope_b:
            norm_b, is_dir_b = _normalize_scope_entry(entry_b)
            if _paths_conflict(norm_a, is_dir_a, norm_b, is_dir_b):
                # Report the more specific path, or the shared one
                if norm_a == norm_b:
                    overlap_key = entry_a
                elif norm_b.startswith(norm_a + "/"):
                    overlap_key = entry_b
                else:
                    overlap_key = entry_a
                if overlap_key not in seen:
                    seen.add(overlap_key)
                    overlaps.append(overlap_key)

    return sorted(overlaps)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def detect_conflicts(tasks: list[Task]) -> list[Conflict]:
    """Detect all pairwise conflicts between tasks.

    Read-only tasks never conflict with anything.
    """
    conflicts: list[Conflict] = []

    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            task_a = tasks[i]
            task_b = tasks[j]

            # Read-only tasks never conflict
            if task_a.readonly or task_b.readonly:
                continue

            overlaps = _find_overlapping_paths(task_a.scope, task_b.scope)
            if overlaps:
                conflicts.append(Conflict(tasks=[task_a.id, task_b.id], overlap=overlaps))

    return conflicts


# ---------------------------------------------------------------------------
# Parallel grouping
# ---------------------------------------------------------------------------


def build_conflict_graph(tasks: list[Task], conflicts: list[Conflict]) -> dict[str, set[str]]:
    """Build an adjacency set mapping task IDs to their conflicting task IDs."""
    graph: dict[str, set[str]] = {t.id: set() for t in tasks}
    for conflict in conflicts:
        a, b = conflict.tasks
        graph[a].add(b)
        graph[b].add(a)
    return graph


def compute_parallel_groups(tasks: list[Task], conflicts: list[Conflict]) -> list[list[str]]:
    """Greedily assign tasks to parallel groups.

    Each task is placed in the first group where it has no conflicts
    with any existing member. Tasks are processed in input order.
    """
    graph = build_conflict_graph(tasks, conflicts)
    groups: list[list[str]] = []

    for task in tasks:
        placed = False
        for group in groups:
            # Check if this task conflicts with any member of this group
            if not any(member in graph[task.id] for member in group):
                group.append(task.id)
                placed = True
                break
        if not placed:
            groups.append([task.id])

    return groups


# ---------------------------------------------------------------------------
# Recommendation text
# ---------------------------------------------------------------------------


def generate_recommendation(parallel_groups: list[list[str]]) -> str:
    """Generate a human-readable recommendation from parallel groups."""
    if len(parallel_groups) == 0:
        return "No tasks to schedule."

    if len(parallel_groups) == 1:
        group = parallel_groups[0]
        if len(group) == 1:
            return f"Run {group[0]} (single task, no parallelization needed)."
        return f"Run {', '.join(group[:-1])} and {group[-1]} in parallel. No conflicts detected."

    parts: list[str] = []
    for i, group in enumerate(parallel_groups):
        if len(group) == 1:
            parts.append(f"Run {group[0]} after group {i} completes." if i > 0 else f"Run {group[0]}.")
        else:
            task_list = f"{', '.join(group[:-1])} and {group[-1]}"
            if i == 0:
                parts.append(f"Run {task_list} in parallel.")
            else:
                parts.append(f"Then run {task_list} in parallel.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Analysis entry point
# ---------------------------------------------------------------------------


def analyze(tasks: list[Task]) -> AnalysisResult:
    """Run full scope overlap analysis."""
    conflicts = detect_conflicts(tasks)
    parallel_groups = compute_parallel_groups(tasks, conflicts)
    recommendation = generate_recommendation(parallel_groups)

    return AnalysisResult(
        conflicts=conflicts,
        parallel_groups=parallel_groups,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def parse_tasks(raw: str) -> list[Task]:
    """Parse JSON task list into Task objects.

    Raises ValueError on invalid input.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("expected a JSON array of tasks")

    if len(data) == 0:
        raise ValueError("task list is empty")

    tasks: list[Task] = []
    seen_ids: set[str] = set()

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"task at index {i} is not an object")

        task_id = item.get("id")
        if not task_id or not isinstance(task_id, str):
            raise ValueError(f"task at index {i} missing or invalid 'id'")

        if task_id in seen_ids:
            raise ValueError(f"duplicate task id: {task_id!r}")
        seen_ids.add(task_id)

        scope = item.get("scope")
        if not scope or not isinstance(scope, list):
            raise ValueError(f"task {task_id!r} missing or invalid 'scope'")

        for j, entry in enumerate(scope):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(f"task {task_id!r} scope[{j}] is not a non-empty string")

        readonly = item.get("readonly", False)
        if not isinstance(readonly, bool):
            raise ValueError(f"task {task_id!r} 'readonly' must be a boolean")

        tasks.append(Task(id=task_id, scope=scope, readonly=readonly))

    return tasks


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _result_to_dict(result: AnalysisResult) -> dict:
    """Convert AnalysisResult to a JSON-serializable dict."""
    return {
        "conflicts": [{"tasks": c.tasks, "overlap": c.overlap} for c in result.conflicts],
        "parallel_groups": result.parallel_groups,
        "recommendation": result.recommendation,
    }


def format_json(result: AnalysisResult) -> str:
    """Format result as JSON."""
    return json.dumps(_result_to_dict(result), indent=2)


def format_human(result: AnalysisResult) -> str:
    """Format result as human-readable text."""
    lines: list[str] = []

    if result.conflicts:
        lines.append(f"Conflicts found: {len(result.conflicts)}")
        lines.append("")
        for conflict in result.conflicts:
            lines.append(f"  {conflict.tasks[0]} <-> {conflict.tasks[1]}")
            for path in conflict.overlap:
                lines.append(f"    - {path}")
        lines.append("")
    else:
        lines.append("No conflicts found.")
        lines.append("")

    lines.append(f"Parallel groups: {len(result.parallel_groups)}")
    for i, group in enumerate(result.parallel_groups):
        lines.append(f"  Group {i + 1}: {', '.join(group)}")
    lines.append("")

    lines.append(f"Recommendation: {result.recommendation}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _die(message: str) -> int:
    """Print error and return exit code 2."""
    print(f"{_SCRIPT_NAME}: {message}", file=sys.stderr)
    return 2


def main() -> int:
    """Entry point for scope overlap checker."""
    parser = argparse.ArgumentParser(
        prog=_SCRIPT_NAME,
        description="Detect file scope overlaps between parallel agent tasks.",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--tasks", type=str, help="JSON array of tasks (inline)")
    input_group.add_argument("--tasks-file", type=str, help="Path to JSON file containing task array")

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Machine-readable JSON output (default)")
    output_group.add_argument("--human", action="store_true", help="Human-readable summary")
    output_group.add_argument("--check", action="store_true", help="Exit 0 if no conflicts, 1 if conflicts")

    args = parser.parse_args()

    # Load task JSON
    if args.tasks is not None:
        raw = args.tasks
    else:
        try:
            with open(args.tasks_file) as f:
                raw = f.read()
        except FileNotFoundError:
            return _die(f"file not found: {args.tasks_file}")
        except OSError as exc:
            return _die(f"cannot read file: {exc}")

    # Parse tasks
    try:
        tasks = parse_tasks(raw)
    except ValueError as exc:
        return _die(str(exc))

    # Analyze
    result = analyze(tasks)

    # Output
    if args.check:
        if result.conflicts:
            print(format_human(result))
            return 1
        return 0
    elif args.human:
        print(format_human(result))
    else:
        print(format_json(result))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
