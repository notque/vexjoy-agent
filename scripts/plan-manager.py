#!/usr/bin/env python3
"""
Deterministic plan management CLI.

Provides mechanical operations for plan management without LLM decision-making.
All output is structured JSON (default) or human-readable (--human flag).

Usage:
    python3 scripts/plan-manager.py list              # List active plans with age warnings
    python3 scripts/plan-manager.py list --all        # Include completed/abandoned
    python3 scripts/plan-manager.py list --stale      # Only plans older than 7 days

    python3 scripts/plan-manager.py show PLAN_NAME    # Show plan details + task status
    python3 scripts/plan-manager.py show PLAN_NAME --tasks  # Show unchecked tasks only

    python3 scripts/plan-manager.py check PLAN_NAME TASK_NUM    # Mark task [x] complete
    python3 scripts/plan-manager.py uncheck PLAN_NAME TASK_NUM  # Mark task [ ] incomplete

    python3 scripts/plan-manager.py complete PLAN_NAME              # Move to completed/YYYY-MM/
    python3 scripts/plan-manager.py abandon PLAN_NAME --reason "reason"  # Move to abandoned/

    python3 scripts/plan-manager.py create PLAN_NAME --title "Title"  # Create from template

    python3 scripts/plan-manager.py validate PLAN_NAME  # Check plan structure
    python3 scripts/plan-manager.py audit               # Audit all active plans for issues

Exit codes:
    0 = success
    1 = error
    2 = warnings (success with warnings)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Constants
STALENESS_THRESHOLD_DAYS = 7
PLAN_SUBDIRS = ["active", "completed", "abandoned"]


@dataclass
class PlanMetadata:
    """Parsed plan metadata."""

    status: str = ""
    created: date | None = None
    updated: date | None = None
    priority: str = ""
    complexity: str = ""
    title: str = ""
    abandoned_date: date | None = None
    abandoned_reason: str = ""


@dataclass
class Task:
    """A single task from the plan."""

    line_number: int
    text: str
    completed: bool
    phase: str = ""


@dataclass
class PlanInfo:
    """Complete plan information."""

    path: Path
    name: str
    metadata: PlanMetadata
    tasks: list[Task] = field(default_factory=list)
    raw_content: str = ""
    validation_errors: list[str] = field(default_factory=list)
    age_days: int = 0
    is_stale: bool = False


@dataclass
class Result:
    """Standard result format for all operations."""

    status: str  # "success", "error", "warning"
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {"status": self.status, "data": self.data}
        if self.warnings:
            result["warnings"] = self.warnings
        if self.errors:
            result["errors"] = self.errors
        return result


def find_plan_root() -> Path:
    """Find the plan directory root."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    plan_dir = repo_root / "plan"

    if not plan_dir.exists():
        plan_dir.mkdir(parents=True)
        for subdir in PLAN_SUBDIRS:
            (plan_dir / subdir).mkdir(exist_ok=True)

    return plan_dir


