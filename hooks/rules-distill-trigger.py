#!/usr/bin/env python3
"""Stop hook: auto-trigger rules distillation when stale (ADR-124).

Checks ~/.claude/state/rules-distill-state.json for staleness.
If last run was >7 days ago (or never), launches rules-distill.py
as a background subprocess so session end isn't delayed.

Stop hooks must NEVER fail — entire main() is wrapped in try/except.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STALENESS_DAYS = 7
STATE_DIR = Path.home() / ".claude" / "state"
STATE_FILE = STATE_DIR / "rules-distill-state.json"
PROPOSALS_DIR = Path.home() / ".claude" / "distillation-proposals"
RULES_DISTILL_SCRIPT = Path.home() / ".claude" / "scripts" / "rules-distill.py"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_stale() -> bool:
    """Return True if distillation hasn't run in STALENESS_DAYS or state is missing."""
    if not STATE_FILE.exists():
        return True
    try:
        data = json.loads(STATE_FILE.read_text())
        last_run = data.get("last_distillation_run")
        if not last_run:
            return True
        last_dt = datetime.fromisoformat(last_run)
        age_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
        return age_days >= STALENESS_DAYS
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        return True


def _update_state() -> None:
    """Write current timestamp to state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "last_distillation_run": _now_iso(),
            },
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    # Exit silently if not stale
    if not _is_stale():
        return 0

    # Exit silently if the distillation script doesn't exist
    if not RULES_DISTILL_SCRIPT.exists():
        return 0

    # Ensure proposals directory exists
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    # Launch distillation in background (non-blocking)
    # Use --auto mode which is designed for automated/cron invocation
    subprocess.Popen(
        [sys.executable, str(RULES_DISTILL_SCRIPT), "--auto"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Update state so subsequent calls in same session are idempotent
    _update_state()

    print(
        "[rules-distill] Distillation triggered (backgrounded). "
        "Proposals will appear in ~/.claude/distillation-proposals/"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Stop hooks must NEVER fail
        sys.exit(0)
