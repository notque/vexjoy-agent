#!/usr/bin/env python3
"""Route-loop signal check: the cheap successor to the dropped eval harness.

Reads `<CLAUDE_LEARNING_DIR or ~/.claude/learning>/route-events.jsonl`
(same path convention as hooks/lib/route_events.py) and counts:

  - routing-relevant failure outcome events,
  - decisions with non-null health_at_decision,
  - decisions whose recorded would-action is demote or tiebreak.

Exit 0 = NO-SIGNAL (informational). Exit 3 = SIGNAL: at least one
routing-relevant failure OR one would-demote/would-tiebreak — re-propose the
actuator (see docs/route-loop-validation.md). Read-only: never writes.

Exit 3 is a verdict, not a crash. `learning-db.py route-health` calls
`count_signals` and prints the same verdict, so no separate job runs this file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Import the canonical DB-dir resolver (ADR-122 hardening lives there)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
from learning_db_v2 import get_db_dir

EXIT_NO_SIGNAL = 0
EXIT_SIGNAL = 3


def events_path() -> Path:
    """Resolve route-events.jsonl honoring CLAUDE_LEARNING_DIR."""
    return get_db_dir() / "route-events.jsonl"


def count_signals(path: Path | None = None) -> dict:
    """Count signal events in route-events.jsonl. Read-only.

    Returns ``failures`` (routing-relevant failure outcomes), ``scored``
    (decisions with a non-null health_at_decision), ``would_act``
    (would-demote or would-tiebreak decisions), and ``signal`` (True when
    ``failures`` or ``would_act`` is non-zero). A missing file counts as zeros.
    `learning-db.py route-health` prints the same counts, so the check runs
    whenever route health is read.
    """
    failures = scored = would_act = 0
    path = path or events_path()
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate interleaved/partial lines in the append-only log
            if not isinstance(event, dict):
                continue
            if event.get("type") == "outcome":
                if event.get("outcome") == "failure" and event.get("routing_relevant") is True:
                    failures += 1
            elif event.get("type") == "decision":
                if event.get("health_at_decision") is not None:
                    scored += 1
                if event.get("action") in ("demote", "tiebreak"):
                    would_act += 1
    return {"failures": failures, "scored": scored, "would_act": would_act, "signal": bool(failures or would_act)}


def main() -> int:
    """Count signal events and report NO-SIGNAL (0) or SIGNAL (3)."""
    counts = count_signals()
    print(f"routing-relevant failures: {counts['failures']}")
    print(f"decisions with health_at_decision: {counts['scored']}")
    print(f"would-demote/would-tiebreak decisions: {counts['would_act']}")
    if counts["signal"]:
        print("SIGNAL: re-propose the actuator (docs/route-loop-validation.md)")
        return EXIT_SIGNAL
    print("NO-SIGNAL")
    return EXIT_NO_SIGNAL


if __name__ == "__main__":
    sys.exit(main())
