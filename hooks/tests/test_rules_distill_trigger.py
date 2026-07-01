#!/usr/bin/env python3
"""
Tests for the rules-distill-trigger hook (Stop hook, ADR-124).

Run with: python3 -m pytest hooks/tests/test_rules_distill_trigger.py -v
"""

import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "rules-distill-trigger.py"


def test_no_state_no_script_exits_0(tmp_path):
    """Baseline: fresh HOME, no distill script present, exits 0 quietly."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert result.returncode == 0


def test_exits_0_on_injected_exception(tmp_path):
    """Point HOME at a state file that is a directory, not a file: reading
    it inside _is_stale() raises IsADirectoryError, uncaught internally.
    The __main__ guard must still exit 0 and print a visibility signal,
    not just silently swallow it (Stop hooks must never fail)."""
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "rules-distill-state.json").mkdir()  # dir where a file is expected

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert result.returncode == 0
    assert "[rules-distill] error: IsADirectoryError" in result.stderr
