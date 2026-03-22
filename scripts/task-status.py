#!/usr/bin/env python3
"""Pipeline task status tracker — register, update, and display active tasks.

Tracks long-running parallel pipeline tasks via a shared JSON file,
providing visibility into what's running, how long it's taken, and
what has completed.

Usage:
    python3 scripts/task-status.py start "review" "Wave 1: 11 agents"
    python3 scripts/task-status.py update "review" "6/11 agents returned"
    python3 scripts/task-status.py done "review" "11/11 complete, 3 findings"
    python3 scripts/task-status.py show [--json] [--include-completed]
    python3 scripts/task-status.py clear

Exit codes:
    0 = success
    2 = usage error
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

STATUS_FILE = Path("/tmp/claude-toolkit-tasks.json")


def _with_lock(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that acquires a file lock for task store mutations."""

    @wraps(func)
    def wrapper(*args: Any, path: Path = STATUS_FILE, **kwargs: Any) -> Any:
        lock_path = path.with_suffix(".lock")
        try:
            lock_path.touch(exist_ok=True)
            lock_fd = open(lock_path)  # noqa: SIM115 — explicit close needed for lock lifecycle
        except OSError as e:
            print(f"Warning: cannot acquire lock: {e}", file=sys.stderr)
            return func(*args, path=path, **kwargs)  # proceed unlocked

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                return func(*args, path=path, **kwargs)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            lock_fd.close()

    return wrapper


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A tracked pipeline task."""

    name: str
    status: str
    started: str
    completed: bool = False
    ended: str | None = None
    elapsed_seconds: float | None = None


@dataclass
class TaskStore:
    """Container for all tracked tasks."""

    tasks: list[Task] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a datetime.

    Args:
        ts: ISO 8601 timestamp string (e.g. "2026-03-22T14:30:00Z").

    Returns:
        Timezone-aware datetime in UTC.
    """
    # Handle both "Z" suffix and "+00:00" format
    cleaned = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


def _load(path: Path) -> TaskStore:
    """Load task store from JSON file.

    Args:
        path: Path to the status JSON file.

    Returns:
        Populated TaskStore, or empty TaskStore if file doesn't exist.
    """
    if not path.exists():
        return TaskStore()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        tasks = [Task(**t) for t in raw.get("tasks", [])]
        return TaskStore(tasks=tasks)
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        print(f"Warning: corrupt task status file {path}, starting fresh: {e}", file=sys.stderr)
        return TaskStore()


def _save(store: TaskStore, path: Path) -> None:
    """Save task store to JSON file.

    Args:
        store: TaskStore to persist.
        path: Path to write the JSON file.

    Raises:
        OSError: If the file cannot be written.
    """
    data = {"tasks": [asdict(t) for t in store.tasks]}
    try:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"Error: could not save task status: {e}", file=sys.stderr)
        raise


def _find_task(store: TaskStore, name: str) -> Task | None:
    """Find a task by name.

    Args:
        store: TaskStore to search.
        name: Task name to find.

    Returns:
        Matching Task or None.
    """
    for task in store.tasks:
        if task.name == name:
            return task
    return None