def parse_date(date_str: str) -> date | None:
    """Parse YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_plan_metadata(content: str) -> PlanMetadata:
    """Parse plan metadata from markdown content."""
    metadata = PlanMetadata()

    # Extract title from first heading
    title_match = re.search(r"^#\s+(?:Plan:\s*)?(.+)$", content, re.MULTILINE)
    if title_match:
        metadata.title = title_match.group(1).strip()

    # Parse key-value metadata
    patterns = {
        "status": r"\*\*Status\*\*:\s*(.+?)(?:\n|$)",
        "created": r"\*\*Created\*\*:\s*(\d{4}-\d{2}-\d{2})",
        "updated": r"\*\*Updated\*\*:\s*(\d{4}-\d{2}-\d{2})",
        "priority": r"\*\*Priority\*\*:\s*(.+?)(?:\n|$)",
        "complexity": r"\*\*Complexity\*\*:\s*(.+?)(?:\n|$)",
        "abandoned": r"\*\*Abandoned\*\*:\s*(\d{4}-\d{2}-\d{2})",
        "reason": r"\*\*Reason\*\*:\s*(.+?)(?:\n|$)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if key == "status":
                metadata.status = value
            elif key == "created":
                metadata.created = parse_date(value)
            elif key == "updated":
                metadata.updated = parse_date(value)
            elif key == "priority":
                metadata.priority = value
            elif key == "complexity":
                metadata.complexity = value
            elif key == "abandoned":
                metadata.abandoned_date = parse_date(value)
            elif key == "reason":
                metadata.abandoned_reason = value

    return metadata


def parse_tasks(content: str) -> list[Task]:
    """Parse tasks from plan content."""
    tasks: list[Task] = []
    lines = content.split("\n")
    current_phase = ""

    for i, line in enumerate(lines, start=1):
        # Track phase headings
        phase_match = re.match(r"^###?\s+(?:Phase\s+\d+[:\s]+)?(.+)$", line)
        if phase_match:
            current_phase = phase_match.group(1).strip()
            continue

        # Parse task lines
        task_match = re.match(r"^\s*-\s+\[([ xX])\]\s+(.+)$", line)
        if task_match:
            completed = task_match.group(1).lower() == "x"
            text = task_match.group(2).strip()
            tasks.append(
                Task(
                    line_number=i,
                    text=text,
                    completed=completed,
                    phase=current_phase,
                )
            )

    return tasks


def load_plan(plan_dir: Path, plan_name: str) -> PlanInfo | None:
    """Load a plan by name from any subdirectory."""
    # Normalize name
    if not plan_name.endswith(".md"):
        plan_name = f"{plan_name}.md"

    # Search in all subdirectories
    for subdir in ["active", "abandoned"]:
        plan_path = plan_dir / subdir / plan_name
        if plan_path.exists():
            return _load_plan_file(plan_path)

    # Check completed subdirectories (YYYY-MM structure)
    completed_dir = plan_dir / "completed"
    if completed_dir.exists():
        for month_dir in completed_dir.iterdir():
            if month_dir.is_dir():
                plan_path = month_dir / plan_name
                if plan_path.exists():
                    return _load_plan_file(plan_path)

    return None


def _load_plan_file(plan_path: Path) -> PlanInfo:
    """Load and parse a plan file."""
    content = plan_path.read_text(encoding="utf-8")
    metadata = parse_plan_metadata(content)
    tasks = parse_tasks(content)

    # Calculate age
    age_days = 0
    is_stale = False
    if metadata.created:
        age_days = (date.today() - metadata.created).days
        is_stale = age_days > STALENESS_THRESHOLD_DAYS

    return PlanInfo(
        path=plan_path,
        name=plan_path.stem,
        metadata=metadata,
        tasks=tasks,
        raw_content=content,
        age_days=age_days,
        is_stale=is_stale,
    )


def list_plans(plan_dir: Path, include_all: bool = False, stale_only: bool = False) -> list[PlanInfo]:
    """List plans based on filters."""
    plans: list[PlanInfo] = []

    # Always include active plans
    active_dir = plan_dir / "active"
    if active_dir.exists():
        for plan_file in active_dir.glob("*.md"):
            plan = _load_plan_file(plan_file)
            if stale_only and not plan.is_stale:
                continue
            plans.append(plan)

    # Include completed and abandoned if --all
    if include_all:
        # Abandoned
        abandoned_dir = plan_dir / "abandoned"
        if abandoned_dir.exists():
            for plan_file in abandoned_dir.glob("*.md"):
                plan = _load_plan_file(plan_file)
                if stale_only and not plan.is_stale:
                    continue
                plans.append(plan)

        # Completed (nested in YYYY-MM directories)
        completed_dir = plan_dir / "completed"
        if completed_dir.exists():
            for month_dir in completed_dir.iterdir():
                if month_dir.is_dir():
                    for plan_file in month_dir.glob("*.md"):
                        plan = _load_plan_file(plan_file)
                        if stale_only and not plan.is_stale:
                            continue
                        plans.append(plan)

    return plans


def validate_plan(plan: PlanInfo) -> list[str]:
    """Validate plan structure and return list of issues."""
    errors: list[str] = []

    # Required metadata
    if not plan.metadata.status:
        errors.append("Missing Status field")
    if not plan.metadata.created:
        errors.append("Missing or invalid Created date")
    if not plan.metadata.title:
        errors.append("Missing plan title")

    # Check for required sections
    required_sections = ["Requirements", "Implementation Tasks"]
    for section in required_sections:
        if f"## {section}" not in plan.raw_content:
            errors.append(f"Missing section: {section}")

    # Check for at least one task
    if not plan.tasks:
        errors.append("No tasks found (expected - [ ] or - [x] format)")

    return errors


def update_task_status(plan: PlanInfo, task_num: int, completed: bool) -> Result:
    """Update a task's completion status."""
    if task_num < 1 or task_num > len(plan.tasks):
        return Result(
            status="error",
            errors=[f"Task {task_num} not found. Plan has {len(plan.tasks)} tasks."],
        )

    task = plan.tasks[task_num - 1]  # Convert to 0-indexed
    current_status = task.completed
    new_marker = "[x]" if completed else "[ ]"
    old_marker = "[x]" if current_status else "[ ]"

    if current_status == completed:
        action = "already complete" if completed else "already incomplete"
        return Result(
            status="warning",
            data={"task_num": task_num, "task_text": task.text, "action": action},
            warnings=[f"Task {task_num} is {action}"],
        )

    # Read file and update the specific line
    lines = plan.raw_content.split("\n")
    line_idx = task.line_number - 1  # Convert to 0-indexed

    if line_idx < len(lines):
        # Replace the marker
        lines[line_idx] = lines[line_idx].replace(old_marker, new_marker, 1)

        # Also update the Updated date
        for i, line in enumerate(lines):
            if "**Updated**:" in line:
                lines[i] = f"**Updated**: {date.today().isoformat()}"
                break

        # Atomic write
        new_content = "\n".join(lines)
        _atomic_write(plan.path, new_content)

        action = "marked complete" if completed else "marked incomplete"
        return Result(
            status="success",
            data={
                "task_num": task_num,
                "task_text": task.text,
                "action": action,
                "plan": plan.name,
            },
        )

    return Result(status="error", errors=["Failed to locate task line in file"])


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically using temp file + rename."""
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(temp_path).replace(path)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise


def move_to_completed(plan: PlanInfo) -> Result:
    """Move plan to completed/YYYY-MM/ directory."""
    if "completed" in str(plan.path):
        return Result(status="warning", warnings=["Plan is already in completed directory"])

    # Create target directory
    today = date.today()
    target_dir = plan.path.parent.parent / "completed" / today.strftime("%Y-%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / plan.path.name

    if target_path.exists():
        return Result(status="error", errors=[f"Target file already exists: {target_path}"])

    # Update status in content
    content = plan.raw_content
    content = re.sub(
        r"(\*\*Status\*\*:\s*).+",
        r"\1Completed",
        content,
    )
    content = re.sub(
        r"(\*\*Updated\*\*:\s*).+",
        f"\\1{today.isoformat()}",
        content,
    )

    # Write to new location
    _atomic_write(target_path, content)

    # Remove old file
    plan.path.unlink()

    return Result(
        status="success",
        data={
            "plan": plan.name,
            "from": str(plan.path),
            "to": str(target_path),
        },
    )


def move_to_abandoned(plan: PlanInfo, reason: str) -> Result:
    """Move plan to abandoned directory with reason."""
    if "abandoned" in str(plan.path):
        return Result(status="warning", warnings=["Plan is already in abandoned directory"])

    target_dir = plan.path.parent.parent / "abandoned"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / plan.path.name

    if target_path.exists():
        return Result(status="error", errors=[f"Target file already exists: {target_path}"])

    # Update content with status, reason, and dates
    today = date.today()
    content = plan.raw_content
    content = re.sub(
        r"(\*\*Status\*\*:\s*).+",
        r"\1Abandoned",
        content,
    )
    content = re.sub(
        r"(\*\*Updated\*\*:\s*).+",
        f"\\1{today.isoformat()}",
        content,
    )

    # Add abandoned date and reason after Updated line
    if "**Abandoned**:" not in content:
        content = re.sub(
            r"(\*\*Updated\*\*:\s*.+\n)",
            f"\\1**Abandoned**: {today.isoformat()}\n**Reason**: {reason}\n",
            content,
        )

    # Write to new location
    _atomic_write(target_path, content)

    # Remove old file
    plan.path.unlink()

    return Result(
        status="success",
        data={
            "plan": plan.name,
            "reason": reason,
            "from": str(plan.path),
            "to": str(target_path),
        },
    )


def create_plan(plan_dir: Path, plan_name: str, title: str) -> Result:
    """Create a new plan from template."""
    # Normalize name
    if not plan_name.endswith(".md"):
        plan_name = f"{plan_name}.md"

    target_path = plan_dir / "active" / plan_name

    if target_path.exists():
        return Result(status="error", errors=[f"Plan already exists: {target_path}"])

    today = date.today()
    template = f"""# Plan: {title}

