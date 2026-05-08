#!/usr/bin/env python3
# hook-version: 1.0.0
"""
Voice Pipeline Tracker — utility script (not a hook).

Tracks completion of the 13-phase voice-writer pipeline for VexJoy blog posts.
State stored in ~/.claude/state/voice-pipeline-state.json.

Usage:
    python3 voice-pipeline-tracker.py record <slug> <phase>
    python3 voice-pipeline-tracker.py status <slug>
    python3 voice-pipeline-tracker.py reset <slug>
    python3 voice-pipeline-tracker.py list
"""

import json
import os
import sys
import tempfile
from pathlib import Path

REQUIRED_PHASES = [
    "LOAD",
    "GROUND",
    "STATS-CHECKPOINT",
    "GENERATE",
    "HOOK-GATE",
    "VALIDATE",
    "REFINE",
    "VARIETY-GATE",
    "JOY-CHECK",
    "ANTI-AI",
    "CLOSE-GATE",
    "OUTPUT",
    "CLEANUP",
]

STATE_FILE = Path.home() / ".claude" / "state" / "voice-pipeline-state.json"


def _load_state() -> dict:
    """Load state file, return empty dict on any error."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_state(state: dict) -> None:
    """Atomic write: temp file + rename."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, str(STATE_FILE))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_record(slug: str, phase: str) -> None:
    phase_upper = phase.upper()
    if phase_upper not in REQUIRED_PHASES:
        print(f"Unknown phase: {phase_upper}", file=sys.stderr)
        print(f"Valid phases: {', '.join(REQUIRED_PHASES)}", file=sys.stderr)
        sys.exit(1)
    state = _load_state()
    if slug not in state:
        state[slug] = {"phases_complete": []}
    phases = state[slug]["phases_complete"]
    if phase_upper not in phases:
        phases.append(phase_upper)
    _save_state(state)
    print(f"[voice-tracker] Recorded {phase_upper} for '{slug}' ({len(phases)}/{len(REQUIRED_PHASES)})")


def cmd_status(slug: str) -> None:
    state = _load_state()
    entry = state.get(slug, {"phases_complete": []})
    complete = entry.get("phases_complete", [])
    missing = [p for p in REQUIRED_PHASES if p not in complete]
    result = {
        "slug": slug,
        "phases_complete": complete,
        "phases_missing": missing,
        "ready_to_publish": len(missing) == 0,
    }
    print(json.dumps(result, indent=2))


def cmd_reset(slug: str) -> None:
    state = _load_state()
    if slug in state:
        del state[slug]
        _save_state(state)
        print(f"[voice-tracker] Reset tracking for '{slug}'")
    else:
        print(f"[voice-tracker] No tracking data for '{slug}'")


def cmd_list() -> None:
    state = _load_state()
    if not state:
        print("[voice-tracker] No articles tracked")
        return
    for slug, entry in state.items():
        n = len(entry.get("phases_complete", []))
        ready = "READY" if n == len(REQUIRED_PHASES) else f"{n}/{len(REQUIRED_PHASES)}"
        print(f"  {slug}: {ready}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: voice-pipeline-tracker.py <record|status|reset|list> [args]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "record":
        if len(sys.argv) < 4:
            print("Usage: voice-pipeline-tracker.py record <slug> <phase>", file=sys.stderr)
            sys.exit(1)
        cmd_record(sys.argv[2], sys.argv[3])
    elif cmd == "status":
        if len(sys.argv) < 3:
            print("Usage: voice-pipeline-tracker.py status <slug>", file=sys.stderr)
            sys.exit(1)
        cmd_status(sys.argv[2])
    elif cmd == "reset":
        if len(sys.argv) < 3:
            print("Usage: voice-pipeline-tracker.py reset <slug>", file=sys.stderr)
            sys.exit(1)
        cmd_reset(sys.argv[2])
    elif cmd == "list":
        cmd_list()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
