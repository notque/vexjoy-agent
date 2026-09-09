#!/usr/bin/env python3
"""CLI for querying the durable task registry.

Usage:
  python3 scripts/task-registry.py list [--status incomplete|completed|dispatched|failed]
  python3 scripts/task-registry.py clear --older-than N  (days)
  python3 scripts/task-registry.py stats
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = Path.home() / ".claude" / "state" / "task-registry.json"


def load_registry() -> dict:
    try:
        if REGISTRY_PATH.exists():
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return data
    except Exception:
        pass
    return {"version": 1, "tasks": []}


def save_registry(registry: dict) -> None:
    import os
    import tempfile

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(REGISTRY_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(REGISTRY_PATH))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_list(args: argparse.Namespace) -> None:
    registry = load_registry()
    tasks = registry["tasks"]

    # Default: last 30 days
    now = datetime.now(tz=timezone.utc)
    cutoff = now.timestamp() - 30 * 86400
    filtered = []
    for t in tasks:
        try:
            dt = datetime.fromisoformat(t.get("dispatched_at", "").replace("Z", "+00:00"))
            if dt.timestamp() < cutoff:
                continue
        except Exception:
            pass
        if args.status:
            status = t.get("status")
            if args.status == "incomplete":
                if status not in ("dispatched", "failed"):
                    continue
            elif status != args.status:
                continue
        filtered.append(t)

    if not filtered:
        print("No tasks found.")
        return

    for t in filtered:
        status = t.get("status", "?")
        print(f"  {t.get('id', '?'):12s}  {status:11s}  {t.get('agent', '?'):30s}  {t.get('summary', '')[:60]}")


def cmd_clear(args: argparse.Namespace) -> None:
    if not args.older_than:
        print("Error: --older-than N required", file=sys.stderr)
        sys.exit(1)
    registry = load_registry()
    now = datetime.now(tz=timezone.utc)
    cutoff = now.timestamp() - args.older_than * 86400
    before = len(registry["tasks"])
    registry["tasks"] = [t for t in registry["tasks"] if _task_ts(t) >= cutoff]
    after = len(registry["tasks"])
    save_registry(registry)
    print(f"Pruned {before - after} tasks older than {args.older_than} days.")


def _task_ts(t: dict) -> float:
    try:
        return datetime.fromisoformat(t.get("dispatched_at", "").replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def cmd_stats(args: argparse.Namespace) -> None:
    registry = load_registry()
    tasks = registry["tasks"]
    total = len(tasks)
    by_status: dict[str, int] = {}
    for t in tasks:
        s = t.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    print(f"Total tasks: {total}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Task registry CLI")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list")
    p_list.add_argument("--status", default=None)

    p_clear = sub.add_parser("clear")
    p_clear.add_argument("--older-than", type=int, default=None)

    sub.add_parser("stats")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "clear":
        cmd_clear(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