**Status**: Draft
**Created**: {today.isoformat()}
**Updated**: {today.isoformat()}
**Priority**: Medium
**Complexity**: Medium

## Summary

Brief description of what this plan accomplishes.

## Context

Why this plan exists and what problem it solves.

## Requirements

- [ ] Requirement 1
- [ ] Requirement 2

## Implementation Tasks

### Phase 1: Setup

- [ ] Task 1
- [ ] Task 2

### Phase 2: Implementation

- [ ] Task 3
- [ ] Task 4

## Dependencies

Any blockers or prerequisites.

## Verification

How to confirm the plan was successfully completed.

## Notes

Additional context, decisions made, or lessons learned.
"""

    target_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target_path, template)

    return Result(
        status="success",
        data={
            "plan": plan_name,
            "path": str(target_path),
            "title": title,
        },
    )


def audit_plans(plan_dir: Path) -> Result:
    """Audit all active plans for issues."""
    active_dir = plan_dir / "active"
    issues: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not active_dir.exists():
        return Result(status="success", data={"issues": [], "summary": "No active plans found"})

    for plan_file in active_dir.glob("*.md"):
        plan = _load_plan_file(plan_file)
        plan_issues: list[str] = []

        # Staleness check
        if plan.is_stale:
            plan_issues.append(f"Plan is {plan.age_days} days old (created {plan.metadata.created})")

        # Validation check
        validation_errors = validate_plan(plan)
        plan_issues.extend(validation_errors)

        # Task progress check
        total_tasks = len(plan.tasks)
        completed_tasks = sum(1 for t in plan.tasks if t.completed)
        if total_tasks > 0:
            completion_pct = (completed_tasks / total_tasks) * 100
            if completion_pct == 0:
                plan_issues.append(f"No tasks completed (0/{total_tasks})")
            elif completion_pct == 100 and plan.metadata.status.lower() not in ("completed", "done"):
                plan_issues.append(f"All tasks complete but status is '{plan.metadata.status}'")

        if plan_issues:
            issues.append(
                {
                    "plan": plan.name,
                    "path": str(plan.path),
                    "age_days": plan.age_days,
                    "issues": plan_issues,
                }
            )

    if issues:
        warnings.append(f"Found {len(issues)} plan(s) with issues")
        return Result(
            status="warning",
            data={"issues": issues, "plans_audited": len(list(active_dir.glob("*.md")))},
            warnings=warnings,
        )

    return Result(
        status="success",
        data={"issues": [], "plans_audited": len(list(active_dir.glob("*.md"))), "summary": "All plans OK"},
    )


def plan_to_dict(plan: PlanInfo) -> dict[str, Any]:
    """Convert PlanInfo to dictionary for JSON output."""
    completed_tasks = sum(1 for t in plan.tasks if t.completed)
    total_tasks = len(plan.tasks)

    return {
        "name": plan.name,
        "path": str(plan.path),
        "title": plan.metadata.title,
        "status": plan.metadata.status,
        "created": plan.metadata.created.isoformat() if plan.metadata.created else None,
        "updated": plan.metadata.updated.isoformat() if plan.metadata.updated else None,
        "priority": plan.metadata.priority,
        "complexity": plan.metadata.complexity,
        "age_days": plan.age_days,
        "is_stale": plan.is_stale,
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "remaining": total_tasks - completed_tasks,
            "progress_pct": round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1),
        },
    }


def format_human_output(result: Result, command: str) -> str:
    """Format result for human-readable output."""
    lines: list[str] = []

    if result.status == "error":
        lines.append(f"ERROR: {result.errors[0] if result.errors else 'Unknown error'}")
        return "\n".join(lines)

    if command == "list":
        plans = result.data.get("plans", [])
        if not plans:
            lines.append("No plans found.")
        else:
            lines.append(f"Found {len(plans)} plan(s):\n")
            for p in plans:
                stale_marker = " [STALE]" if p["is_stale"] else ""
                progress = f"{p['tasks']['completed']}/{p['tasks']['total']}"
                lines.append(f"  {p['name']}{stale_marker}")
                lines.append(f"    Status: {p['status']} | Progress: {progress} | Age: {p['age_days']}d")
                lines.append(f"    Path: {p['path']}")
                lines.append("")

    elif command == "show":
        p = result.data.get("plan", {})
        lines.append(f"Plan: {p.get('title', p.get('name', 'Unknown'))}")
        lines.append(f"Status: {p.get('status', 'Unknown')}")
        lines.append(f"Created: {p.get('created', 'Unknown')} ({p.get('age_days', 0)} days ago)")
        lines.append(f"Priority: {p.get('priority', 'Unknown')}")
        lines.append("")

        tasks = result.data.get("tasks", [])
        if tasks:
            lines.append("Tasks:")
            for i, t in enumerate(tasks, 1):
                marker = "[x]" if t["completed"] else "[ ]"
                phase_info = f" ({t['phase']})" if t.get("phase") else ""
                lines.append(f"  {i}. {marker} {t['text']}{phase_info}")
        else:
            lines.append("No tasks found.")

    elif command in ("check", "uncheck"):
        data = result.data
        lines.append(f"Task {data.get('task_num')}: {data.get('action')}")
        lines.append(f"  {data.get('task_text')}")

    elif command in ("complete", "abandon"):
        data = result.data
        action_word = "completed" if command == "complete" else "abandoned"
        lines.append(f"Plan '{data.get('plan')}' {action_word}")
        lines.append(f"  Moved to: {data.get('to')}")

    elif command == "create":
        data = result.data
        lines.append(f"Created plan: {data.get('plan')}")
        lines.append(f"  Path: {data.get('path')}")

    elif command == "validate":
        errors = result.data.get("errors", [])
        if errors:
            lines.append("Validation errors:")
            for e in errors:
                lines.append(f"  - {e}")
        else:
            lines.append("Plan structure is valid.")

    elif command == "audit":
        issues = result.data.get("issues", [])
        if issues:
            lines.append(f"Found issues in {len(issues)} plan(s):\n")
            for item in issues:
                lines.append(f"  {item['plan']} ({item['age_days']} days old)")
                for issue in item["issues"]:
                    lines.append(f"    - {issue}")
                lines.append("")
        else:
            lines.append("All active plans are OK.")

    # Add warnings
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    return "\n".join(lines)


def cmd_list(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle list command."""
    plans = list_plans(plan_dir, include_all=args.all, stale_only=args.stale)
    warnings: list[str] = []

    # Add staleness warnings
    for plan in plans:
        if plan.is_stale:
            warnings.append(f"Plan '{plan.name}' is {plan.age_days} days old")

    return Result(
        status="warning" if warnings else "success",
        data={"plans": [plan_to_dict(p) for p in plans]},
        warnings=warnings,
    )


