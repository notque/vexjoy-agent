#!/usr/bin/env python3
"""
Check for wedged subagents that have been active too long.

Reads ~/.claude/state/subagent-registry.json and flags agents still
marked "active" beyond a configurable threshold.

Env:
  VEXJOY_WEDGE_THRESHOLD_MINUTES  default 30

Always exits 0 (informational).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_STATE_FILE = Path.home() / ".claude" / "state" / "subagent-registry.json"


def main() -> None:
    threshold_min = int(os.environ.get("VEXJOY_WEDGE_THRESHOLD_MINUTES", "30"))

    if not _STATE_FILE.exists():
        print("No subagent registry found. No wedged agents.")
        return

    try:
        state = json.loads(_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Cannot read registry: {e}")
        return

    now = datetime.now(timezone.utc)
    wedged = []

    for agent_id, entry in state.get("agents", {}).items():
        if entry.get("status") != "active":
            continue
        started = entry.get("started", "")
        if not started:
            wedged.append((agent_id, entry, None))
            continue
        try:
            start_dt = datetime.fromisoformat(started)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            elapsed = (now - start_dt).total_seconds() / 60
            if elapsed > threshold_min:
                wedged.append((agent_id, entry, elapsed))
        except (ValueError, TypeError):
            wedged.append((agent_id, entry, None))

    if not wedged:
        print("No wedged agents.")
        return

    print(f"WEDGE ALARM: {len(wedged)} agent(s) exceeded {threshold_min}min threshold\n")
    for agent_id, entry, elapsed in wedged:
        duration = f"{elapsed:.0f}min" if elapsed is not None else "unknown duration"
        print(f"  {agent_id} ({entry.get('type', 'unknown')}): {duration}")
        task = entry.get("task", "")
        if task:
            print(f"    Task: {task}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    sys.exit(0)
