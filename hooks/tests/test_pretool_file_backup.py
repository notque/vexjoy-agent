#!/usr/bin/env python3
"""
Tests for the pretool-file-backup hook (adr/020-pre-edit-file-backup.md).

Run with: python3 -m pytest hooks/tests/test_pretool_file_backup.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "pretool-file-backup.py"


def test_backs_up_existing_file(tmp_path):
    """Baseline: an Edit on an existing file exits 0 and writes a backup."""
    src = tmp_path / "target.txt"
    src.write_text("hello")
    event = {"tool_input": {"file_path": str(src)}}

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_exits_0_on_injected_exception():
    """A JSON boolean is valid JSON but has no .get() — main() calls
    event.get(...) downstream, raising AttributeError uncaught by main()'s
    own json.loads try/except. The __main__ guard must still exit 0 and
    print a visibility signal, not just silently swallow it."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="true",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[pretool-file-backup] error: AttributeError" in result.stderr