def cmd_show(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle show command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    warnings: list[str] = []
    if plan.is_stale:
        warnings.append(f"Plan is {plan.age_days} days old (created {plan.metadata.created})")

    tasks = plan.tasks
    if args.tasks:
        tasks = [t for t in tasks if not t.completed]

    task_dicts = [
        {
            "num": i + 1,
            "text": t.text,
            "completed": t.completed,
            "phase": t.phase,
            "line": t.line_number,
        }
        for i, t in enumerate(plan.tasks)
        if not args.tasks or not t.completed
    ]

    return Result(
        status="warning" if warnings else "success",
        data={"plan": plan_to_dict(plan), "tasks": task_dicts},
        warnings=warnings,
    )


def cmd_check(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle check command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    return update_task_status(plan, args.task_num, completed=True)


def cmd_uncheck(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle uncheck command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    return update_task_status(plan, args.task_num, completed=False)


def cmd_complete(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle complete command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    return move_to_completed(plan)


def cmd_abandon(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle abandon command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    return move_to_abandoned(plan, args.reason)


def cmd_create(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle create command."""
    return create_plan(plan_dir, args.plan_name, args.title)


def cmd_validate(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle validate command."""
    plan = load_plan(plan_dir, args.plan_name)
    if not plan:
        return Result(status="error", errors=[f"Plan not found: {args.plan_name}"])

    errors = validate_plan(plan)
    if errors:
        return Result(
            status="error",
            data={"plan": plan.name, "errors": errors},
            errors=errors,
        )

    return Result(
        status="success",
        data={"plan": plan.name, "errors": [], "message": "Plan structure is valid"},
    )


def cmd_audit(args: argparse.Namespace, plan_dir: Path) -> Result:
    """Handle audit command."""
    return audit_plans(plan_dir)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    # Common parent parser for --human flag (allows it before or after subcommand)
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--human",
        action="store_true",
        help="Output human-readable format instead of JSON",
    )

    parser = argparse.ArgumentParser(
        description="Deterministic plan management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List plans", parents=[parent_parser])
    list_parser.add_argument("--all", action="store_true", help="Include completed and abandoned plans")
    list_parser.add_argument("--stale", action="store_true", help="Only show plans older than 7 days")

    # show command
    show_parser = subparsers.add_parser("show", help="Show plan details", parents=[parent_parser])
    show_parser.add_argument("plan_name", help="Plan name (with or without .md extension)")
    show_parser.add_argument("--tasks", action="store_true", help="Show only uncompleted tasks")

    # check command
    check_parser = subparsers.add_parser("check", help="Mark task as complete", parents=[parent_parser])
    check_parser.add_argument("plan_name", help="Plan name")
    check_parser.add_argument("task_num", type=int, help="Task number (1-indexed)")

    # uncheck command
    uncheck_parser = subparsers.add_parser("uncheck", help="Mark task as incomplete", parents=[parent_parser])
    uncheck_parser.add_argument("plan_name", help="Plan name")
    uncheck_parser.add_argument("task_num", type=int, help="Task number (1-indexed)")

    # complete command
    complete_parser = subparsers.add_parser("complete", help="Move plan to completed", parents=[parent_parser])
    complete_parser.add_argument("plan_name", help="Plan name")

    # abandon command
    abandon_parser = subparsers.add_parser("abandon", help="Move plan to abandoned", parents=[parent_parser])
    abandon_parser.add_argument("plan_name", help="Plan name")
    abandon_parser.add_argument("--reason", required=True, help="Reason for abandoning")

    # create command
    create_parser = subparsers.add_parser("create", help="Create new plan from template", parents=[parent_parser])
    create_parser.add_argument("plan_name", help="Plan name (will be kebab-cased)")
    create_parser.add_argument("--title", required=True, help="Plan title")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate plan structure", parents=[parent_parser])
    validate_parser.add_argument("plan_name", help="Plan name")

    # audit command
    subparsers.add_parser("audit", help="Audit all active plans for issues", parents=[parent_parser])

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    plan_dir = find_plan_root()

    # Dispatch to command handler
    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "check": cmd_check,
        "uncheck": cmd_uncheck,
        "complete": cmd_complete,
        "abandon": cmd_abandon,
        "create": cmd_create,
        "validate": cmd_validate,
        "audit": cmd_audit,
    }

    handler = handlers.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    try:
        result = handler(args, plan_dir)
    except Exception as e:
        result = Result(status="error", errors=[str(e)])

    # Output
    if args.human:
        print(format_human_output(result, args.command))
    else:
        print(json.dumps(result.to_dict(), indent=2))

    # Exit code
    if result.status == "error":
        return 1
    elif result.status == "warning":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
