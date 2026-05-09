#!/usr/bin/env python3
"""Assemble a workflow plan from a JSON template and parameters.

Reads the plan template and example plans from co-located templates/ directory.
Outputs assembled plan JSON to stdout or a file.

Usage:
    python3 assemble-plan.py --list
    python3 assemble-plan.py --example db-schema
    python3 assemble-plan.py --category DB --number 001 --description "Add table"
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"

# Pre-built example plans matching the original plan-template.md content
EXAMPLES = {
    "db-schema": {
        "plan_id": "PLAN_DB_001",
        "description": "Add user_preferences table with migration",
        "approach": "Django-style migration with backward compatibility",
        "estimated_total_time": "14 minutes",
        "task_count": 4,
        "pattern": "T1 -> T2 -> T3 -> T4 (linear)",
    },
    "api-endpoint": {
        "plan_id": "PLAN_API_001",
        "description": "Add GET /api/v1/user/preferences endpoint",
        "approach": "Flask blueprint with JWT authentication",
        "estimated_total_time": "13 minutes",
        "task_count": 4,
        "pattern": "T1 -> T2 -> T3 -> T4 (linear)",
    },
    "frontend-component": {
        "plan_id": "PLAN_FE_001",
        "description": "Add UserPreferencePanel component",
        "approach": "React functional component with hooks",
        "estimated_total_time": "16 minutes",
        "task_count": 4,
        "pattern": "T1 -> T2 -> T4, T1 -> T3 (diamond)",
    },
    "bug-fix": {
        "plan_id": "PLAN_BUG_001",
        "description": "Fix user preference persistence on logout",
        "approach": "Add beforeunload event handler to save preferences",
        "estimated_total_time": "12 minutes",
        "task_count": 3,
        "pattern": "T1 -> T2 -> T3 (linear, test-first)",
    },
    "config-change": {
        "plan_id": "PLAN_CONFIG_001",
        "description": "Add nginx route for /api/v2/preferences",
        "approach": "Update nginx config with backup and validation",
        "estimated_total_time": "9 minutes",
        "task_count": 4,
        "pattern": "T1 -> T2 -> T3 -> T4 (linear with backup)",
    },
}

GUIDELINES = """
Plan Structure Guidelines:

Essential Elements:
  1. plan_id:  Unique identifier (format: PLAN_[CATEGORY]_[NUMBER])
  2. description:  One-line summary
  3. approach:  High-level strategy
  4. estimated_total_time:  Sum of all task durations
  5. tasks:  Array of task objects
  6. dependencies:  Object mapping dependent tasks to prerequisites

Task Object Requirements:
  1. task_id, title, estimated_duration, dependencies
  2. files (absolute paths), operations (specific steps)
  3. verification (command + expected_output + success_criteria)
  4. rollback (description + commands)

Verification Best Practices:
  + python manage.py check, npm test -- Component, nginx -t
  - No verification, ls file.py, echo "OK"

Rollback Best Practices:
  + rm new_file.py, git checkout file.py, cp backup original
  - No rollback, destructive without backup
"""


def list_examples():
    print("Available example plan templates:")
    print()
    for name, info in sorted(EXAMPLES.items()):
        print(f"  {name:<20} {info['description']}")
        print(f"  {'':20} Tasks: {info['task_count']}, Pattern: {info['pattern']}")
        print()
    print("Usage: python3 assemble-plan.py --example <name>")
    print()
    print("To create a new plan skeleton:")
    print('  python3 assemble-plan.py --category DB --number 002 --description "..."')


def show_example(name: str):
    if name not in EXAMPLES:
        print(f"Error: unknown example '{name}'. Use --list to see options.", file=sys.stderr)
        sys.exit(1)

    # Load the full example from the template file
    template_path = TEMPLATES_DIR / f"example-{name}.json"
    if template_path.exists():
        print(template_path.read_text())
    else:
        # Output the summary
        info = EXAMPLES[name]
        print(json.dumps(info, indent=2))
        print()
        print(f"Full template at: {template_path} (generate with --generate-examples)")


def create_skeleton(args):
    """Create a minimal plan skeleton from parameters."""
    plan = {
        "plan_id": f"PLAN_{args.category}_{args.number}",
        "description": args.description,
        "approach": args.approach or "TODO: describe approach",
        "estimated_total_time": args.time or "TODO",
        "tasks": [],
        "dependencies": {},
    }

    # Generate task stubs
    task_count = args.tasks or 3
    for i in range(1, task_count + 1):
        task = {
            "task_id": f"T{i}",
            "title": f"TODO: Task {i} title",
            "estimated_duration": "3 minutes",
            "dependencies": [f"T{i - 1}"] if i > 1 else [],
            "files": [],
            "operations": ["TODO: describe operations"],
            "verification": {
                "command": "TODO",
                "expected_output": "TODO",
                "success_criteria": "TODO",
            },
            "rollback": {
                "description": "TODO",
                "commands": [],
            },
        }
        plan["tasks"].append(task)
        if i > 1:
            plan["dependencies"][f"T{i}"] = [f"T{i - 1}"]

    output = json.dumps(plan, indent=2)
    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Assemble workflow plans from templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=GUIDELINES,
    )
    parser.add_argument("--list", action="store_true", help="List available example plans")
    parser.add_argument("--example", help="Show a specific example plan")
    parser.add_argument("--guidelines", action="store_true", help="Show plan structure guidelines")
    parser.add_argument("--category", help="Plan category (e.g., DB, API, FE, BUG, CONFIG)")
    parser.add_argument("--number", default="001", help="Plan number (default: 001)")
    parser.add_argument("--description", help="Plan description")
    parser.add_argument("--approach", help="High-level approach")
    parser.add_argument("--time", help="Estimated total time")
    parser.add_argument("--tasks", type=int, help="Number of task stubs to generate")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if args.list:
        list_examples()
        return

    if args.guidelines:
        print(GUIDELINES)
        return

    if args.example:
        show_example(args.example)
        return

    if not args.category:
        parser.error("--category is required (use --list for examples, --guidelines for structure)")

    if not args.description:
        parser.error("--description is required")

    create_skeleton(args)


if __name__ == "__main__":
    main()
