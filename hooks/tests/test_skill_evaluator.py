#!/usr/bin/env python3
"""
Tests for the skill-evaluator hook, a disabled no-op stub.

The stub stays on disk so an old settings.json that still registers it keeps
working; these tests pin that contract: exit 0, no output, any input.

Run with: python3 -m pytest hooks/tests/test_skill_evaluator.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "skill-evaluator.py"


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def test_disabled_hook_produces_no_output():
    """Hook is disabled (redundant with /do SKILL.md routing tables) and should produce no output."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "implement a new feature with comprehensive testing and documentation",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0, f"Hook failed: {stderr}"
    assert stdout == "", "Disabled hook should produce no output"


def test_handles_invalid_json():
    """Hook should handle invalid JSON gracefully."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not valid json {{{",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, "Should not crash on invalid JSON"
