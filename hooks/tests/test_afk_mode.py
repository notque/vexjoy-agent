#!/usr/bin/env python3
"""
Tests for the afk-mode hook (SessionStart, ADR-143).

Run with: python3 -m pytest hooks/tests/test_afk_mode.py -v
"""

import os
import subprocess
import sys
from pathlib import Path

HOOK_SRC = Path(__file__).parent.parent / "afk-mode.py"


def test_never_mode_exits_0():
    """Baseline: CLAUDE_AFK_MODE=never exits 0 with empty SessionStart output."""
    result = subprocess.run(
        [sys.executable, str(HOOK_SRC)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_AFK_MODE": "never"},
    )
    assert result.returncode == 0
    assert "SessionStart" in result.stdout


def test_exits_0_on_injected_exception(tmp_path):
    """A crash inside main() must still fail open (exit 0): the __main__
    guard's except-block must catch it and print a visibility signal,
    not just silently swallow it."""
    # Copy the real hook unmodified; point its own `lib/` import at a stub
    # hook_utils that raises, so main()'s call into it crashes for real.
    hook_copy = tmp_path / "afk-mode.py"
    hook_copy.write_text(HOOK_SRC.read_text())
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "hook_utils.py").write_text(
        "import sys\n"
        "def context_output(*a, **k):\n"
        "    raise RuntimeError('injected failure')\n"
        "def empty_output(*a, **k):\n"
        "    raise RuntimeError('injected failure')\n"
        "def hook_error(name, exc):\n"
        "    print(f'[{name}] HOOK-ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)\n"
    )

    result = subprocess.run(
        [sys.executable, str(hook_copy)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_AFK_MODE": "always"},
    )

    assert result.returncode == 0
    assert "[afk-mode] HOOK-ERROR: RuntimeError" in result.stderr