def _elapsed_seconds(started: str) -> float:
    """Compute elapsed seconds from a start timestamp to now.

    Args:
        started: ISO 8601 start timestamp.

    Returns:
        Elapsed seconds as a float.
    """
    start_dt = _parse_iso(started)
    now_dt = datetime.now(timezone.utc)
    return (now_dt - start_dt).total_seconds()


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "45s", "2m 15s", or "1h 3m".
    """
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


@_with_lock
def cmd_start(name: str, status: str, *, path: Path = STATUS_FILE) -> int:
    """Register a new task, overwriting if it already exists.

    Args:
        name: Task name (unique identifier).
        status: Initial status text.
        path: Status file path.

    Returns:
        Exit code (always 0).
    """
    store = _load(path)
    # Remove existing task with same name
    store.tasks = [t for t in store.tasks if t.name != name]
    store.tasks.append(Task(name=name, status=status, started=_now_iso()))
    _save(store, path)
    return 0


@_with_lock
def cmd_update(name: str, status: str, *, path: Path = STATUS_FILE) -> int:
    """Update status text for a task, creating it if missing.

    Args:
        name: Task name.
        status: New status text.
        path: Status file path.

    Returns:
        Exit code (always 0).
    """
    store = _load(path)
    task = _find_task(store, name)
    if task is None:
        store.tasks.append(Task(name=name, status=status, started=_now_iso()))
    else:
        task.status = status
    _save(store, path)
    return 0


@_with_lock
def cmd_done(name: str, status: str, *, path: Path = STATUS_FILE) -> int:
    """Mark a task as completed with final status and elapsed time.

    Args:
        name: Task name.
        status: Final status text.
        path: Status file path.

    Returns:
        Exit code (always 0).
    """
    store = _load(path)
    task = _find_task(store, name)
    if task is None:
        # Create a completed task with zero elapsed
        task = Task(name=name, status=status, started=_now_iso(), completed=True, ended=_now_iso(), elapsed_seconds=0.0)
        store.tasks.append(task)
    else:
        task.status = status
        task.completed = True
        task.ended = _now_iso()
        task.elapsed_seconds = _elapsed_seconds(task.started)
    _save(store, path)
    return 0


def cmd_show(*, as_json: bool = False, include_completed: bool = False, path: Path = STATUS_FILE) -> int:
    """Display all tracked tasks.

    Args:
        as_json: Output JSON instead of human-readable format.
        include_completed: Include completed tasks in output.
        path: Status file path.

    Returns:
        Exit code (always 0).
    """
    store = _load(path)

    if as_json:
        tasks = store.tasks if include_completed else [t for t in store.tasks if not t.completed]
        output = []
        for task in tasks:
            entry = asdict(task)
            if not task.completed:
                try:
                    entry["elapsed_seconds"] = _elapsed_seconds(task.started)
                except (ValueError, OSError):
                    entry["elapsed_seconds"] = None
            output.append(entry)
        print(json.dumps({"tasks": output}, indent=2))
        return 0

    active = [t for t in store.tasks if not t.completed]
    completed = [t for t in store.tasks if t.completed]

    if not active and not (include_completed and completed):
        print("No active pipelines.")
        return 0

    if active:
        print("ACTIVE PIPELINES")
        name_width = max(len(t.name) for t in active)
        for task in active:
            try:
                elapsed = _format_duration(_elapsed_seconds(task.started))
            except (ValueError, OSError):
                elapsed = "unknown"
            print(f"  {task.name:<{name_width}}  {task.status:<40s} ({elapsed})")

    if include_completed and completed:
        if active:
            print()
        print("COMPLETED")
        name_width = max(len(t.name) for t in completed)
        for task in completed:
            elapsed = _format_duration(task.elapsed_seconds or 0)
            print(f"  {task.name:<{name_width}}  {task.status:<40s} ({elapsed})")

    return 0


@_with_lock
def cmd_clear(*, path: Path = STATUS_FILE) -> int:
    """Remove all tracked tasks.

    Args:
        path: Status file path.

    Returns:
        Exit code (always 0).
    """
    if path.exists():
        path.unlink()
    lock_path = path.with_suffix(".lock")
    if lock_path.exists():
        lock_path.unlink(missing_ok=True)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="task-status.py",
        description="Track status of long-running parallel pipeline tasks.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # start
    p_start = subparsers.add_parser("start", help="Register a new task")
    p_start.add_argument("name", help="Task name (unique identifier)")
    p_start.add_argument("status", help="Initial status text")

    # update
    p_update = subparsers.add_parser("update", help="Update task status text")
    p_update.add_argument("name", help="Task name")
    p_update.add_argument("status", help="New status text")

    # done
    p_done = subparsers.add_parser("done", help="Mark task as completed")
    p_done.add_argument("name", help="Task name")
    p_done.add_argument("status", help="Final status text")

    # show
    p_show = subparsers.add_parser("show", help="Display all tracked tasks")
    p_show.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    p_show.add_argument("--include-completed", action="store_true", help="Include completed tasks")

    # clear
    subparsers.add_parser("clear", help="Remove all tracked tasks")

    return parser


def main() -> int:
    """Entry point -- parse args and dispatch to subcommand handler."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        return 2

    match args.command:
        case "start":
            return cmd_start(args.name, args.status)
        case "update":
            return cmd_update(args.name, args.status)
        case "done":
            return cmd_done(args.name, args.status)
        case "show":
            return cmd_show(as_json=args.as_json, include_completed=args.include_completed)
        case "clear":
            return cmd_clear()
        case _:
            parser.print_help(sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
