#!/usr/bin/env python3
"""A crash in the unified gate stays fail-open but is now recorded (B-10).

The top-level handler used to print one stderr line and allow the tool call.
Claude Code does not show PreToolUse stderr on exit 0, so a crash bug could
switch off every check in the gate without anyone seeing it. The handler now
also calls hook_error(), which appends to hook-errors.jsonl where
validate-hook-health reports repeat offenders. Whether a crash should block
instead (B-15) is the owner's call; this keeps the allow.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate_crash.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "pretool-unified-gate.py"


def test_crash_is_recorded_and_still_allows(tmp_path: Path) -> None:
    errors = Path(os.environ["CLAUDE_HOOK_ERRORS_PATH"])
    # tool_input must be an object; a list makes main() raise AttributeError.
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": ["not", "an", "object"]}

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
        cwd=tmp_path,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stdout == "", "a crash must not emit a decision (fail-open)"
    assert "[unified-gate] HOOK-CRASH: AttributeError" in result.stderr
    entries = [json.loads(line) for line in errors.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [(e["hook"], e["type"]) for e in entries] == [("pretool-unified-gate", "AttributeError")]
